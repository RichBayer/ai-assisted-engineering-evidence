# Context and Authority

AI-assisted engineering becomes fragile when a model treats whatever it remembers as current truth or treats repository visibility as permission to act.

This method separates **context**, **authority**, and **current state**.

## Repository state outranks conversational memory

A new session should recover from current sources, not from a model's recollection of a prior conversation. The practical rule is simple:

- identify the repository and source baseline;
- load the current documents and code that govern the task;
- verify source freshness before acting;
- treat remembered conclusions as hypotheses until current sources support them.

This is how long-running AI-assisted work remains resumable without requiring one permanent chat thread.

## Load the smallest sufficient context

More context is not automatically better. A useful context set contains the sources required to understand the current task, its constraints, and its dependencies without flooding the model with unrelated repository history.

Typical context profiles include startup/resume, task preparation, implementation, review, closeout, and cross-repository work. A profile is a navigation aid, not an authority grant.

## Stable document identity

Long-lived documentation benefits from stable identifiers and lightweight metadata. A stable ID can survive a file move while still identifying the same authority or concept. Metadata can describe lifecycle state, context role, dependencies, and review/export properties.

This makes repository context addressable instead of depending entirely on remembered paths.

## Visibility does not equal write authority

A model may need to read broadly to understand a system while being authorized to write only one or two files. Cross-repository visibility is especially useful for understanding interfaces and upstream doctrine, but it must not silently become cross-repository mutation authority.

A useful rule from the private Build Ops Doctrine work is:

> Read broadly. Write narrowly. Cite clearly. Close out locally. Ask before crossing repository boundaries.

## Source drift fails closed

A bounded task is prepared against a known source state. If the source changes materially before implementation or review, the safe response is to reconcile the new state before continuing. This prevents a valid plan for one baseline from being applied blindly to another.

## Cross-repository ownership

Different repositories may own different kinds of truth. In the private system behind this public example:

- Build Ops Doctrine owns upstream methodology and context-routing concepts;
- Agent Operations owns executable task orchestration, lifecycle, evidence, and review rules;
- each target repository owns its own implementation state and project-specific authority.

The important transferable idea is not the repository names. It is that a higher-level orchestration system should not overwrite the authority of the project it is helping to modify.
