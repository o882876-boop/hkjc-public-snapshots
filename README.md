# Public racing market snapshots

Standalone recorder for official, publicly available ST/HV race schedules and WIN/PLA/QIN/DBL market quotes. This public project contains no prediction model, betting selection, stake, trading threshold, account credentials or private datasets. The source and its public observations can be inspected and copied.

The scheduled workflow uses standard GitHub-hosted runners and a repository-scoped ephemeral token; no Oracle account, personal access token or private repository connection is needed. Official calendar checks determine whether a local meeting is in its collection window. Two sequential bounded jobs cover a meeting. This is a public data project; it is not a hidden runner for executing private code.

`public-data` branch stores `calendar.json`, `session.json`, `heartbeat.json` and `market/YYYY-MM-DD_VENUE/records.jsonl`. Capture and record times, official quote publication times, pool/leg identities, selling state and the source payload SHA are retained. The recorder runs from 90 minutes before each scheduled race through preoff; closed or missing quotes remain marked, not fabricated. It does not calculate strategy scores or certify that any quote was usable at a private decision cutoff.

Run the **Public market recorder** workflow manually or allow its schedule to run. No local computer needs to stay on. Missing source data, delayed schedules and runner interruptions remain possible. Heartbeat freshness is persisted every 15 seconds during long workers, subject to Git/network delays. Calendar-only checks run on nonrace days; no long worker starts then. Existing completed meetings do not restart.

No raw HTML, personal data, private repo files, models or ledgers are copied into this repository. No code/data licence from the upstream source is implied. Keep use within source permissions and GitHub platform limits. Public standard runner compute currently has no private-runner minute quota, but storage and service limits still apply; this does not guarantee an unlimited free service.

Private analysis must independently validate schema and timestamps, record its actual receipt/decision time, and reject data arriving after a live cutoff. Replaying recorded snapshots later is a separate retrospective evaluation, not an already-placed live paper decision. Keeping analysis private may still consume private compute.

Local verification: `python -m unittest discover -p 'test_*.py' -v`. Tests use isolated fixtures, never production observation files. See SECURITY.md for the security boundary.
