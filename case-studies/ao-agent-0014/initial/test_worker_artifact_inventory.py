from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from worker_artifact_inventory import (
    InventoryError,
    build_inventory,
    write_manifest_external,
)


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
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
        git(repo, "config", "user.email", "ao@example.invalid")
        git(repo, "config", "user.name", "AO Test")
        (repo / ".gitignore").write_text("*.pyc\nignored/\n", encoding="utf-8")
        (repo / "tracked.txt").write_bytes(b"base\n")
        git(repo, "add", ".gitignore", "tracked.txt")
        git(repo, "commit", "-m", "base")
        return temp, repo

    def by_path(self, manifest: dict) -> dict[str, dict]:
        return {item["path"]: item for item in manifest["artifacts"]}

    def test_inventory_captures_tracked_untracked_and_ignored_files(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "tracked.txt").write_bytes(b"changed\n")
        (repo / "new file.txt").write_bytes(b"new\x00bytes")
        (repo / "cache.pyc").write_bytes(b"generated")

        manifest = build_inventory(repo)
        items = self.by_path(manifest)

        self.assertEqual(items["tracked.txt"]["classification"], "tracked_modified")
        self.assertEqual(items["new file.txt"]["classification"], "untracked")
        self.assertEqual(items["cache.pyc"]["classification"], "ignored_generated_or_local")
        self.assertEqual(items["new file.txt"]["size_bytes"], 9)
        self.assertEqual(items["new file.txt"]["sha256"], hashlib.sha256(b"new\x00bytes").hexdigest())

    def test_deleted_tracked_file_is_recorded_without_hash(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "tracked.txt").unlink()

        item = self.by_path(build_inventory(repo))["tracked.txt"]
        self.assertEqual(item["classification"], "tracked_deleted")
        self.assertEqual(item["object_type"], "missing")
        self.assertIsNone(item["size_bytes"])
        self.assertIsNone(item["sha256"])

    def test_symlink_identity_hashes_link_text_without_following_target(self) -> None:
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
        self.assertEqual(item["object_type"], "symlink")
        self.assertEqual(item["sha256"], hashlib.sha256(os.fsencode(target)).hexdigest())
        self.assertNotEqual(item["sha256"], hashlib.sha256(b"outside-secret").hexdigest())

    def test_filename_with_newline_survives_nul_delimited_git_status(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        name = "line\nbreak.txt"
        (repo / name).write_bytes(b"x")
        self.assertIn(name, self.by_path(build_inventory(repo)))

    def test_workspace_must_be_exact_git_root(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        child = repo / "child"
        child.mkdir()
        with self.assertRaisesRegex(InventoryError, "workspace must be the Git worktree root"):
            build_inventory(child)

    def test_external_manifest_is_canonical_json_and_exclusive_create(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / "new.txt").write_bytes(b"new")
        manifest = build_inventory(repo)
        output = Path(temp.name) / "evidence" / "manifest.json"
        output.parent.mkdir()

        write_manifest_external(repo.resolve(), output, manifest)
        raw = output.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(json.loads(raw), manifest)
        with self.assertRaises(FileExistsError):
            write_manifest_external(repo.resolve(), output, manifest)

    def test_manifest_output_inside_repository_is_denied(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        manifest = build_inventory(repo)
        with self.assertRaisesRegex(InventoryError, "outside the repository"):
            write_manifest_external(repo.resolve(), repo / "manifest.json", manifest)

    def test_manifest_output_symlink_is_denied(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        manifest = build_inventory(repo)
        evidence = Path(temp.name) / "evidence"
        evidence.mkdir()
        real = evidence / "real.json"
        real.write_text("keep", encoding="utf-8")
        link = evidence / "manifest.json"
        try:
            link.symlink_to(real)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaisesRegex(InventoryError, "symlink"):
            write_manifest_external(repo.resolve(), link, manifest)
        self.assertEqual(real.read_text(encoding="utf-8"), "keep")

    def test_clean_workspace_has_empty_inventory(self) -> None:
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        manifest = build_inventory(repo)
        self.assertEqual(manifest["artifact_count"], 0)
        self.assertEqual(manifest["classification_counts"], {})
        self.assertEqual(manifest["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
