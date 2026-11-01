# Security boundary

Only official public market data and a standalone recorder belong here. There are no private models, selections, stakes, trading thresholds, account credentials, historical private datasets, or private-repository access tokens.

- No pull-request or issue-triggered execution. The fixed repository and default branch are checked before execution.
- Use GitHub-hosted disposable runners. Never attach a personal computer or a shared self-hosted runner.
- Only the ephemeral token for this public repository is passed to the data publishing step. No personal access token, cloud key or cross-repository credential is needed.
- The official HTTPS endpoint is fixed; redirects, custom URLs and commands are unsupported. Source responses are untrusted data, parsed into an explicit field allowlist and never executed.
- Only explicit public data paths are staged. Logs do not echo response bodies, request headers or raw exception text. No runner home or environment dump is published.
- Official checkout action is pinned to a commit. The recorder and tests use Python standard library only.
- Public means files, logs and data may be copied indefinitely. No claim of perfect secrecy, uninterrupted execution, or guaranteed zero storage costs is made.

Keep private analytics in a separate private environment that reads public data as data only. Do not download and execute this repository's code inside a privileged private workflow. Validate schema, identifiers, timestamps and pool state before analysis; never backfill a live decision from later data.

The watchdog workflow has read-only repository permission, downloads two public JSON files and the official calendar, and has no write step. The optional stop-sell probe uses the same fixed endpoint and field allowlist and is disabled unless a maintainer starts a manual run with a non-zero value.
