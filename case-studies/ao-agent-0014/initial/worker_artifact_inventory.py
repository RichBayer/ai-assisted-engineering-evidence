#!/usr/bin/env python3
"""Build a deterministic, read-only inventory of worker-created workspace artifacts.

This is a Class B evidence primitive.  It observes one Git worktree, records every
non-clean path reported by Git (including untracked and matching ignored paths),
and emits bounded metadata plus SHA-256 identities without cleaning or modifying
the worktree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

SCHEMA_VERSION = 1
HASH_CHUNK_BYTES = 1024 * 1024


class InventoryError(RuntimeError):
    """Raised when deterministic inventory evidence cannot be produced safely."""


def _run_git(workspace: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", os.fspath(workspace), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
    )
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
    """Parse `git status --porcelain=v1 -z --no-renames` output."""
    records: list[tuple[str, str]] = []
    for raw in payload.split(b"\x00"):
        if not raw:
            continue
        if len(raw) < 4 or raw[2:3] != b" ":
            raise InventoryError("unexpected Git porcelain record")
        status_text = raw[:2].decode("ascii", "strict")
        path = _safe_relative_path(_decode_git_path(raw[3:]))
        records.append((status_text, path))
    return records


def _classify(status_text: str) -> str:
    if status_text == "??":
        return "untracked"
    if status_text == "!!":
        return "ignored_generated_or_local"
    if "D" in status_text:
        return "tracked_deleted"
    if "A" in status_text:
        return "tracked_added"
    if "U" in status_text or status_text in {"AA", "DD"}:
        return "tracked_unmerged"
    return "tracked_modified"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as handle:
        while True:
            chunk = handle.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _path_evidence(root: Path, rel: str, status_text: str) -> dict[str, Any]:
    candidate = root / rel
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        if _classify(status_text) != "tracked_deleted":
            raise InventoryError(f"Git reported path that disappeared during inventory: {rel!r}")
        return {
            "path": rel,
            "git_status": status_text,
            "classification": "tracked_deleted",
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
            "classification": _classify(status_text),
            "object_type": "symlink",
            "size_bytes": len(target_bytes),
            "sha256": hashlib.sha256(target_bytes).hexdigest(),
            "symlink_target": target,
        }

    if stat.S_ISREG(info.st_mode):
        before = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        digest = _sha256_file(candidate)
        after_info = candidate.lstat()
        after = (after_info.st_dev, after_info.st_ino, after_info.st_size, after_info.st_mtime_ns)
        if before != after or not stat.S_ISREG(after_info.st_mode):
            raise InventoryError(f"file changed while being hashed: {rel!r}")
        return {
            "path": rel,
            "git_status": status_text,
            "classification": _classify(status_text),
            "object_type": "regular_file",
            "size_bytes": after_info.st_size,
            "sha256": digest,
        }

    if stat.S_ISDIR(info.st_mode):
        return {
            "path": rel,
            "git_status": status_text,
            "classification": _classify(status_text),
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

    payload = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored=matching",
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
        "head_sha": head,
        "artifact_count": len(artifacts),
        "classification_counts": dict(sorted(counts.items())),
        "artifacts": artifacts,
    }


def _assert_external_output(root: Path, output: Path) -> Path:
    parent = output.parent.resolve(strict=True)
    resolved = parent / output.name
    if resolved == root or root in resolved.parents:
        raise InventoryError("manifest output must be outside the repository worktree")
    if output.exists() and output.is_symlink():
        raise InventoryError("refusing to replace symlink manifest output")
    return resolved


def write_manifest_external(root: Path, output: Path, manifest: dict[str, Any]) -> None:
    target = _assert_external_output(root, output)
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
