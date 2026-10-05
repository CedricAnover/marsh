# P0 Repository Audit — Marsh

Date: 2026-10-03
Phase: P0 — Repository audit, baseline, and scope lock
Base branch: develop
Base commit: f68201a256f2a9ecac4b6335b688005911b1951c

## 1. Repository snapshot

- Repository: CedricAnover/marsh
- Default branch: main
- Integration branch: develop (confirmed present)
- develop is currently unprotected and has no required status checks.
- Latest develop commit is a verified merge of PR #46 (Node.from_cmd_runners).
- Packaging backend: Hatchling.
- Package layout: src/marsh.
- Dependency manager: uv; uv.lock is committed.
- Python requirement: >=3.10,<3.13 (3.10–3.12).
- OS classifiers: Windows and POSIX/Linux.
- Runtime dependencies currently include Fabric and Docker.
- Development/test dependencies include flake8, isort, black, pytest, pytest-mock, and testcontainers.

## 2. Current architecture inventory

### Core
The current core contains:
- Conveyor and CmdRunnerSpec for command composition.
- CommandGrammar/PyCommandGrammar.
- Connector/Authenticator.
- Script and Expression utilities.
- CmdRunDecorator plus processor/modifier functions.
- Executor hierarchy including LocalCommandExecutor, RemoteCommandExecutor, PythonExecutor, and PyInterpreterExecutor.

### DAG
The current DAG package contains:
- Startable
- Node
- Dag
- SyncDag
- AsyncDag
- ThreadDag
- ThreadPoolDag
- MultiprocessDag
- ProcessPoolDag

Node wraps Conveyor; Dag owns a dependency graph using graphlib.TopologicalSorter.

### Providers/integrations
Execution mechanisms currently include local subprocess execution, SSH/Fabric integration, Docker integration, and Python execution. These are exposed directly through the existing library surface rather than a provider-independent Workflow IR/runtime.

## 3. Tests and examples

Tests are organized by:
- core
- dag
- bash
- docker
- ssh
- utils
- root-level processor tests

Samples cover Bash, decorators, expressions, DAGs, Docker, Python interpreter execution, and SSH.

The repository already has substantial behavior coverage, but there is no evidence yet of a canonical Workflow IR, provider registry/capability protocol, structured Result model, or a unified lifecycle/event model.

## 4. CI/CD baseline

GitHub Actions currently contains:
- .github/workflows/test.yml
- .github/workflows/release.yml
- .github/workflows/pypi-publish.yml

test.yml currently:
- runs on every push and on pull requests targeting main;
- uses ubuntu-latest;
- installs Python 3.10 through setup-uv;
- runs uv sync --all-groups;
- runs pytest with SSH connector/factory and Docker suites excluded;
- publishes PR coverage through orgoro/coverage.

There is no CircleCI configuration in the repository.

The current workflow therefore does not yet implement the approved tiered CI strategy or the declared Python/platform matrix. Expensive Docker/SSH tests are explicitly excluded from the primary GitHub Actions path.

## 5. Baseline command set

Repository-defined local commands:
- `uv run pytest -vv --disable-warnings --tb=short` with SSH/Docker exclusions for the normal test task.
- `uv run pflake8` for linting.
- `uv build --wheel --out-dir dist -v` for packaging.
- `task test-act` for local GitHub Actions emulation with act/Docker.
- `task test-sysbox` for Docker/SSH suites where Sysbox is available.

Authoritative CI baseline command is the command in .github/workflows/test.yml.

## 6. Architecture gap matrix

| Area | Current state | Target P0/P1 direction | Risk |
|---|---|---|---|
| Workflow representation | DAG + Conveyor objects | Explicit, syntax-independent Workflow IR | High |
| Task model | Implicitly represented by Node/Conveyor | Explicit Task contract | High |
| Machine model | Backend-specific execution mechanisms | Machine abstraction | High |
| Process model | Executor.run and Startable.start | Explicit ProcessSpec/Process lifecycle | High |
| Results | Mostly (stdout, stderr) tuples | Structured Result semantics | High |
| Scheduling | Multiple DAG implementations | One Scheduler contract with strategies | High |
| Providers | Direct integrations | Provider/capability contracts | High |
| Policies | Scattered parameters | Explicit mechanism-independent policies | Medium |
| Observability | Logger/decorators | Orthogonal Observer/event protocol | Medium |
| Caching | No canonical cache identity | Explicit/opt-in cache | Medium |
| Configuration | Python/object APIs | Validated configuration boundary | High |
| Compatibility | Existing API is established | Preserve through adapters/deprecation | High |

## 7. Compatibility map

Existing public behavior that must be protected during evolution:
- `Conveyor` construction and callable execution.
- `CmdRunnerSpec` and `Conveyor.from_specs`.
- `Node.from_cmd_runners`.
- Existing command runner decorators/processors/modifiers.
- Existing local, SSH, Docker, and Python execution entry points.
- Existing DAG class names and start() behavior unless an explicitly approved compatibility migration is introduced.

No public-interface rewrite is justified by P0 alone.

## 8. Support matrix proposal

Evidence-based current package contract:
- Python 3.10: required support.
- Python 3.11: required support.
- Python 3.12: required support.
- Python 3.13: not currently supported by project metadata; do not add to required support without an explicit decision.
- Linux: required representative platform.
- Windows: declared platform and should receive representative compatibility validation.
- macOS: not declared by current project classifiers; defer required support until repository/project requirements establish it.

CI should avoid a full Cartesian matrix. Required coverage should be risk-based:
1. Linux × Python 3.10/3.11/3.12 for compatibility.
2. Representative Windows coverage for native-platform behavior.
3. Linux integration jobs for Docker/network/provider behavior.
4. Scheduled/deep coverage through GitHub Actions and, where useful, CircleCI supplementary capacity.

## 9. CI/resource assessment

GitHub Actions remains the primary CI gate. CircleCI is not currently configured and should be introduced only as supplementary capacity.

The repository already separates expensive Docker/SSH tests from the fast path. This is consistent with the approved resource-aware direction, but the CI architecture should be normalized around reusable commands and explicit tiers rather than ad-hoc exclusions.

The free-tier constraint reinforces:
- short deterministic PR jobs;
- dependency caching;
- targeted matrices;
- scheduled/release deep suites;
- CircleCI overflow/deep capacity without divergent test semantics.

## 10. Scope lock

P0 establishes the following implementation sequence:
1. Protect current behavior with compatibility/contract tests before public interface changes.
2. Define minimal domain contracts.
3. Introduce the canonical Workflow IR and configuration boundary.
4. Build planning + sequential local execution as the first vertical slice.
5. Add provider/capability and lifecycle contracts.
6. Add observability and opt-in caching.
7. Polish UX adapters and release hardening.

P0 does not authorize:
- a rewrite of the existing library;
- mandatory Docker/SSH dependencies in the core;
- a distributed scheduler;
- a second execution engine;
- YAML/JSON as a first-release requirement without explicit approval;
- a new non-local provider without a concrete use case and test environment.

## 11. Baseline verification

The branch will use the repository's existing GitHub Actions test workflow as the reproducible CI baseline. The workflow result for this P0 branch is recorded in the final revision of this document after GitHub Actions completes.

## 12. P0 acceptance

- Repository/source/test/package/CI inventory: complete.
- Compatibility risks and protected public surface: documented.
- Python/platform support proposal: documented from repository evidence.
- CI/CD resource strategy: reconciled with current workflows.
- First-release scope and implementation sequence: locked.
- No public interfaces changed by P0 audit.
