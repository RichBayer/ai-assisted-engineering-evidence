# AI-Assisted Engineering: Evidence, Review, and Human Acceptance

AI can produce code quickly. That does not make the code correct, safe, maintainable, or accepted.

This repository shows how I use AI as an engineering accelerator while keeping source evidence, deterministic validation, independent review, bounded correction, and human judgment between generated work and acceptance.

The core loop is:

> bounded task → AI-assisted implementation → deterministic validation → independent adversarial review → bounded repair → revalidation → human review → acceptance → durable closeout

One case in this repository began with green tests and still failed review. That is intentional evidence of the process working. The purpose is not to prove that AI can generate code; it is to make AI-assisted work reviewable enough that incorrect code can be caught before human acceptance.

## Start here

If you are evaluating how I build software, the fastest path is:

1. Read [`method/evidence-driven-workflow.md`](method/evidence-driven-workflow.md) for the operating model.
2. Read [`case-studies/ao-agent-0014/README.md`](case-studies/ao-agent-0014/README.md) for a real implementation/review/hardening case.
3. Review [`case-studies/ao-agent-0014/review/findings.md`](case-studies/ao-agent-0014/review/findings.md) to see why the initial green test result was not enough.
4. Compare the initial and accepted code/test evidence once the standalone extraction is present in this repository.

## What this demonstrates

- **AI-assisted implementation without blind acceptance.** AI can propose and repair code, but validation and review are separate gates.
- **Bounded work.** A task defines source state, read/write scope, allowed actions, tests, stop conditions, and acceptance criteria before implementation begins.
- **Evidence over narrative.** Passing commands, test output, source identity, changed-file scope, and review findings matter more than a model saying the work is complete.
- **Adversarial review.** A different review pass is expected to challenge assumptions, test coverage, edge cases, security boundaries, and failure behavior.
- **Human ownership.** Acceptance, publication, and broader repository changes remain human decisions.
- **Durable continuity.** Repository state and documented evidence are used to resume work instead of relying on conversational memory.

## Method notes

The method summarized here was developed across my private engineering repositories. Some of the underlying governance documents are intentionally private and non-exportable, so this public repository re-expresses the transferable engineering ideas rather than publishing those authorities wholesale.

Several context-management concepts were developed in an upstream private methodology repository I call **Build Ops Doctrine**, while the executable task lifecycle, evidence rules, validation behavior, and case study were developed in **Agent Operations**. Those names are included for provenance; this repository is the public, reviewer-oriented evidence surface.

## AI-use disclosure

I use AI coding tools heavily. I also expect their output to be wrong sometimes.

My responsibility is to understand the requested behavior, constrain the work, inspect the code, run deterministic checks, seek adversarial review, distinguish test success from acceptance, correct remaining defects, and be able to explain what was shipped and why.

The AO-AGENT-0014 case is included because it demonstrates that distinction with real defects and real corrections rather than a hypothetical workflow.

## Repository map

```text
method/
  evidence-driven-workflow.md
  context-and-authority.md
  bounded-task-contracts.md
examples/
  bounded-task-packet.yaml
case-studies/
  ao-agent-0014/
    README.md
    initial/
    review/findings.md
    accepted/
    retrospective.md
```

## Scope and limitations

This repository is a focused engineering-evidence sample, not a claim of enterprise-scale software ownership or a complete reproduction of the private systems behind it. It intentionally excludes private infrastructure, credentials, internal paths, unrelated roadmaps, model-plan details, and non-exportable governance documents.
