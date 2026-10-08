# Progress

## Updater adoption — 2026-10-08

Entry release target: 1.0.0. Source adds durable admission and an independent
mTLS Owner with application-owned schema/resource inspection. Review/testing
and matched dependency wiring are in progress. No release or live update is
claimed. See [Updater contract](docs/UPDATER.md).


## Updater entry review checkpoint

Independent Owner and durable admission are implemented; existing application
state and unresolved work remain protected. Local complete suite: **175 passed, 34 skipped**.
Ruff check/format passed. SDK pinned to
d9f010a92ff6e8a1e7a3b7fad8817850bdfb72cd (Updater PR #6); owning
Controller/Intelligence dependencies are pinned to their matched adoption commits.
Final application CI remains under review. No release, trust/profile provisioning,
provider call, enrollment or real-host change has been performed.


### Public SDK and container review correction

The operator changed Updater to public. Re-run CI resolves the pinned SDK and
passes Agent tests, including real disposable PostgreSQL and installed-wheel
smoke. Container CI caught two cryptography versions in the wheelhouse because
the separate Intelligence wheel build also resolved unconstrained dependencies.
Build that source wheel with --no-deps, then resolve all runtime dependencies
from the existing fixed snapshot in one step. Runtime pip check verifies the
installed dependency graph. Container re-verification is pending.
