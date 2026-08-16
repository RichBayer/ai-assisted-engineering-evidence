# Provenance of the Public Accepted Extraction

This directory is intentionally **not** presented as a byte-for-byte copy of the accepted private Agent Operations implementation.

## Private accepted source

The integrated implementation is:

- private repository: `RichBayer/agent-operations`
- module: `scripts/worker_artifact_inventory.py`
- accepted task: `AO-AGENT-0014 — Deterministic Worker Artifact Inventory And Hash Manifest`
- merged through Agent Operations PR #24
- merge commit: `b62f2b61e5308b6c7bf6db3cd09a49c06f0bc0b8`

The accepted private module reuses trusted Git execution primitives from neighboring Agent Operations modules rather than duplicating them.

## What was changed for this public package

The public `worker_artifact_inventory.py` preserves the accepted artifact-inventory behavior while making the sample independently readable and runnable.

Packaging changes are limited to the dependency boundary:

1. the imports of private shared helpers were removed;
2. a small fixed trusted Git search path was defined locally;
3. trusted Git executable resolution was inlined;
4. sanitized Git child-environment construction was inlined;
5. Agent-Operations-specific exception types around those shared helpers were replaced with this module's `InventoryError`.

The inventory behavior retained from the accepted implementation includes:

- explicit seven-state unmerged/conflict classification;
- fail-closed malformed/unsupported porcelain handling;
- NUL-delimited raw-byte Git status parsing;
- ignored/generated per-file enumeration;
- sanitized, bounded, shell-free Git execution;
- symlink identity hashing without target dereference;
- `O_NOFOLLOW` regular-file opening where supported;
- descriptor identity and concurrent-change checks;
- post-hash repository-path binding verification;
- deterministic path ordering and canonical JSON output;
- output denial inside the observed worktree, Git storage, and canonical checkout associated with linked worktrees.

## Test provenance

The final integrated private task passed:

- 34/34 targeted tests;
- 279/279 full Agent Operations tests;
- task packet/context validation;
- independent source review before human acceptance.

The public test file is a **reviewer-oriented adversarial subset**, adapted to the standalone import/package shape. It intentionally concentrates on the defects that mattered during review rather than reproducing unrelated private repository integration tests.

The original nine-test candidate is preserved separately under `../initial/` so reviewers can compare the coverage and implementation assumptions before and after review.

## Why this distinction matters

Publishing a broken copy that still imported private modules would be poor evidence. Quietly rewriting it and calling it identical would be worse.

This file makes the transformation explicit so the public sample can be evaluated on its own while preserving an honest chain back to the integrated accepted implementation.
