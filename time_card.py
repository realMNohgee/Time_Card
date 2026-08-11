#!/usr/bin/env python3
"""Time_Card — Worklog tracker. Clock in/out, tag projects, weekly summaries,
CSV export. Zero dependencies (Python stdlib only).

Data stored in ~/.time_card.jsonl (JSONL, one JSON object per line).
"""

import argparse
import csv
import json
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data file
# ---------------------------------------------------------------------------
DATA_FILE = Path.home() / ".time_card.jsonl"


def _ensure_data_dir() -> None:
    """Create the parent directory for the data file if it does not exist."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_sessions() -> List[Dict[str, Any]]:
    """Return every session as a list of dicts (sorted by start ascending)."""
    if not DATA_FILE.exists():
        return []
    sessions: List[Dict[str, Any]] = []
    with open(DATA_FILE, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                sessions.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # silently skip malformed lines
    sessions.sort(key=lambda s: s.get("start", ""))
    return sessions


def _append_session(session: Dict[str, Any]) -> None:
    """Append one session object as a JSON line to the data file."""
    _ensure_data_dir()
    with open(DATA_FILE, "a") as fh:
        fh.write(json.dumps(session) + "\n")


def _write_sessions(sessions: List[Dict[str, Any]]) -> None:
    """Overwrite the data file with a list of session dicts."""
    _ensure_data_dir()
    with open(DATA_FILE, "w") as fh:
        for s in sessions:
            fh.write(json.dumps(s) + "\n")


def _open_session() -> Optional[Dict[str, Any]]:
    """Return the session dict that is currently open (end is None), or None."""
    sessions = _read_sessions()
    for s in reversed(sessions):
        if s.get("end") is None:
            return s
    return None


def _close_open_session(note: Optional[str] = None) -> None:
    """If there is an open session, close it now."""
    sessions = _read_sessions()
    found = False
    for s in sessions:
        if s.get("end") is None:
            now = datetime.now(timezone.utc)
            s["end"] = now.isoformat()
            start_dt = datetime.fromisoformat(s["start"])
            s["duration_seconds"] = int((now - start_dt).total_seconds())
            if note:
                s["note"] = note
            found = True
            break
    if found:
        _write_sessions(sessions)


def _calc_duration_seconds(start_iso: str, end_iso: str) -> int:
    return int((datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)).total_seconds())


# ---------------------------------------------------------------------------
# Helpers for display
# ---------------------------------------------------------------------------
def _format_duration(seconds: int) -> str:
    """Format duration seconds as Hh Mm or Xh Ym."""
    if seconds < 0:
        seconds = 0
    h, remainder = divmod(seconds, 3600)
    m = remainder // 60
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    elif h > 0:
        return f"{h}h"
    else:
        return f"{m}m"


def _format_elapsed(seconds: int) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    s = max(seconds, 0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _parse_date_arg(raw: Optional[str]) -> Optional[date]:
    if raw is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Unrecognised date: {raw!r}")


def _parse_time_arg(raw: Optional[str]) -> Optional[str]:
    """Normalise a time string to HH:MM (24-h).  Returns None if raw is None."""
    if raw is None:
        return None
    raw = raw.strip()
    # Accept HH:MM, H:MM, HHMM
    m = re.match(r"^(\d{1,2}):?(\d{2})$", raw)
    if not m:
        raise argparse.ArgumentTypeError(f"Invalid time: {raw!r}. Use HH:MM or HHMM.")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise argparse.ArgumentTypeError(f"Invalid time: {raw!r}")
    return f"{h:02d}:{mi:02d}"


def _session_date(s: Dict[str, Any]) -> date:
    return datetime.fromisoformat(s["start"]).date()


def _sessions_in_range(
    sessions: List[Dict[str, Any]],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in sessions:
        st = datetime.fromisoformat(s["start"])
        if from_dt and st < from_dt:
            continue
        if to_dt and st > to_dt:
            continue
        out.append(s)
    return out


def _sessions_for_day(sessions: List[Dict[str, Any]], d: date) -> List[Dict[str, Any]]:
    start_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    return _sessions_in_range(sessions, start_dt, end_dt)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------
def cmd_in(args: argparse.Namespace) -> None:
    """Clock in — auto-clocks out any previous open session."""
    _close_open_session(note=args.note)

    session: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "start": datetime.now(timezone.utc).isoformat(),
        "end": None,
        "project": args.project or "default",
        "note": args.note or "",
        "duration_seconds": 0,
    }
    _append_session(session)
    print(f"\u23f1  Clocked in \u2014 {session['start']}  (project: {session['project']})")


def cmd_out(args: argparse.Namespace) -> None:
    """Clock out."""
    sessions = _read_sessions()
    open_s: Optional[Dict[str, Any]] = None
    for s in sessions:
        if s.get("end") is None:
            open_s = s
            break
    if open_s is None:
        print("Not clocked in.")
        return

    now = datetime.now(timezone.utc)
    open_s["end"] = now.isoformat()
    open_s["duration_seconds"] = _calc_duration_seconds(open_s["start"], open_s["end"])
    if args.note:
        open_s["note"] = args.note

    _write_sessions(sessions)
    dur = _format_duration(open_s["duration_seconds"])
    print(f"\u23f9  Clocked out \u2014 {dur}  (project: {open_s.get('project', 'default')})")


def cmd_status(_args: argparse.Namespace) -> None:
    """Show current status."""
    open_s = _open_session()
    if open_s is None:
        print("Not clocked in.")
        sessions = _read_sessions()
        today_sessions = _sessions_for_day(sessions, date.today())
        if today_sessions:
            total_secs = sum(s.get("duration_seconds", 0) for s in today_sessions)
            print(f"Today's total: {_format_duration(total_secs)}  ({len(today_sessions)} session(s))")
        return

    elapsed = _calc_duration_seconds(open_s["start"], datetime.now(timezone.utc).isoformat())
    print(f"Clocked in  \u2014 {_format_elapsed(elapsed)}")
    print(f"  Started:   {open_s['start']}")
    print(f"  Project:   {open_s.get('project', 'default')}")
    if open_s.get("note"):
        print(f"  Note:      {open_s['note']}")

    sessions = _read_sessions()
    today_sessions = _sessions_for_day(sessions, date.today())
    total_secs = sum(s.get("duration_seconds", 0) for s in today_sessions if s.get("end") is not None)
    total_secs += elapsed
    print(f"\nToday's total (incl. running): {_format_duration(total_secs)}  ({len(today_sessions)} session(s))")


def _cmd_today_text(sessions: List[Dict[str, Any]]) -> str:
    if not sessions:
        return "No sessions for today."
    lines: List[str] = []
    total = 0
    EM_DASH = "\u2014"
    ARROW = "\u2192"
    for s in sessions:
        dur = s.get("duration_seconds", 0)
        total += dur
        end_str = s["end"] if s.get("end") else "running"
        lines.append(
            f"  {s['start']}  {ARROW}  {end_str}  "
            f"({_format_duration(dur)})  [{s.get('project', 'default')}]"
            f"{'  ' + EM_DASH + ' ' + s['note'] if s.get('note') else ''}"
        )
    lines.append(f"Total: {_format_duration(total)}  ({len(sessions)} session(s))")
    return "\n".join(lines)


def cmd_today(args: argparse.Namespace) -> None:
    """Show today's sessions."""
    sessions = _read_sessions()
    today_sessions = _sessions_for_day(sessions, date.today())

    if args.format == "json":
        out = []
        for s in today_sessions:
            out.append(
                {
                    "id": s.get("id"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "project": s.get("project", "default"),
                    "note": s.get("note", ""),
                    "duration_seconds": s.get("duration_seconds", 0),
                }
            )
        print(json.dumps(out, indent=2))
        return

    print(_cmd_today_text(today_sessions))


def cmd_week(args: argparse.Namespace) -> None:
    """Weekly summary."""
    sessions = _read_sessions()
    today = date.today()
    # Monday \u2192 Sunday
    monday = today - timedelta(days=today.weekday())
    start_dt = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=7)

    week_sessions = _sessions_in_range(sessions, start_dt, end_dt)
    daily: Dict[date, List[Dict[str, Any]]] = {}
    for s in week_sessions:
        d = _session_date(s)
        daily.setdefault(d, []).append(s)

    if args.format == "json":
        out: Dict[str, Any] = {"week_start": monday.isoformat(), "days": {}}
        total_week = 0
        for d in sorted(daily):
            day_total = sum(s.get("duration_seconds", 0) for s in daily[d])
            total_week += day_total
            proj: Dict[str, int] = {}
            for s in daily[d]:
                p = s.get("project", "default")
                proj[p] = proj.get(p, 0) + s.get("duration_seconds", 0)
            out["days"][d.isoformat()] = {
                "total_seconds": day_total,
                "total_formatted": _format_duration(day_total),
                "project_breakdown": {k: _format_duration(v) for k, v in proj.items()},
                "session_count": len(daily[d]),
            }
        out["week_total_seconds"] = total_week
        out["week_total_formatted"] = _format_duration(total_week)
        print(json.dumps(out, indent=2))
        return

    # Text
    if not week_sessions:
        print(f"No sessions for week starting {monday.isoformat()}.")
        return

    print(f"Week of {monday.isoformat()}  (Mon\u2013Sun)")
    print("-" * 50)
    total_week = 0
    for d in sorted(daily):
        day_name = d.strftime("%a %m/%d")
        day_total = sum(s.get("duration_seconds", 0) for s in daily[d])
        total_week += day_total
        print(f"\n{day_name}  \u2014  {_format_duration(day_total)}  ({len(daily[d])} sessions)")
        proj: Dict[str, int] = {}
        for s in daily[d]:
            p = s.get("project", "default")
            proj[p] = proj.get(p, 0) + s.get("duration_seconds", 0)
        for p, secs in sorted(proj.items()):
            print(f"    {p}: {_format_duration(secs)}")

    print(f"\n{'=' * 50}")
    print(f"Week total: {_format_duration(total_week)}")


