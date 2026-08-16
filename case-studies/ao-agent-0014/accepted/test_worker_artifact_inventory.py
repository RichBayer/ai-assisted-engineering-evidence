from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import worker_artifact_inventory as inventory
from worker_artifact_inventory import InventoryError, build_inventory, write_manifest_external

UNMERGED_STAGES = {
    "DD": (1,),
    "AU": (2,),
    "UD": (1, 2),
    "UA": (3,),
    "DU": (1, 3),
    "AA": (2, 3),
    "UU": (1, 2, 3),
}
UNMERGED_DELETING_STATES = ("DD", "UD", "DU")


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return proc.stdout


class WorkerArtifactInventoryTests(unittest.TestCase):
    def make_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name) / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "evidence@example.invalid")
        git(repo, "config", "user.name", "Evidence Test")
        (repo / ".gitignore").write_text("*.pyc\nignored/\n", encoding="utf-8")
        (repo / "tracked.txt").write_bytes(b"base\n")
        git(repo, "add", ".gitignore", "tracked.txt")
        git(repo, "commit", "-m", "base")
        return temp, repo

    def by_path(self, manifest: dict) -> dict[str, dict]:
        return {item["path"]: item for item in manifest["artifacts"]}

    def stage_unmerged(self, repo: Path, path: str, stages: tuple[int, ...], blob: str) -> None:
        payload = "".join(f"100644 {blob} {stage}\t{path}\n" for stage in stages)
        git(repo, "update-index", "--index-info", stdin=payload)

    def test_captures_tracked_untracked_and_ignored_files(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "tracked.txt").write_bytes(b"changed\n")
        (repo / "new file.txt").write_bytes(b"new\x00bytes")
        (repo / "cache.pyc").write_bytes(b"generated")

        items = self.by_path(build_inventory(repo))
        self.assertEqual(items["tracked.txt"]["classification"], "tracked_modified")
        self.assertEqual(items["new file.txt"]["classification"], "untracked")
        self.assertEqual(items["cache.pyc"]["classification"], "ignored_generated_or_local")
        self.assertEqual(items["new file.txt"]["sha256"], hashlib.sha256(b"new\x00bytes").hexdigest())

    def test_all_seven_unmerged_states_are_classified_before_add_delete(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        blob = git(repo, "hash-object", "-w", "--stdin", stdin="conflict\n").strip()

        for code, stages in sorted(UNMERGED_STAGES.items()):
            name = f"conflict_{code.lower()}.txt"
            if code not in UNMERGED_DELETING_STATES:
                (repo / name).write_bytes(b"conflict\n")
            self.stage_unmerged(repo, name, stages, blob)

        manifest = build_inventory(repo)
        items = self.by_path(manifest)
        for code in sorted(UNMERGED_STAGES):
            item = items[f"conflict_{code.lower()}.txt"]
            self.assertEqual(item["git_status"], code)
            self.assertEqual(item["classification"], "tracked_unmerged")
        self.assertEqual(manifest["classification_counts"]["tracked_unmerged"], 7)

    def test_unknown_porcelain_status_fails_closed(self) -> None:
        for payload in (b"ZZ file.txt\x00", b"XM file.txt\x00", b"U  file.txt\x00"):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(InventoryError, "unsupported Git porcelain status"):
                    inventory._parse_porcelain_z(payload)

    def test_malformed_or_escaping_paths_fail_closed(self) -> None:
        with self.assertRaisesRegex(InventoryError, "unexpected Git porcelain record"):
            inventory._parse_porcelain_z(b"??x.txt\x00")
        with self.assertRaisesRegex(InventoryError, "unsafe path"):
            inventory._parse_porcelain_z(b"?? ../escape.txt\x00")
        with self.assertRaisesRegex(InventoryError, "invalid repository-relative path"):
            inventory._parse_porcelain_z(b"?? /absolute.txt\x00")

    def test_ignored_directory_keeps_per_file_hash_evidence(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        generated = repo / "ignored"
        generated.mkdir()
        payloads = {
            "ignored/alpha.txt": b"alpha-generated",
            "ignored/beta.bin": b"\x00\x01beta",
        }
        for rel, body in payloads.items():
            (repo / rel).write_bytes(body)

        items = self.by_path(build_inventory(repo))
        for rel, body in payloads.items():
            self.assertEqual(items[rel]["object_type"], "regular_file")
            self.assertEqual(items[rel]["size_bytes"], len(body))
            self.assertEqual(items[rel]["sha256"], hashlib.sha256(body).hexdigest())

    def test_git_environment_is_built_not_inherited(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        hostile = {
            "GIT_DIR": "/hostile/.git",
            "GIT_WORK_TREE": "/hostile",
            "GIT_INDEX_FILE": "/hostile/index",
            "GIT_COMMON_DIR": "/hostile/.git",
            "GIT_EXTERNAL_DIFF": "/hostile/diff",
            "GIT_SSH_COMMAND": "/hostile/ssh",
        }
        with patch.dict(os.environ, hostile):
            environment = inventory.git_environment(repo.resolve())

        for name in hostile:
            self.assertNotIn(name, environment)
        self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")

    def test_git_executable_ignores_inherited_path(self) -> None:
        with patch.dict(os.environ, {"PATH": "/nonexistent-hostile-bin"}):
            executable = inventory.trusted_git_executable()
        self.assertTrue(os.path.isabs(executable))
        self.assertNotIn("/nonexistent-hostile-bin", executable)

    def test_hostile_git_environment_cannot_redirect_inventory(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "real.txt").write_bytes(b"real")

        other = Path(temp.name) / "other"
        other.mkdir()
        git(other, "init")
        git(other, "config", "user.email", "evidence@example.invalid")
        git(other, "config", "user.name", "Evidence Test")
        (other / "seed.txt").write_bytes(b"seed")
        git(other, "add", "seed.txt")
        git(other, "commit", "-m", "seed")
        (other / "decoy.txt").write_bytes(b"decoy")

        hostile_environment = {
            "PATH": "/nonexistent-hostile-bin",
            "GIT_DIR": os.fspath(other / ".git"),
            "GIT_WORK_TREE": os.fspath(other),
            "GIT_INDEX_FILE": os.fspath(other / ".git" / "index"),
            "GIT_COMMON_DIR": os.fspath(other / ".git"),
        }
        with patch.dict(os.environ, hostile_environment):
            manifest = build_inventory(repo)

        items = self.by_path(manifest)
        self.assertIn("real.txt", items)
        self.assertNotIn("decoy.txt", items)
        self.assertNotIn("seed.txt", items)

    def test_git_timeout_fails_closed(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)

        def timeout_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="git", timeout=inventory.GIT_TIMEOUT_SECONDS)

        with patch.object(inventory.subprocess, "run", timeout_run):
            with self.assertRaisesRegex(InventoryError, "exceeded"):
                build_inventory(repo)

    def test_symlink_identity_hashes_link_text_not_target(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        outside = Path(temp.name) / "secret.txt"
        outside.write_bytes(b"outside-secret")
        link = repo / "link"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        item = self.by_path(build_inventory(repo))["link"]
        target = os.readlink(link)
        self.assertEqual(item["sha256"], hashlib.sha256(os.fsencode(target)).hexdigest())
        self.assertNotEqual(item["sha256"], hashlib.sha256(b"outside-secret").hexdigest())

    def test_regular_file_replaced_between_observation_and_open_fails(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        original = repo / "original.txt"
        replacement = repo / "replacement.txt"
        original.write_bytes(b"original")
        replacement.write_bytes(b"replacement")

        with self.assertRaisesRegex(InventoryError, "replaced between observation and hashing"):
            inventory._hash_regular_file(original, replacement.lstat(), "original.txt")

    def test_concurrent_change_during_hash_fails(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        target = repo / "racing.txt"
        target.write_bytes(b"0123456789")
        observed = target.lstat()
        real_read = inventory._read_chunk
        state = {"raced": False}

        def racing_read(fd: int, size: int) -> bytes:
            chunk = real_read(fd, size)
            if chunk and not state["raced"]:
                state["raced"] = True
                with open(target, "ab") as handle:
                    handle.write(b"appended-during-hash")
            return chunk

        with patch.object(inventory, "_read_chunk", racing_read), patch.object(
            inventory, "HASH_CHUNK_BYTES", 4
        ):
            with self.assertRaisesRegex(InventoryError, "changed while being hashed"):
                inventory._hash_regular_file(target, observed, "racing.txt")

    def test_path_replaced_after_open_fails_binding_check(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        target = repo / "binding-race.txt"
        target.write_bytes(b"0123456789abcdef")
        observed = target.lstat()
        displaced = repo / "binding-race-original.txt"
        replacement = b"replacement-path-bytes"
        real_read = inventory._read_chunk
        state = {"replaced": False}

        def replacing_read(fd: int, size: int) -> bytes:
            chunk = real_read(fd, size)
            if chunk and not state["replaced"]:
                state["replaced"] = True
                target.rename(displaced)
                target.write_bytes(replacement)
            return chunk

        with patch.object(inventory, "_read_chunk", replacing_read), patch.object(
            inventory, "HASH_CHUNK_BYTES", 4
        ):
            with self.assertRaisesRegex(InventoryError, "path binding changed while being hashed"):
                inventory._hash_regular_file(target, observed, "binding-race.txt")

        self.assertEqual(target.read_bytes(), replacement)
        self.assertEqual(displaced.read_bytes(), b"0123456789abcdef")

    def test_manifest_is_deterministic_and_time_free(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "tracked.txt").write_bytes(b"changed\n")
        (repo / "b.txt").write_bytes(b"b")
        (repo / "a.txt").write_bytes(b"a")
        first = build_inventory(repo)
        second = build_inventory(repo)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )
        keys = set(first) | {key for item in first["artifacts"] for key in item}
        for key in keys:
            self.assertNotIn("time", key)
            self.assertNotIn("date", key)

    def test_manifest_output_is_external_exclusive_and_canonical(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "new.txt").write_bytes(b"new")
        manifest = build_inventory(repo)
        output = Path(temp.name) / "evidence" / "manifest.json"
        output.parent.mkdir()

        write_manifest_external(repo.resolve(), output, manifest)
        self.assertEqual(json.loads(output.read_bytes()), manifest)
        with self.assertRaises(FileExistsError):
            write_manifest_external(repo.resolve(), output, manifest)
        with self.assertRaisesRegex(InventoryError, "outside the repository"):
            write_manifest_external(repo.resolve(), repo / "manifest.json", manifest)

    def test_linked_worktree_git_storage_and_canonical_checkout_are_denied(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        linked = Path(temp.name) / "linked"
        git(repo, "worktree", "add", "-b", "probe", os.fspath(linked))

        manifest = build_inventory(linked)
        root = Path(manifest["workspace_root"])
        for denied in (
            repo / ".git" / "manifest.json",
            repo / ".git" / "worktrees" / "manifest.json",
            repo / "manifest.json",
        ):
            with self.subTest(denied=denied):
                with self.assertRaisesRegex(InventoryError, "outside the repository"):
                    write_manifest_external(root, denied, manifest)


if __name__ == "__main__":
    unittest.main()
