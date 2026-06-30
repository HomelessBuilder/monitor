# Monitor — User Manual

## What This Is

The monitor is a dedicated Claude Code instance that runs on a schedule and watches your development ecosystem for activity and anomalies. It reads project state, writes timestamped reports, and flags concerns — but takes no other actions. It cannot edit project files, commit code, or change system configuration.

---

## Directory Structure

```
~/monitor/
  CLAUDE.md           — monitor's role definition and operating rules
  USER-MANUAL.md      — this file
  run-monitor.sh      — script called by cron each hour
  web-server.py       — local web viewer for reports (localhost:8765)
  cron.log            — log of each cron invocation (created on first run)
  .claude/
    settings.json     — pre-approved permissions for headless operation
  reports/
    YYYY-MM-DD_HH-MM.md   — one report per hourly check
    CONCERNS.md            — running log of flagged concerns (appended, never overwritten)
  state/
    last-run.json          — tracks last-seen git SHAs and timestamps for delta checks
```

---

## Cron Job

The monitor runs automatically at the top of every hour. The cron entry is:

```
0 * * * * /home/bored/monitor/run-monitor.sh
```

To confirm it is active: `crontab -l`

To deactivate, open `crontab -e` and remove or comment out that line. To reactivate, add it back.

---

## Web Viewer

Reports can be viewed in a browser via a local web server included with the monitor.

**Starting the viewer:**
```
python3 ~/monitor/web-server.py
```

Then open your browser and go to:
```
http://localhost:8765
```

The viewer shows a sidebar listing all reports newest-first, with CONCERNS.md pinned at the top if any concerns have been logged. Click any report to read it as formatted HTML.

**Stopping the viewer:**
Press `Ctrl+C` in the terminal where it is running.

The viewer runs only while you have it open — it does not start automatically on boot. Start it when you want to review reports; stop it when done.

---

## Reading Reports (Terminal)

Reports are saved to `~/monitor/reports/` with filenames in the format `YYYY-MM-DD_HH-MM.md`.

Each report contains:
- **Activity Since Last Check** — new git commits per project, file changes, new directories
- **Concerns** — anything that met the concern criteria (or "None")
- **State** — confirmation that last-run.json was updated

To list recent reports from the terminal:
```
ls -lt ~/monitor/reports/*.md | head -5
```

---

## The CONCERNS.md File

`~/monitor/reports/CONCERNS.md` is a running log. Every time a check finds something worth flagging, it is appended here with a timestamp. This file is never overwritten — concerns accumulate so nothing gets lost between your review sessions.

It appears at the top of the web viewer sidebar when it exists. To check it from the terminal:
```
cat ~/monitor/reports/CONCERNS.md
```

If the file does not exist, no concerns have been raised yet.

---

## What the Monitor Considers a Concern

- Any project silent for more than 48 hours (no commits, no file changes)
- Unexpected files or directories appearing in project folders
- New top-level directories in `~/` that don't match known projects or known archives
- A project's CURRENT.md or DEVLOG.md modified but no corresponding git commit
- Any sign that a project instance wrote outside its own directory
- Errors in bash output during a check

**Not considered concerns:**
- No activity during overnight hours (midnight–7am)
- devlog-engine having no git repo (expected — it is in planning phase)
- Known archive/backup directories (sandiegoai-live-snapshot-*, sdai-h_backed-*, etc.)

---

## Running a Manual Check

You can trigger a check at any time without waiting for cron:

```
cd ~/monitor && ./run-monitor.sh
```

The report will appear in `~/monitor/reports/` with the current timestamp.

---

## Checking the Cron Log

Each time cron fires the script, an entry is written to `~/monitor/cron.log`:

```
cat ~/monitor/cron.log
```

This shows whether checks are running successfully, and records any errors from the `claude` process.

---

## First Run Behavior

On the first run, `state/last-run.json` contains null values for all projects. The monitor will treat this as a cold start and report the current HEAD commit for each repo as the new baseline. No historical activity will be surfaced — only future changes from that point forward.

---

## Updating the Monitor's Scope

If a new project becomes active, the monitor's awareness needs two updates:

1. Add a row to the **Projects to Watch** table in `~/monitor/CLAUDE.md`
2. Add a corresponding entry under `"projects"` in `~/monitor/state/last-run.json`

The overseer instance at `~/` handles new project onboarding and should prompt these updates when a new project is designated active.

---

## Troubleshooting

**Reports are not being created**
- Check `~/monitor/cron.log` for error messages
- Confirm the cron job is active: `crontab -l`
- Confirm the script is executable: `ls -l ~/monitor/run-monitor.sh`
- Confirm claude is reachable: `which claude`

**Monitor reports an error finding claude**
- The script exports `~/.local/bin` on PATH, which is where claude lives
- If claude moves, update the PATH line in `run-monitor.sh` accordingly

**Web viewer shows "No reports yet"**
- The cron job hasn't run yet, or the cron job is not active
- Trigger a manual check: `cd ~/monitor && ./run-monitor.sh`
- Refresh the browser after the check completes

**Web viewer port 8765 is already in use**
- Check what is using it: `ss -tlnp | grep 8765`
- Either stop that process or edit the PORT value at the top of `web-server.py`

**Monitor outputs a permission request instead of a report**
- This means the `.claude/settings.json` permissions aren't being applied
- First check that the workspace is trusted: look for `/home/bored/monitor` in the `projects` section of `~/.claude.json` and confirm `"hasTrustDialogAccepted": true`
- If the entry is missing, add it manually:
  ```json
  "/home/bored/monitor": {
    "hasTrustDialogAccepted": true
  }
  ```
- If trust is set but prompts persist, check that `.claude/settings.json` exists in `~/monitor/.claude/` and is valid JSON

**Monitor reports show git activity but cannot read files or list directories**
- The `Bash(*)` and `Read(*)` entries in `.claude/settings.json` cover all read-only operations
- If these are missing or malformed, restore the full settings file:
  ```json
  {
    "permissions": {
      "allow": ["Bash(*)", "Read(*)", "Write(*)"],
      "deny": []
    }
  }
  ```
- Note: `Write(*)` is intentionally broad here. The monitor's CLAUDE.md restricts what it will actually write — only `last-run.json` and `CONCERNS.md`. The permission allows it; the instructions constrain it.

**last-run.json is malformed**
- Reset it by restoring the null-state template:
  ```json
  {
    "last_run": null,
    "projects": {
      "my-eleventy-sdai-h": { "last_sha": null, "last_checked": null },
      "claude-journal": { "last_sha": null, "last_checked": null },
      "devlog-engine": { "last_sha": null, "last_checked": null }
    },
    "home_dir": { "last_checked": null }
  }
  ```
- The next run will treat it as a cold start.
