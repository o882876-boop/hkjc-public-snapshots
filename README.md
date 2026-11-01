# Public racing market snapshots

Standalone recorder for official, publicly available ST/HV race schedules and WIN/PLA/QIN/DBL market quotes. This public project contains no prediction model, betting selection, stake, trading threshold, account credentials or private datasets. The source and its public observations can be inspected and copied.

The scheduled workflow uses standard GitHub-hosted runners and a repository-scoped ephemeral token; no Oracle account, personal access token or private repository connection is needed. Official calendar checks determine whether a local meeting is in its collection window. Two sequential bounded jobs cover a meeting. This is a public data project; it is not a hidden runner for executing private code.

`public-data` branch stores `calendar.json`, `session.json`, `heartbeat.json` and `market/YYYY-MM-DD_VENUE/race_XX_YYYYMMDDTHH.jsonl.gz` (bounded per-race/hour append archives). Capture and record times, official quote publication times, pool/leg identities, selling state and the source payload SHA are retained. The recorder runs from 90 minutes before each scheduled race through preoff; closed or missing quotes remain marked, not fabricated. It does not calculate strategy scores or certify that any quote was usable at a private decision cutoff.

Run the **Public market recorder** workflow manually or allow its schedule to run. No local computer needs to stay on. Missing source data, delayed schedules and runner interruptions remain possible. Heartbeat freshness is persisted every 15 seconds during long workers, subject to Git/network delays. Calendar-only checks run on nonrace days; no long worker starts then. Existing completed meetings do not restart.

No raw HTML, personal data, private repo files, models or ledgers are copied into this repository. No code/data licence from the upstream source is implied. Keep use within source permissions and GitHub platform limits. Public standard runner compute currently has no private-runner minute quota, but storage and service limits still apply; this does not guarantee an unlimited free service.

Private analysis must independently validate schema and timestamps, record its actual receipt/decision time, and reject data arriving after a live cutoff. Replaying recorded snapshots later is a separate retrospective evaluation, not an already-placed live paper decision. Keeping analysis private may still consume private compute.

Local verification: `python -m unittest discover -p 'test_*.py' -v`. Tests use isolated fixtures, never production observation files. See SECURITY.md for the security boundary.

Private consumers can read bounded `race_XX_opening_samples.json` (5-minute samples, at most24), `race_XX_latest.json`, and `race_XX_preoff_samples.json` (last12 captures). Indexes contain only the same public observations with original timestamps and source run/commit, no trading logic. Compressed hourly archives avoid a single growing meeting file exceeding hosting limits. These indexes are transport conveniences, not predeclared private decisions.

## Monitoring additions (proposed)

- Each recorded book carries `win_summary`: declared/active runner counts, WIN node and valid-quote counts, the inverse-quote sum over active runners, `complete`, explicit `missing_reasons` and informational markers (for example `scratched_runner_marker:SCR`). It is a descriptive observation, not a threshold or model.
- **Public recorder watchdog** (`watchdog.yml`) is read-only. It reads only `heartbeat.json` and `session.json` from `public-data`, checks the official calendar, and fails visibly when an ST/HV meeting is inside its collection window but the recorder has not started or its heartbeat is older than 5 minutes. It never writes data and never starts or restarts the recorder.
- **Stop-sell probe (test only, off by default).** A manual run of the recorder may set `stop_sell_probe_minutes` (max 10). After each scheduled post it polls only the WIN pool until it is first seen not selling, writing `poolstate_race_XX_*.jsonl.gz` and `race_XX_pool_state.json`. `first_not_selling_seen_at` is the first poll that saw the pool closed; it is an upper bound limited by poll spacing and is **not the actual race off time**. Probe output never enters `race_XX_latest.json`, `opening_samples` or `preoff_samples`. Scheduled runs always use 0.
