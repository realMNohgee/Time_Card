# Time_Card
![CI](https://github.com/realMNohgee/Time_Card/actions/workflows/ci.yml/badge.svg) ![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Worklog tracker.** Clock in/out, tag projects, weekly summaries, CSV export.  
Zero dependencies — Python stdlib only.

## Install

```bash
curl -O https://raw.githubusercontent.com/realMNohgee/Time_Card/main/time_card.py
chmod +x time_card.py
./time_card.py --help
```

Or clone:

```bash
git clone git@github.com:realMNohgee/Time_Card.git
cd Time_Card
python3 time_card.py --help
```

## Usage

```
time_card.py in        Clock in (start a new work session)
time_card.py out       Clock out (end current session)
time_card.py status    Show current status
time_card.py today     Show today's sessions
time_card.py week      Weekly summary (Mon–Sun)
time_card.py report    Report for a date range
time_card.py edit      Edit a past session
time_card.py projects  List all projects with total hours
```

### Clock in/out

```bash
time_card.py in --project hermetica --note "building CLI"
# ⏱  Clocked in — 2026-08-11T15:46:33+00:00  (project: hermetica)

time_card.py out --note "done for now"
# ⏹  Clocked out — 2h 15m  (project: hermetica)
```

- `in` auto-closes any previous open session before starting a new one.
- Midnight crossings are handled gracefully — sessions span across dates without issues.

### Status

```bash
time_card.py status
# Clocked in  — 01:23:45
#   Started:   2026-08-11T15:46:33+00:00
#   Project:   hermetica
#   Note:      building CLI
#
# Today's total (incl. running): 1h 23m  (1 session(s))
```

### Today / Week

```bash
time_card.py today                # text (default)
time_card.py today --format json  # JSON output

time_card.py week                 # text (default)
time_card.py week --format json   # JSON with daily breakdown + project totals
```

### Reports

```bash
time_card.py report                                     # all sessions
time_card.py report --format csv                         # CSV output
time_card.py report --format json                        # JSON output
time_card.py report --from 2026-08-01 --to 2026-08-31   # date range
time_card.py report --project hermetica --format csv     # filter by project
```

### Edit

```bash
time_card.py edit <session_id> --project newname --note "updated"
time_card.py edit <session_id> --start 09:00 --end 17:30
```

### Projects

```bash
time_card.py projects
# Project                             Total  Sessions
# -------------------------------------------------------
# hermetica                          12h 30m  5
# default                             3h 15m  2
```

## Data

All sessions are stored in `~/.time_card.jsonl` (one JSON object per line):

```json
{"id": "a3b9c1", "start": "2026-08-11T09:00:00+00:00", "end": "2026-08-11T17:00:00+00:00", "project": "hermetica", "note": "building CLI", "duration_seconds": 28800}
```

## Marketplace

Part of the [Hermtica](https://hermtica.com) marketplace — free, zero-dependency Python tools.

## License

MIT — see [LICENSE](LICENSE).
