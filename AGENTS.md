## TL;DR

You are a Marsh contributor. Work from the existing contracts and tests, and preserve Python 3.10–3.12, public semantics, and the dependency-light core. Do not turn future roadmap ideas into implementation requirements.

This document covers installation, development workflows, code standards, review requirements, and project boundaries.

## Installation

Install `uv`, then sync the locked dependencies:

```bash
python -m pip install uv
uv sync --all-groups
# Optional provider dependencies:
uv sync --all-groups --extra docker --extra ssh
```

Use the repository's `uv.lock`; do not replace dependency resolution with ad-hoc installs.

## Development & contribution

Follow this workflow for every contribution:

1. Start from an up-to-date `develop`; inspect code, tests, docs, and relevant contracts before editing.
2. Use a short-lived `feature/*` or `fix/*` branch; target pull requests (PRs) at `develop`.
3. For behavior changes: RED → GREEN → REFACTOR.
4. Keep scope limited to the issue/specification. Update tests and docs with behavior changes.
5. Do not develop routinely on `main`; it is the stable/release branch.

## Planning & approval

Before starting a long-running or multi-stage task, show the action plan, intended changes, and other details. Ask for review and permission before executing.

## Git

Inspect state and create a focused branch with:

```bash
git status
git switch develop
git pull --ff-only
git switch -c feature/<short-description>   # or fix/<short-description>
git diff --check
git diff
git log --oneline -10
```

Use Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `release:`.

Never:

- commit secrets, credentials, private data, local environments, or build artifacts;
- create or modify GitHub labels;
- force-push to protected branches.

Before every `git commit`, run the Security review checklist below and ask for explicit permission. Commit only after permission is granted.

## GitHub CLI (`gh`)

GitHub's command-line interface (CLI) is `gh`. Use it for GitHub-native operations such as Issues, Pull Requests, Releases, and Actions. Prefer read-only commands for inspection, and use `--repo`, `--json`, and `--jq` when they make the target or output deterministic.

Before any remote mutation through `gh`:

1. Confirm the target repository, branch/ref, and intended mutation.
2. Perform the required security checks.
3. Ask for explicit permission when the operation requires approval.
4. Perform the mutation only after approval.
5. Re-read the resulting GitHub state and verify that it matches the intended result.

For long or multiline Issue, Pull Request, comment, or review bodies, prefer `--body-file` over shell-escaped inline strings.

Use `gh pr checks` to inspect continuous integration (CI) status and verify required checks before considering a Pull Request ready.

Verify the intended base and head branches before creating a Pull Request. Avoid creating duplicate Pull Requests when an existing one can be updated.

Prefer high-level `gh` commands over `gh api` when the required operation is already supported by the CLI. Use `gh api` only when the higher-level command does not provide the required capability.

Never place secrets, credentials, or tokens in command arguments, source files, logs, or published GitHub content. Do not run authentication or credential-management commands unless they are explicitly required.

Do not merge Pull Requests unless explicitly authorized.

## uv

Run tools in the locked project environment with `uv run <command>`. After dependency changes, run `uv sync --all-groups`. Use `uv build` for package builds.

Add provider dependencies as optional extras. Do not add backend dependencies to core `project.dependencies`.

## Python

Support Python 3.10–3.12. Apply these rules:

- Follow PEP 8 and type clearly.
- Use small, cohesive functions and classes with explicit interfaces.
- Prefer composition over inheritance.
- Use standard-library solutions when sufficient.
- Preserve structured Result, error, and lifecycle semantics.
- Never equate non-empty stderr with failure.

## Formatting, linting & tests

Configure Black for line length 88 and pflake8 for 120; use isort.

```bash
uv run isort src tests
uv run black src tests
uv run pflake8
uv run pytest -vv --disable-warnings --tb=short
```

Run the smallest relevant test first, then the relevant broader suite. Integration tests use Docker/SSH and the `integration` pytest marker where applicable. CI tests Python 3.10/3.11/3.12 and runs build, lint, Docker, and SSH integration checks.

## GitHub Issue workflow

Create an Issue for actionable work. State:

- objective
- scope/non-goals
- acceptance criteria
- architecture impact
- dependencies
- tests
- docs
- compatibility/security impact
- release scope

Treat an Issue as a goal, not a guarantee.

## Pull Request workflow

Open PRs against `develop`. Include:

- problem
- intended behavior
- linked Issue
- architecture/design impact
- compatibility impact
- tests
- docs
- verification evidence

Review for:

- scope drift
- unnecessary abstractions
- duplicate execution semantics
- dependency leakage
- backend conditionals
- application programming interface (API) breaks
- missing tests/docs

## Feature workflow

The full path from issue to merge:

```text
Issue → Scope Check → Architecture Check → Branch → Tests → Implement → Docs → Local Verify → PR → CI → Review → develop
```

