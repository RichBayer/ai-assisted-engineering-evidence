# Claude Code Local Independent Review Runbook

## Purpose

Use this runbook when a local Claude Code session should independently review this repository without receiving GitHub credentials or repository write authority.

The default review model is:

1. work from a local clone;
2. keep the target branch explicit;
3. give Claude read access to this repository and only the additional source repositories needed for provenance checks;
4. deny Claude file-edit tools for the review session;
5. approve Bash commands manually and only when they are read-only inspection or bounded validation/test commands;
6. collect findings before authorizing any repair;
7. keep human acceptance, commit, push, PR, merge, publication, and application-submission authority separate.

This runbook records the operating procedure. It is not itself authority to modify a repository.

## Current AHEAD Evidence Review Target

Repository:

`/mnt/g/ai/projects/ai-assisted-engineering-evidence`

Review branch:

`career/ahead-evidence-foundation-20260816`

Private provenance source that Claude may read when needed:

`/mnt/g/ai/projects/agent-operations`

Claude must not modify the private provenance source during this review.

## 1. Reconcile the local review target

From the evidence repository:

```bash
pwd
git status -sb
git branch --show-current
git fetch origin
git status -sb
git log --oneline --decorate -5
```

Expected review branch:

`career/ahead-evidence-foundation-20260816`

Do not start the review if the checkout has unexplained local modifications or is on the wrong branch.

## 2. Check Claude Code before use

```bash
claude --version
claude doctor
```

If authentication is requested, use the already-approved local Claude account/subscription path. Do not add GitHub integration merely to perform this local review.

## 3. Start a bounded interactive review session

Run Claude Code from the root of this repository:

```bash
claude --model opus \
  --add-dir /mnt/g/ai/projects/agent-operations \
  --disallowedTools Edit Write
```

Why this shape:

- `--model opus` selects the current Opus alias for a high-effort independent review.
- `--add-dir` gives Claude read visibility into the private Agent Operations checkout for provenance verification.
- `--disallowedTools Edit Write` prevents the normal Claude file-edit/write tools from being used in this review session.
- Bash remains permission-gated. Approve only commands that are clearly read-only inspection commands or bounded tests/validation for this review.

Do **not** use `--dangerously-skip-permissions`.

Do **not** use `--permission-mode acceptEdits` for an independent review.

`--permission-mode plan` is not the normal choice here because plan mode also prevents command execution; this review needs to run tests.

## 4. Permission behavior during the session

Claude Code can normally read/search files without a per-read approval prompt. Bash commands normally require approval unless separately allowed.

For this review, approve only commands in these categories:

- repository identity/state inspection, such as `pwd`, `git status`, `git branch`, `git log`, `git diff`, `git show`, `git rev-parse`;
- file/content inspection, such as `cat`, `sed`, `head`, `tail`, `find`, `grep`, `rg`, `wc`, `stat`;
- Python syntax/test execution for the public sample;
- other commands that are demonstrably read-only and necessary to validate a finding.

Reject commands that would mutate repository or external state, including examples such as:

- `git add`, `git commit`, `git push`, `git merge`, `git rebase`, `git reset`, `git checkout`/`git switch` when used to change the working state;
- file-writing redirection, `rm`, `mv`, `cp` into a repository, formatting/fix commands, package installation, or dependency updates;
- GitHub CLI writes, PR/issue writes, releases, deployments, or external-service mutations.

If a command is unfamiliar, do not approve it until its effect is understood.

## 5. Independent review prompt

Paste the following into the interactive Claude Code session:

---

You are performing an independent, READ-ONLY adversarial review of the current branch of `ai-assisted-engineering-evidence`.

Do not edit files. Do not create files. Do not commit, push, merge, rebase, switch branches, create issues or pull requests, or modify GitHub/external state.

You may run read-only inspection commands and bounded tests. You may read `/mnt/g/ai/projects/agent-operations` only as needed to verify provenance and technical claims about AO-AGENT-0014. Treat that repository as authoritative private source material and do not modify it.

Review this repository from two independent perspectives:

1. an experienced software engineer assessing technical credibility; and
2. a skeptical AHEAD hiring reviewer assessing whether this evidence demonstrates that Richard can understand, test, debug, review, harden, and own AI-assisted software rather than blindly accepting model output.

