# Case Study: AO-AGENT-0014

## Deterministic Worker Artifact Inventory and Hash Manifest

This case study is included because the first implementation looked successful by conventional signals and still was not good enough to accept.

The task was to build a deterministic, read-only evidence primitive for a Git worktree. It needed to inventory non-clean paths—including tracked, untracked, ignored/generated, deleted, symlink, and conflict states—and record bounded metadata plus SHA-256 identities without mutating the worktree.

## Why the task mattered

AI-assisted implementation creates a provenance problem: after a worker changes a repository, the review process needs a trustworthy answer to “what is actually different here?” A worker-authored summary is not sufficient evidence by itself.

This helper was designed as a low-level evidence primitive that could describe changed workspace artifacts deterministically before later review/retention decisions.

## Initial candidate

The initial implementation was compact and standalone. Its validation results were all green:

- Python compilation: **PASS**
- targeted tests: **9/9 PASS**
- full repository suite: **254/254 PASS**
- task packet validation: **PASS**
- context validation: **PASS**
- workspace validation: **PASS**

That candidate was **not accepted**.

Independent adversarial source review found multiple blocking defects despite the green test results:

1. several Git conflict states could be misclassified because ordinary `A`/`D` handling happened before complete unmerged-state handling;
2. Git execution inherited process/environment behavior that should have been hardened rather than trusted;
3. regular-file hashing had a symlink/pathname time-of-check/time-of-use weakness;
4. ignored-directory status behavior could collapse evidence instead of preserving per-file hashes;
5. malformed or unsupported porcelain status states could fall through to a guessed classification instead of failing closed.

The detailed findings are summarized in [`review/findings.md`](review/findings.md).

## Bounded AI repair

A single authorized AI repair addressed those findings within the existing task boundary. After the repair:

- targeted tests: **33/33 PASS**
- full repository suite: **278/278 PASS**
- packet/context/workspace validation: **PASS**

The work still was **not accepted yet**.

A second independent source review found another race: a file descriptor can remain stable after the repository pathname is renamed away and replaced. The implementation could therefore hash the original object while the manifest path now referred to a different object.

That was corrected with a final bounded human/control-plane change that revalidated the pathname binding after hashing.

## Final validation and acceptance

After the final correction:

- Python compilation: **PASS**
- targeted tests: **34/34 PASS**
- full repository suite: **279/279 PASS**
- task packet/context validation: **PASS**
- independent review: blockers resolved
- human acceptance: **APPROVED**

The accepted private implementation was merged through PR #24 in Agent Operations with merge commit:

`b62f2b61e5308b6c7bf6db3cd09a49c06f0bc0b8`

## What changed between “green” and “accepted”

The important change was not simply a larger test count. The engineering understanding improved.

The accepted behavior added or strengthened:

- explicit handling for all seven Git porcelain v1 unmerged states;
- fail-closed handling for malformed/unsupported statuses;
- trusted Git executable and sanitized Git environment behavior;
- bounded Git execution with explicit timeout;
- per-file ignored/generated evidence rather than collapsed ignored directories;
- non-dereferencing regular-file opens;
- object identity checks before/during hashing;
- post-hash pathname-binding verification;
- stronger output-location protections, including Git storage and linked-worktree cases;
- adversarial tests for the defects found during review.

## Files in this case study

- `initial/` preserves the original candidate and its original nine-test suite.
- `review/findings.md` explains why that passing candidate failed review.
- `accepted/` contains the public standalone extraction of the accepted logic and its tests, plus provenance notes.
- `retrospective.md` explains what I learned from the sequence and how I use AI in the engineering loop.

## Why I am publishing the failure history

A cleaned-up final implementation would show code. It would not show judgment.

The useful evidence here is that the system did not treat AI output, a clean compile, or hundreds of green tests as sufficient reason to accept the work. Review changed the code twice, and the second defect was found only after the first repair had also passed its tests.

That is the behavior I want from AI-assisted engineering: faster iteration without lowering the acceptance bar.
