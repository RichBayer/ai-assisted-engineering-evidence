#!/usr/bin/env python3
"""Standalone public extraction of the accepted worker artifact inventory logic.

This module observes one Git worktree, records every non-clean path reported by
Git (including untracked and ignored/generated paths), and emits deterministic
metadata plus SHA-256 identities without cleaning or modifying the worktree.

The integrated private Agent Operations implementation reuses shared trusted-Git
helpers. This public extraction inlines only the small hardening boundary needed
to make the evidence sample independently readable and runnable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
HASH_CHUNK_BYTES = 1024 * 1024
GIT_TIMEOUT_SECONDS = 30

UNTRACKED_STATUS = "??"
IGNORED_STATUS = "!!"
UNMERGED_STATUS_CODES = frozenset({"DD", "AU", "UD", "UA", "DU", "AA", "UU"})
TRACKED_STATUS_LETTERS = frozenset({" ", "M", "T", "A", "D"})
MISSING_PATH_CLASSIFICATIONS = frozenset({"tracked_deleted", "tracked_unmerged"})
TRUSTED_SEARCH_PATH = ("/usr/bin", "/bin", "/usr/local/bin")
TRUSTED_PATH_VALUE = os.pathsep.join(TRUSTED_SEARCH_PATH)


class InventoryError(RuntimeError):
    """Raised when deterministic inventory evidence cannot be produced safely."""


def trusted_git_executable() -> str:
    """Resolve Git from a fixed trusted search path, never inherited PATH."""
    for directory in TRUSTED_SEARCH_PATH:
        candidate = Path(directory) / "git"
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return os.fspath(resolved)
    raise InventoryError(
        "trusted Git executable could not be resolved from: "
        + ", ".join(TRUSTED_SEARCH_PATH)
    )


def git_environment(workspace: Path) -> dict[str, str]:
    """Build a sanitized environment for one read-only Git query."""
    return {
        "PATH": TRUSTED_PATH_VALUE,
        "HOME": os.fspath(workspace),
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
    }


def _run_git(workspace: Path, *args: str) -> bytes:
    """Run one bounded read-only Git query with sanitized process state."""
    executable = trusted_git_executable()
    try:
        proc = subprocess.run(
            [executable, *args],
            cwd=os.fspath(workspace),
            env=git_environment(Path(workspace)),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise InventoryError(
            f"git {' '.join(args)} exceeded {GIT_TIMEOUT_SECONDS} seconds; "
            "inventory evidence could not be produced"
        ) from exc
    except (OSError, ValueError) as exc:
        raise InventoryError(f"git {' '.join(args)} could not be executed: {exc}") from exc

    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise InventoryError(f"git {' '.join(args)} failed ({proc.returncode}): {detail}")
    return proc.stdout


def _git_root(workspace: Path) -> Path:
    raw = _run_git(workspace, "rev-parse", "--show-toplevel")
    try:
        root = Path(os.fsdecode(raw.rstrip(b"\n"))).resolve(strict=True)
    except (OSError, UnicodeError) as exc:
        raise InventoryError(f"cannot resolve Git worktree root: {exc}") from exc
    requested = workspace.resolve(strict=True)
    if root != requested:
        raise InventoryError(f"workspace must be the Git worktree root: expected {root}")
    return root


def _git_location(root: Path, raw: bytes) -> Path:
    """Resolve a Git-reported repository location, which may be relative."""
    value = os.fsdecode(raw.rstrip(b"\n"))
    if not value:
        raise InventoryError("Git did not report a repository storage location")
    location = Path(value)
    try:
        return location.resolve() if location.is_absolute() else (root / location).resolve()
    except OSError as exc:
        raise InventoryError(f"cannot resolve Git repository storage: {exc}") from exc


def _decode_git_path(raw: bytes) -> str:
    return os.fsdecode(raw)


def _safe_relative_path(path: str) -> str:
    if not path or path.startswith("/") or "\x00" in path:
        raise InventoryError("Git reported an invalid repository-relative path")
    parts = Path(path).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise InventoryError(f"Git reported unsafe path {path!r}")
    return path


def _parse_porcelain_z(payload: bytes) -> list[tuple[str, str]]:
    """Parse ``git status --porcelain=v1 -z --no-renames`` output."""
    records: list[tuple[str, str]] = []
    for raw in payload.split(b"\x00"):
        if not raw:
            continue
        if len(raw) < 4 or raw[2:3] != b" ":
            raise InventoryError("unexpected Git porcelain record")
        try:
            status_text = raw[:2].decode("ascii", "strict")
        except UnicodeDecodeError as exc:
            raise InventoryError("Git porcelain status is not ASCII") from exc
        _classify(status_text)
        path = _safe_relative_path(_decode_git_path(raw[3:]))
        records.append((status_text, path))
    return records


def _classify(status_text: str) -> str:
    """Return the classification of one porcelain XY state, or fail closed."""
    if status_text == UNTRACKED_STATUS:
        return "untracked"
    if status_text == IGNORED_STATUS:
        return "ignored_generated_or_local"
    if status_text in UNMERGED_STATUS_CODES:
        return "tracked_unmerged"
    if (
        len(status_text) != 2
        or status_text == "  "
        or status_text[0] not in TRACKED_STATUS_LETTERS
        or status_text[1] not in TRACKED_STATUS_LETTERS
    ):
        raise InventoryError(
            f"unsupported Git porcelain status {status_text!r}; inventory "
            "evidence cannot be classified safely"
        )
    if "D" in status_text:
        return "tracked_deleted"
    if "A" in status_text:
        return "tracked_added"
    return "tracked_modified"


def _read_chunk(fd: int, size: int) -> bytes:
    """Read one bounded chunk from an already-opened descriptor."""
    return os.read(fd, size)


def _hash_regular_file(path: Path, observed: os.stat_result, rel: str) -> tuple[int, str]:
    """Hash one regular file through a single non-following descriptor."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise InventoryError(
            "O_NOFOLLOW is unavailable; regular-file identity cannot be proven "
            f"without following a symlink: {rel!r}"
        )
    flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOCTTY", 0)
    try:
        handle = os.open(path, flags)
    except OSError as exc:
        raise InventoryError(
            f"regular file could not be opened without following a symlink: {rel!r}: {exc}"
        ) from exc

    try:
        before = os.fstat(handle)
        if not stat.S_ISREG(before.st_mode):
            raise InventoryError(f"unsupported filesystem object in worker inventory: {rel!r}")
        if (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino):
            raise InventoryError(f"file was replaced between observation and hashing: {rel!r}")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = _read_chunk(handle, HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(handle)
    finally:
        os.close(handle)

    if (
        not stat.S_ISREG(after.st_mode)
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or size != after.st_size
    ):
        raise InventoryError(f"file changed while being hashed: {rel!r}")

    try:
        rebound = path.lstat()
    except OSError as exc:
        raise InventoryError(
            f"file path binding changed while being hashed: {rel!r}: {exc}"
        ) from exc

    if (
        not stat.S_ISREG(rebound.st_mode)
        or (
            rebound.st_dev,
            rebound.st_ino,
            rebound.st_size,
            rebound.st_mtime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
    ):
        raise InventoryError(f"file path binding changed while being hashed: {rel!r}")

    return size, digest.hexdigest()


def _path_evidence(root: Path, rel: str, status_text: str) -> dict[str, Any]:
    classification = _classify(status_text)
    candidate = root / rel
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        if classification not in MISSING_PATH_CLASSIFICATIONS:
            raise InventoryError(f"Git reported path that disappeared during inventory: {rel!r}")
        return {
            "path": rel,
            "git_status": status_text,
            "classification": classification,
            "object_type": "missing",
            "size_bytes": None,
            "sha256": None,
        }

    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(candidate)
        target_bytes = os.fsencode(target)
        return {
            "path": rel,
            "git_status": status_text,
            "classification": classification,
            "object_type": "symlink",
            "size_bytes": len(target_bytes),
            "sha256": hashlib.sha256(target_bytes).hexdigest(),
            "symlink_target": target,
        }

    if stat.S_ISREG(info.st_mode):
        size, digest = _hash_regular_file(candidate, info, rel)
        return {
            "path": rel,
            "git_status": status_text,
            "classification": classification,
            "object_type": "regular_file",
            "size_bytes": size,
            "sha256": digest,
        }

    if stat.S_ISDIR(info.st_mode):
        return {
            "path": rel,
            "git_status": status_text,
            "classification": classification,
            "object_type": "directory",
            "size_bytes": None,
            "sha256": None,
        }

    raise InventoryError(f"unsupported filesystem object in worker inventory: {rel!r}")


def build_inventory(workspace: Path) -> dict[str, Any]:
    root = _git_root(workspace)
    head = _run_git(root, "rev-parse", "HEAD").decode("ascii", "strict").strip()
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise InventoryError("Git returned an invalid HEAD identity")

    git_dir = _git_location(root, _run_git(root, "rev-parse", "--git-dir"))
    git_common_dir = _git_location(root, _run_git(root, "rev-parse", "--git-common-dir"))

    payload = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored=traditional",
        "--no-renames",
    )
    records = _parse_porcelain_z(payload)

    seen: set[str] = set()
    artifacts: list[dict[str, Any]] = []
    for status_text, rel in sorted(records, key=lambda item: os.fsencode(item[1])):
        if rel in seen:
            raise InventoryError(f"duplicate path reported by Git: {rel!r}")
        seen.add(rel)
        artifacts.append(_path_evidence(root, rel, status_text))

    counts: dict[str, int] = {}
    for item in artifacts:
        key = str(item["classification"])
        counts[key] = counts.get(key, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_root": os.fspath(root),
        "git_dir": os.fspath(git_dir),
        "git_common_dir": os.fspath(git_common_dir),
        "head_sha": head,
        "artifact_count": len(artifacts),
        "classification_counts": dict(sorted(counts.items())),
        "artifacts": artifacts,
    }


def _denied_output_roots(root: Path, manifest: dict[str, Any]) -> tuple[Path, ...]:
    denied = [root]
    for key in ("git_dir", "git_common_dir"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value:
            continue
        location = Path(value)
        denied.append(location)
        if location.name == ".git":
            denied.append(location.parent)
    return tuple(denied)


def _assert_external_output(root: Path, output: Path, manifest: dict[str, Any]) -> Path:
    parent = output.parent.resolve(strict=True)
    resolved = parent / output.name
    for denied in _denied_output_roots(root, manifest):
        if resolved == denied or denied in resolved.parents:
            raise InventoryError(
                "manifest output must be outside the repository worktree and its "
                f"Git storage: {denied}"
            )
    if output.is_symlink():
        raise InventoryError("refusing to replace symlink manifest output")
    return resolved


def write_manifest_external(root: Path, output: Path, manifest: dict[str, Any]) -> None:
    target = _assert_external_output(root, output, manifest)
    encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        manifest = build_inventory(args.workspace)
        root = Path(manifest["workspace_root"])
        write_manifest_external(root, args.output, manifest)
    except (InventoryError, OSError, UnicodeError) as exc:
        print(f"AO_WORKER_ARTIFACT_INVENTORY_FAILED: {exc}", file=sys.stderr)
        return 2
    print("AO_WORKER_ARTIFACT_INVENTORY_OK")
    print(f"artifact_count={manifest['artifact_count']}")
    print(f"head_sha={manifest['head_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
