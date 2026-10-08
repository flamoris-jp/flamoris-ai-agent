# Progress

## Updater adoption — 2026-10-08

Entry release target: **1.0.0**. Independent mTLS Owner and durable admission
source are implemented; source review/fixes and CI integration are complete.
PR [#45](https://github.com/flamoris-jp/flamoris-ai-agent/pull/45) is prepared for human
review. Release publication and real-host adoption remain pending.

## Verification

Local full suite: **175 passed, 34 database tests skipped locally**. All seven application wheel-from-sdist builds and
declared Owner entrypoint/module checks passed. The operator made Updater public,
resolving the initial SDK download 404. That adoption checkpoint used SDK source
pinned to
`d9f010a92ff6e8a1e7a3b7fad8817850bdfb72cd` (Updater PR #6).

[CI run 37768251469](https://github.com/flamoris-jp/flamoris-ai-agent/actions/runs/37768251469):
209 passed against disposable PostgreSQL 16; test and container jobs succeeded. The container builds the separate Intelligence source wheel with --no-deps and checks the installed dependency graph with pip check.
These results precede this progress-only commit; package/source dependency pins
are unchanged. Cross-repository findings and exact evidence are recorded in
Updater [ADOPTION_REVIEW.md](https://github.com/flamoris-jp/flamoris-updater/blob/feat/application-entry-v1/docs/ADOPTION_REVIEW.md).

## Operational boundary

The entry path preserves already current application schemas and retained data;
unsupported schemas/resources and unknown outcomes remain blocked. No data/schema
initialization, private profile/trust provisioning, release publication, live
provider call, real-host update, enrollment or automatic merge occurred. Native
deployment overlays and matched dependencies remain deployment-owned.
See [Updater contract](docs/UPDATER.md).

## Pre-deployment dependency refresh

The SDK now targets merged Updater revision
`d5ec3408d2a9b43ce44efef6ab8209a6b8ffad25`, and Intelligence targets merged
dependency refresh `274fc9196036a937f7059caac861ada2346d09e7`. Review and CI at
these exact revisions are pending. No runtime, release, data or host state was
changed.