Reuse these existing seams before adding new abstractions:

- Workflow, Task, Machine, Process, Result, and Scheduler
- Provider, Adapter, Policy, and Observer
- Capability, configuration, and extension seams

## Fix / debugging workflow

Use this sequence when fixing a bug:

```text
Reproduce → failing regression test → inspect root cause → smallest fix → targeted test → broader regression suite → verify → document
```

Do not weaken a test to make it pass. Preserve `UNKNOWN`/`AMBIGUOUS` when evidence is insufficient. Report every check you ran and every check you skipped.

## CI/CD

CircleCI is the required baseline verification path: build, pflake8, Python 3.10/3.11/3.12 tests, Docker integration, and SSH integration. Match local commands to CI where practical. Do not claim completion without inspecting actual results. Release automation must validate before publishing and use least-privilege credentials/permissions.

## Release management

Use Semantic Versioning and tags `vMAJOR.MINOR.PATCH`.

```bash
uv build
git diff --check
git tag vX.Y.Z
git show vX.Y.Z
```

Release only verified artifacts from `main`. Validate metadata, wheel/sdist installation and smoke behavior, tests, artifact integrity, release notes, and publication results. Treat published versions as immutable. Do not infer a release from a tag alone.

## Documentation

Treat docs as part of the public contract. Update README, concepts, reference, how-to, architecture, or contribution docs when public behavior changes. Use version-free headings where the documentation convention requires them. Do not document speculative behavior as implemented.

Write concise docstrings and comments. Explain why the code exists, not what it does, and keep them next to the code they describe.

## Code review

Review:

- behavior and API compatibility
- tests and lifecycle/error semantics
- architecture boundaries and dependency impact
- security, documentation, and scope

Reject unnecessary abstractions, duplicate engines, provider leakage, and unverified claims.

Require architecture review when any of these change:

- Workflow intermediate representation (IR)
- core contracts
- public APIs
- provider/plugin/adapter/policy contracts
- lifecycle
- serialization
- reproducibility
- dependency strategy
- security boundaries

## Security review checklist

Before merge/release, check:

- no secrets/credentials/private data in code, tests, logs, artifacts, or Git history;
- untrusted command values use structured arguments rather than unsafe shell interpolation;
- remote execution, providers, subprocesses, artifacts, dependencies, CI, and publishing trust boundaries are explicit;
- CI uses least privilege;
- sensitive values are redacted and not logged by default;
- optional integrations cannot silently contaminate core dependencies;
- package/release artifacts are validated before publication.

## Boundaries

- **Allowed**: modify implementation, tests, docs, issues, PRs, and release milestones within Marsh; use existing extension points; use optional provider dependencies.
- **Permission required**: change approved architecture/design, roadmap/plan scope, public contracts, release intent, or project governance; make destructive or risky operations outside the normal workflow.
- **Denied**: create or modify GitHub labels; commit secrets; bypass branch protection; force-push protected branches; add a second workflow, runtime, or orchestration engine; put provider-specific dependencies or semantics into core; implement speculative roadmap infrastructure without approval.

## Programming practices

Apply these practices:

- Unix composition, progressive disclosure, and integration over reinvention.
- SOLID (single responsibility, open/closed, Liskov substitution, interface segregation, dependency inversion).
- DRY (don't repeat yourself), KISS (keep it short and simple), and YAGNI (you aren't gonna need it).
- Mechanism/policy separation, and reification where it enables validation, inspection, or provenance.
- Explicit contracts, testability, portability, and optionality.

Keep assumptions separate from requirements.

## Architecture & design

Preserve:

```text
UX Adapter → Configuration → Workflow IR → Runtime → Task → Machine → Process → Result
Providers + Policies + Observers + Cache + Artifacts remain orthogonal.
```

Workflow describes intent; providers implement mechanisms; adapters translate external systems; policies define configurable behavior. Machine is an environment; Process is an execution instance. Do not create a provider-specific Workflow IR or second execution engine.

Reify work when it enables:

- validation
- serialization
- planning
- inspection
- reproducibility
- caching
- visualization
- provenance

## Plugins, providers & adapters

Use `Provider` to supply/implement a capability, `Plugin` to extend Marsh, `Adapter` to translate an external mechanism into Marsh contracts, and `Policy` for mechanism-independent behavior. Use the `marsh.extensions` entry-point group for third-party extensions. Providers may own optional dependencies and infrastructure-specific configuration; core must depend only on stable contracts. Extensions should not require core changes.

## Completion checklist

Before claiming work complete:

```bash
uv run pflake8
uv run pytest -vv --disable-warnings --tb=short
uv build
git diff --check
```

Then inspect the results, confirm tests/docs/CI/review requirements, and state any unverified limitation.