def cmd_report(args: argparse.Namespace) -> None:
    """Date-range report."""
    sessions = _read_sessions()

    from_dt: Optional[datetime] = None
    to_dt: Optional[datetime] = None

    if args.from_date:
        d = _parse_date_arg(args.from_date)
        from_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    if args.to_date:
        d = _parse_date_arg(args.to_date)
        to_dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)

    filtered = _sessions_in_range(sessions, from_dt, to_dt)
    if args.project:
        filtered = [s for s in filtered if s.get("project") == args.project]

    fmt = args.format

    if fmt == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["id", "start", "end", "project", "note", "duration_seconds", "duration_formatted"])
        for s in filtered:
            writer.writerow(
                [
                    s.get("id", ""),
                    s.get("start", ""),
                    s.get("end", ""),
                    s.get("project", "default"),
                    s.get("note", ""),
                    s.get("duration_seconds", 0),
                    _format_duration(s.get("duration_seconds", 0)),
                ]
            )
        return

    if fmt == "json":
        out = []
        for s in filtered:
            out.append(
                {
                    "id": s.get("id"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "project": s.get("project", "default"),
                    "note": s.get("note", ""),
                    "duration_seconds": s.get("duration_seconds", 0),
                    "duration_formatted": _format_duration(s.get("duration_seconds", 0)),
                }
            )
        print(json.dumps(out, indent=2))
        return

    # Text
    if not filtered:
        print("No sessions in range.")
        return

    total = 0
    ARROW = "\u2192"
    EM_DASH = "\u2014"
    for s in filtered:
        dur = s.get("duration_seconds", 0)
        total += dur
        end_str = s.get("end") or "running"
        print(
            f"  {s['start']}  {ARROW}  {end_str}  "
            f"({_format_duration(dur)})  [{s.get('project', 'default')}]"
            f"{'  ' + EM_DASH + ' ' + s['note'] if s.get('note') else ''}"
        )

    print(f"\nTotal: {_format_duration(total)}  ({len(filtered)} session(s))")


def cmd_edit(args: argparse.Namespace) -> None:
    """Edit a past session."""
    session_id: str = args.session_id
    sessions = _read_sessions()

    target: Optional[Dict[str, Any]] = None
    for s in sessions:
        if s.get("id") == session_id:
            target = s
            break

    if target is None:
        print(f"No session found with id {session_id!r}", file=sys.stderr)
        sys.exit(1)

    if args.start:
        start_time = _parse_time_arg(args.start)
        start_dt = datetime.fromisoformat(target["start"])
        new_start = start_dt.replace(hour=int(start_time[:2]), minute=int(start_time[3:]))
        target["start"] = new_start.isoformat()

    if args.end:
        end_time = _parse_time_arg(args.end)
        if target.get("end"):
            end_dt = datetime.fromisoformat(target["end"])
            new_end = end_dt.replace(hour=int(end_time[:2]), minute=int(end_time[3:]))
        else:
            start_dt = datetime.fromisoformat(target["start"])
            new_end = start_dt.replace(hour=int(end_time[:2]), minute=int(end_time[3:]))
        target["end"] = new_end.isoformat()

    if args.project is not None:
        target["project"] = args.project

    if args.note is not None:
        target["note"] = args.note

    # Recalculate duration if both start and end are set
    if target.get("start") and target.get("end"):
        target["duration_seconds"] = _calc_duration_seconds(target["start"], target["end"])

    _write_sessions(sessions)
    print(f"Session {session_id!r} updated.")


def cmd_projects(_args: argparse.Namespace) -> None:
    """List all projects with total hours."""
    sessions = _read_sessions()
    proj: Dict[str, int] = {}
    for s in sessions:
        p = s.get("project", "default")
        proj[p] = proj.get(p, 0) + s.get("duration_seconds", 0)

    if not proj:
        print("No sessions recorded.")
        return

    print(f"{'Project':<30} {'Total':>10}  Sessions")
    print("-" * 55)
    for p_name in sorted(proj, key=lambda k: proj[k], reverse=True):
        secs = proj[p_name]
        count = sum(1 for s in sessions if s.get("project") == p_name)
        print(f"{p_name:<30} {_format_duration(secs):>10}  {count}")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------
def _add_format_arg(parser: argparse.ArgumentParser, default: str = "text") -> None:
    parser.add_argument("--format", choices=["text", "json", "csv"], default=default, help="Output format")


def _add_common_format_arg(parser: argparse.ArgumentParser, default: str = "text") -> None:
    parser.add_argument("--format", choices=["text", "json"], default=default, help="Output format")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Time_Card \u2014 Worklog tracker. Clock in/out, tag projects, weekly summaries, CSV export.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # in
    p_in = sub.add_parser("in", help="Clock in (start a new work session)")
    p_in.add_argument("--project", "-p", default=None, help="Project name")
    p_in.add_argument("--note", "-n", default=None, help="Note for this session")

    # out
    p_out = sub.add_parser("out", help="Clock out (end current session)")
    p_out.add_argument("--note", "-n", default=None, help="Note for this session")

    # status
    sub.add_parser("status", help="Show current status")

    # today
    p_today = sub.add_parser("today", help="Show today's sessions")
    _add_common_format_arg(p_today)

    # week
    p_week = sub.add_parser("week", help="Weekly summary (Mon\u2013Sun)")
    _add_common_format_arg(p_week)

    # report
    p_report = sub.add_parser("report", help="Report for a date range")
    p_report.add_argument("--from", dest="from_date", metavar="DATE", help="Start date (YYYY-MM-DD)")
    p_report.add_argument("--to", dest="to_date", metavar="DATE", help="End date (YYYY-MM-DD)")
    p_report.add_argument("--project", "-p", help="Filter by project")
    _add_format_arg(p_report)

    # edit
    p_edit = sub.add_parser("edit", help="Edit a past session")
    p_edit.add_argument("session_id", help="Session ID to edit")
    p_edit.add_argument("--start", help="New start time (HH:MM)")
    p_edit.add_argument("--end", help="New end time (HH:MM)")
    p_edit.add_argument("--project", "-p", help="New project name")
    p_edit.add_argument("--note", "-n", help="New note")

    # projects
    sub.add_parser("projects", help="List all projects with total hours")

    args = parser.parse_args()

    dispatch = {
        "in": cmd_in,
        "out": cmd_out,
        "status": cmd_status,
        "today": cmd_today,
        "week": cmd_week,
        "report": cmd_report,
        "edit": cmd_edit,
        "projects": cmd_projects,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
