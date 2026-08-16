# Bounded Task Contracts

A prompt is not a sufficient engineering task contract.

For AI-assisted work, ambiguity in scope can turn into unintended code changes very quickly. A bounded task packet makes the work inspectable before implementation starts and gives validation/review something concrete to compare against.

## Minimum contract

A useful task contract identifies:

- **repository and source baseline** — where the work belongs and the commit/ref it was prepared against;
- **objective** — the behavior or evidence the task must produce;
- **authoritative sources** — current code/docs that govern the work;
- **read scope** — what may be inspected;
- **write scope** — exact files or bounded paths that may change;
- **protected paths** — areas that must remain untouched;
- **allowed/forbidden actions** — especially mutation, network, shell, deployment, and publication boundaries;
- **validation plan** — deterministic checks expected before review;
- **acceptance criteria** — observable requirements rather than model confidence;
- **stop conditions** — situations that require escalation instead of improvisation;
- **human decisions** — actions the AI cannot authorize for itself;
- **documentation/closeout impact** — what durable state must be updated if the task is accepted.

## Default-deny behavior

The absence of a prohibition should not automatically become permission for broad changes. If a task authorizes edits to two files, discovering that a third file would be convenient to change is a reason to request a boundary change, not to silently expand scope.

This matters because AI systems are often optimized to finish a request. A bounded contract intentionally gives the model another valid outcome: **stop with evidence explaining why the current boundary is insufficient.**

## Separate implementation authority from acceptance authority

The same task can authorize an AI to edit files without authorizing it to:

- commit;
- push;
- open or merge a pull request;
- deploy;
- publish externally;
- alter another repository;
- declare its own work accepted.

Those are separate state transitions and should be authorized separately when risk or provenance matters.

## Review against the contract

A review should ask more than “does the code look good?” It should ask:

- Did the implementation satisfy each acceptance criterion?
- Were all changes inside the authorized scope?
- Did the worker invent semantics not present in the source authorities?
- Are failure modes deterministic and fail-closed where required?
- Do the tests exercise the contract or merely the happy path?
- Is any claimed evidence missing, stale, or based only on worker narrative?

The sanitized example in [`../examples/bounded-task-packet.yaml`](../examples/bounded-task-packet.yaml) demonstrates the shape without exposing private repository details.
