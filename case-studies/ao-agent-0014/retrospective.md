# Retrospective

AO-AGENT-0014 changed how I think about “AI-assisted development” as an engineering claim.

The interesting part was not that an AI could write a Python utility quickly. The interesting part was how much engineering remained after the utility appeared to work.

## What worked

### A bounded task kept review actionable

The task had a narrow purpose and a defined validation boundary. When review found defects, the repair could stay focused on evidence correctness rather than expanding into a redesign of Agent Operations.

### Independent review found things the authoring loop missed

The initial candidate had nine targeted tests and passed the entire repository suite. Review still found conflict-classification, process-environment, race, ignored-file, and fail-open problems.

That reinforced a useful separation: the implementation loop is optimized to make the requested thing work; an adversarial review loop is optimized to find reasons it should not yet be trusted.

### Tests improved as understanding improved

The targeted suite grew from 9 to 33 and then 34 tests because review identified behaviors the original contract/tests had not exercised strongly enough.

I do not view that as “the tests failed.” The tests were evidence of the understanding available at each stage. Review exposed missing understanding, which then became executable regression coverage.

## What did not work

### Green output created a false sense of completion risk

A compile pass, 9/9 targeted tests, 254/254 regression tests, and several validation checks looked strong. If I had treated those numbers as the acceptance decision, I would have accepted incorrect code.

### The first repair still was not the finish line

After the AI repair, 33 targeted tests and 278 repository tests passed. A second source review still found a pathname-binding race.

That is an important failure mode in AI workflows: once a model “fixes the review,” it is tempting to treat the repair as authoritative because it directly answered the findings. It still needs review.

### Shared hardening primitives complicate public evidence

The accepted private implementation correctly reuses shared Agent Operations helpers for trusted executable resolution and sanitized Git execution. That is good internal design, but it means copying only one accepted file into a public repository would create a misleading or broken sample.

The public accepted sample is therefore packaged as a standalone extraction with provenance instead of pretending it is byte-for-byte identical to the private integrated module.

## How I use AI after this case

I use AI aggressively for speed, but I try to keep five questions separate:

1. **Did the model produce code?**
2. **Does the code run?**
3. **Do the current tests pass?**
4. **Does independent review support the intended behavior and boundaries?**
5. **Am I willing to accept and own the result?**

Those questions may all eventually have “yes” answers, but they are not the same question.

## Compute efficiency

This process also changed how I think about AI cost and speed. The objective is not the fewest model calls or the cheapest first draft. It is **quality-adjusted compute for durable accepted code**.

A cheap implementation that creates review churn or ships a hidden defect is not actually cheaper. Conversely, not every task needs the most expensive model. Bounded implementation, targeted review, deterministic validation, and human judgment let model capability be applied where it has the most leverage.

## What I would explain in a code review

For this case I should be able to explain without outsourcing the answer to an AI:

- why Git porcelain uses two-character status states;
- why conflict states have to be classified before ordinary added/deleted membership checks;
- why `-z` matters for path parsing;
- why ignored-directory enumeration affects evidence completeness;
- why a symlink-safe `lstat` is insufficient if a later open follows the pathname;
- why descriptor identity does not prove that the repository pathname still points to that descriptor's object;
- why inherited `PATH` and `GIT_*` state are inappropriate trust inputs for a deterministic evidence primitive;
- why passing tests are evidence but not the acceptance decision.

That explanatory ownership is the standard I want for AI-assisted code I present as my engineering work.