Inspect the root README, method documentation, bounded task example, AO-AGENT-0014 chronology, original candidate and tests, review findings, accepted standalone extraction, accepted regression tests, provenance documentation, retrospective, and CI workflow.

Actively look for:

- code defects or unsafe edge cases in the public standalone extraction;
- missing or weak adversarial tests;
- discrepancies between the original source, stated review findings, accepted source, and private authoritative Agent Operations implementation;
- provenance claims that are inaccurate, ambiguous, or overstated;
- technical or hiring claims that exceed the evidence;
- places where green-test history is described misleadingly;
- security, filesystem, Git, encoding, race, determinism, or failure-mode issues;
- documentation that looks like process theater rather than useful engineering control;
- material information a reviewer needs that is buried or hard to find;
- unnecessary complexity that weakens the hiring signal;
- interview claims Richard would be unable to defend from the repository evidence alone;
- any private/internal information that should not be exposed publicly.

Run the relevant public tests. Also compare the public accepted extraction against the private authoritative Agent Operations implementation closely enough to verify the stated extraction/provenance boundary.

Do not repair anything in this pass.

Classify every finding as:

- BLOCKING — should prevent merge/public use;
- IMPORTANT — should be corrected before using this repository in the AHEAD application unless there is a strong reason not to;
- OPTIONAL — useful improvement that is not required for credibility.

For each BLOCKING or IMPORTANT finding, provide:

- exact file/path and relevant function, section, or line area;
- concrete evidence;
- why it matters technically or as hiring evidence;
- the smallest correction that would resolve it;
- whether the finding requires code changes, test changes, documentation changes, or only clarification.

Finish with four explicit outputs:

1. **Test/validation results** — exact commands run and results observed.
2. **Engineering evidence verdict** — whether the repository is technically credible as currently written.
3. **Hiring-signal verdict** — whether linking this repository would strengthen Richard Bayer's AHEAD Software Engineer application.
4. **Merge recommendation** — `MERGE`, `MERGE AFTER IMPORTANT FIXES`, or `DO NOT MERGE`, with reasons.

Do not flatter the candidate. Do not recommend changes merely to make the repository longer or more polished. Optimize for correctness, credibility, reviewer time, and defensible engineering evidence.

---

## 6. Preserve the review result

At the end of the Claude session, copy Claude's final review report into the controlling ChatGPT/AHEAD campaign thread for triage.

Do not let Claude apply repairs during the independent review pass.

The review result should be evaluated against source evidence before any mutation is approved.

## 7. Repair loop

If findings are accepted:

1. classify which findings are real and in scope;
2. define the exact repair boundary;
3. authorize the repair separately;
4. apply the smallest justified changes;
5. rerun targeted tests;
6. rerun broader relevant tests;
7. inspect the final diff;
8. give Claude a fresh read-only verification pass focused on the prior blockers;
9. retain human merge/publication acceptance.

A reviewer finding is evidence to investigate, not automatic authority to edit.

## 8. Useful Claude Code session commands

Inside Claude Code:

- `/permissions` — inspect/manage current tool permissions.
- Exit the session normally when the review is complete.

From the shell afterward, Claude Code can resume the most recent conversation in the current directory with:

```bash
claude --continue
```

A specific saved session can be resumed using Claude Code's `--resume` option.

## 9. Safety rules

- Never use `--dangerously-skip-permissions` for this workflow.
- Never give a review agent broad GitHub write access merely because local read access is inconvenient.
- Never combine independent review and repair authority in the same pass unless a separately approved task explicitly requires it.
- Never treat model confidence as validation evidence.
- Never treat passing tests as sufficient acceptance evidence when the task also requires source review.
- Never claim a public extraction is byte-for-byte identical to private authoritative source unless that identity has actually been proven.

## 10. Why this workflow exists

The AO-AGENT-0014 case demonstrated that an implementation can compile and pass its existing tests while still containing acceptance-blocking defects. The review process therefore separates generation, deterministic validation, adversarial source review, bounded repair, revalidation, and human acceptance.

Claude Code is one review instrument inside that process. It is not the authority that decides what is accepted or published.
