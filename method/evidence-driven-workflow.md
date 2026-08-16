# Evidence-Driven AI-Assisted Workflow

The objective of this workflow is not to minimize human involvement. It is to use AI where it accelerates implementation while preserving enough structure and evidence for a human to decide whether the result deserves acceptance.

## The control loop

1. **Bound the task.** Define the repository and source state, objective, relevant context, read/write scope, allowed and forbidden actions, validation plan, acceptance criteria, stop conditions, and decisions reserved for a human.
2. **Load the smallest sufficient context.** Read current repository sources that actually govern the task. Do not substitute conversational memory for current source state.
3. **Implement inside the boundary.** AI may write code only within the authorized scope. Unexpected source drift or an unanticipated required change is a reason to stop or re-authorize, not silently broaden the task.
4. **Run deterministic validation.** Capture concrete checks such as compilation, targeted tests, broader regression tests, source/base identity, and task-specific validation.
5. **Review independently and adversarially.** Treat passing tests as evidence, not proof. Inspect source behavior, edge cases, malformed input, failure modes, security assumptions, race conditions, and whether tests actually exercise the intended contract.
6. **Repair narrowly.** Correct approved defects without turning review findings into permission for broad redesign.
7. **Revalidate.** Repeat relevant targeted and regression checks after every repair.
8. **Separate recommendation from acceptance.** A worker or reviewing model can recommend acceptance. The human owner decides whether the work is accepted and whether it may be published, merged, deployed, or used as a new source baseline.
9. **Close out with durable evidence.** Leave enough source-backed state for another session to determine what changed, what passed, what remains uncertain, and what authority controls the next action.

## Why green tests are not acceptance

Tests only prove what they actually test. They can be incomplete, encode a mistaken assumption, miss malformed input, fail to model concurrent state changes, or exercise a safe path while a dangerous path remains untested.

The AO-AGENT-0014 case in this repository illustrates this directly. Its first candidate compiled, passed all targeted tests, passed the full repository suite, and passed task/context/workspace validation. Independent source review still found several correctness and hardening defects. After an AI repair and another fully green validation pass, a second source review found one more race involving pathname identity during hashing.

The final acceptance decision therefore depended on **code reading + adversarial reasoning + tests + bounded correction**, not on the test count alone.

## Evidence before narrative

Useful engineering evidence includes:

- exact source/base identity;
- the authorized task boundary;
- changed-file scope;
- deterministic commands and exit results;
- targeted and regression test results;
- raw or reproducible failure evidence where practical;
- review findings tied to specific behavior;
- explicit unresolved uncertainty;
- the human acceptance decision.

A model saying “done,” “safe,” or “all tests pass” is not equivalent to any of those things.

## AI's role

AI is useful in this process for:

- implementation;
- refactoring within a bounded scope;
- generating adversarial test ideas;
- code review;
- debugging hypotheses;
- comparing behavior against a task contract;
- documentation and closeout drafting.

AI does not receive authority merely because it can see a repository or because it produced the previous implementation. Visibility is not permission, and authorship is not acceptance authority.

## Human ownership

The human owner remains responsible for the engineering outcome. In practical terms that means understanding the requested behavior, deciding which review findings matter, authorizing scope changes, deciding when evidence is sufficient, and accepting or rejecting the result.

That human gate is especially important when AI is used heavily: the faster implementation becomes, the more important it is to prevent speed from being confused with correctness.
