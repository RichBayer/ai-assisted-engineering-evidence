# Review Findings

The initial AO-AGENT-0014 candidate compiled and passed its targeted and repository-wide tests. Independent source review still found blockers.

## Initial review blockers

### 1. Conflict-state classification was not reliable

The original classifier checked for ordinary deletion/addition before fully handling unmerged Git states. Several porcelain conflict codes contain `A` or `D`, so they could be recorded as ordinary additions/deletions instead of conflicts.

**Why it mattered:** evidence classification must not silently turn a conflict into a normal worker change.

**Correction:** define and handle all seven porcelain v1 unmerged XY states before ordinary tracked classifications.

### 2. Git execution trusted inherited process state

The original helper invoked `git` by name and inherited the ambient environment.

**Why it mattered:** inherited `PATH` or `GIT_*` variables can redirect executable resolution, repository state, configuration, object directories, or other behavior. An evidence primitive should not trust those inputs implicitly.

**Correction:** resolve a trusted Git executable independently of inherited `PATH`, construct a sanitized child environment, disable prompts/pager and system/global config influence, use list-form `shell=False`, and bound each query with a timeout.

### 3. Regular-file hashing had a symlink/pathname TOCTOU gap

The initial implementation performed `lstat`, then reopened the pathname through normal file APIs to hash it.

**Why it mattered:** an attacker or concurrent process could replace the regular file with a symlink between observation and open, causing the evidence helper to dereference a different target.

**Correction:** open with non-following descriptor semantics (`O_NOFOLLOW` where available), use `fstat` to prove object type and identity, hash through that descriptor, and fail closed when identity or content changes.

### 4. Ignored directories could collapse per-file evidence

The initial Git status mode used ignored matching behavior that may report an ignored directory as one record.

**Why it mattered:** a directory record cannot preserve individual artifact byte sizes and hashes, defeating the purpose of an artifact manifest.

**Correction:** enumerate ignored content in a mode that preserves individual files alongside `--untracked-files=all`.

### 5. Unsupported porcelain states failed open

The initial classifier had a broad fallback to `tracked_modified`.

**Why it mattered:** malformed, unknown, or unexpectedly shaped status data could be converted into plausible-looking evidence instead of stopping the inventory.

**Correction:** validate the XY state explicitly and reject unsupported/malformed states.

## Post-repair review blocker

The first repair addressed all five findings and expanded the targeted suite to 33 passing tests. A second source review found one additional race.

### 6. Descriptor stability did not prove pathname stability

The repaired implementation correctly proved that the file descriptor continued to refer to the same object during hashing. But a descriptor remains valid if that object is renamed away. Another file could then be placed at the original repository pathname.

The manifest could therefore bind:

- the **path** of the replacement file,
- to the **hash** of the original file held by the descriptor.

**Correction:** after hashing, perform a fresh non-following pathname observation and require its device, inode, size, and modification time to match the object that was actually hashed.

This finding became the 34th targeted adversarial test.

## Review lesson

None of these defects were disproved by the initial green tests because the tests did not yet model them.

The review process changed the test suite as understanding changed. That is why the acceptance gate uses tests as evidence rather than treating a passing suite as self-certifying proof of correctness.
