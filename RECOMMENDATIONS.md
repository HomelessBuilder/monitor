# Monitor — Recommendations for Production-Grade Operation

**Prepared by:** Overseer instance (~/)
**Date:** 2026-07-04
**Basis:** Direct inspection of `~/monitor/` — CLAUDE.md, USER-MANUAL.md, run-monitor.sh, web-server.py, cron.log, state/last-run.json, reports/CONCERNS.md, and the full reports/ directory (94 files).
**Scope of this document:** Findings and recommendations only. No files were modified, deleted, or reorganized in `~/monitor/` as part of this review, per standing rules. This file is new — it does not overwrite anything.

This monitor was launched as an experiment and has been running mostly unattended. That shows up concretely in the file system, not just as a vague feeling — the evidence below is drawn directly from what's on disk right now.

---

## 1. Root cause: no enforced output contract

This is the source of most of the mess below, so it's listed first.

`CLAUDE.md` instructs the Claude Code instance to "output the full report to stdout... the calling script saves it as a file" (step 5 of the Monitoring Check Procedure), and to write **only** `state/last-run.json` and `reports/CONCERNS.md` directly. But `.claude/settings.json` grants unrestricted `Write(*)`, and in practice the model frequently writes its **own** report file too, with its own invented name and timestamp — in addition to the one `run-monitor.sh` saves from stdout.

Evidence in `reports/`: 94 files total, only 65 follow the canonical `YYYY-MM-DD_HH-MM.md` naming the script produces. The other 29 are self-written duplicates in at least six different naming schemes:

```
MONITOR_2026-06-30_20-00-25.md
monitor-2026-07-01-22-00.md
monitor-2026-07-01.md
MONITOR-2026-07-01.md
REPORT-2026-07-01-20-00.txt
report-2026-07-02-01-00.md
monitor-report-2026-07-02_post-check.md
2026-07-03-19-00-check.md   (missing underscore before "check")
CURRENT-REPORT.md           (no timestamp at all — appears to be self-designated as "the current one")
```

This is not a filesystem problem, it's an instruction-following problem: an LLM given broad write permission and a soft prose constraint ("write only X and Y") will drift, especially across dozens of independent hourly invocations with no shared memory between them. **Prose instructions are not an enforcement mechanism.** This single issue is responsible for most of the clutter and inconsistency described in the rest of this document, so it should be fixed first.

**Recommendation:** Narrow `.claude/settings.json` from blanket `Write(*)` to an explicit allowlist of the two real write targets (`state/last-run.json`, `reports/CONCERNS.md`). Have the model return the report as its final message only — never as a file write. This turns the existing soft rule into a technical constraint instead of a hope.

---

## 2. Failures are logged but not surfaced, and pollute the report archive

`cron.log` shows 4 outright failures (`ERROR: claude exited with code 1`) across ~2 weeks, plus at least one early failure caused by the workspace not being trust-accepted yet (visible in the Jun 29 16:00 entries — `Ignoring 9 permissions.allow entries... this workspace has not been trusted`), which produced a silent 0-byte report instead of a visible error.

Worse, `run-monitor.sh` redirects stdout to the report file unconditionally, regardless of exit code. So when the underlying `claude` call fails, the failure text itself becomes a "report":

```
$ cat reports/2026-07-02_02-00.md
API Error: Unable to connect to API (ConnectionRefused)
```

There are 5 such degenerate reports currently in the archive (0–99 bytes), indistinguishable from real reports unless opened. In the web viewer these show up in the sidebar exactly like every other report, with no visual flag.

**Recommendations:**
- In `run-monitor.sh`, check `$EXIT_CODE` before treating stdout as a valid report. On failure, write to a distinctly-named file (e.g. `reports/FAILED_$TIMESTAMP.md` or a separate `failures/` directory) so it's never confused with real monitoring output.
- Add a lightweight escalation for repeated failures — e.g. if the last 2+ consecutive runs failed, write an entry to `CONCERNS.md` automatically from the bash script (not the LLM), so a broken monitor is guaranteed to surface a concern about itself even if the LLM call is what's broken.
- This closes the current blind spot: a monitor whose job is to notice silence has no mechanism to notice its own silence.

---

## 3. Watch scope is stale — most active projects aren't being watched

`CLAUDE.md`'s "Projects to Watch" table lists 3 projects: `my-eleventy-sdai-h`, `claude-journal`, `devlog-engine`. `state/last-run.json` has actually drifted to tracking 4 (it picked up `ai-dev-platform` on its own at some point, without `CLAUDE.md` ever being updated to match — another instance of the model not respecting its own written procedure, similar to §1).

Meanwhile the overseer's own project list (`~/CLAUDE.md`) currently names roughly 15 active projects — including `ai-audit-interview`, `ai-foundations-lab`, `course-concepts`, `idea-bank`, `project-dashboard`, `solo-builder-meta-system`, `ai-course-platform` — none of which are under git-log-level monitoring. They'd only ever get noticed by the generic "new top-level directory" check, and only once, at creation — not for ongoing silence/activity within them.

`USER-MANUAL.md` already describes the correct procedure for this ("If a new project becomes active, the monitor's awareness needs two updates... The overseer instance should prompt these updates when a new project is designated active") but this hasn't been happening in practice.

**Recommendation:** Rather than hand-maintaining two independent lists (`~/CLAUDE.md` Active Projects and `~/monitor/CLAUDE.md` Projects to Watch) that will keep drifting apart, consider having the monitor **derive** its watch list directly from `~/CLAUDE.md`'s Active Projects table each run, rather than keeping its own copy. That removes an entire class of drift permanently instead of relying on a human or another instance to remember to sync two files. Until that's built, the near-term fix is simply to update `~/monitor/CLAUDE.md`'s table now to match current reality, and make "sync watch list" an explicit, checked step of onboarding rather than a hoped-for prompt.

---

## 4. Concerns accumulate but never resolve

`reports/CONCERNS.md` is append-only by design, which is right for not losing signal — but there's no status field, no resolution step, and no re-validation. Concerns from a week ago sit at the same visual priority as concerns from today. Checking a few of them against current disk state:

| Concern (as logged) | Logged | Current reality |
|---|---|---|
| `un-namedProject` new directory | 2026-07-04 19:42 | Directory no longer exists — resolved/renamed, never noted |
| `MoneyMachine` unexpected directory | 2026-07-02 22:00 (via CURRENT-REPORT.md) | Now has a `CLAUDE.md` — it's an onboarded project, but `CONCERNS.md` still lists it as an open unknown |
| `.calendar` unknown directory | 2026-07-03 19:00 | Still present, still no `CLAUDE.md`, still unresolved — 1+ day old with no follow-up |
| Baseline timestamp anomaly (future timestamp) | 2026-07-02 00:15 | No note of whether this was ever diagnosed or was a one-off |

As written, `CONCERNS.md` will grow forever and become harder to scan precisely as it becomes more valuable. A file meant to be the one place Diego checks for "what needs my attention" currently mixes live issues with dead ones, with no way to tell them apart at a glance.

**Recommendation:** Add a minimal status model — even just a `[ ]` / `[x]` prefix per concern line, or a `## Resolved` section concerns get moved to once they check out on a later run (the model already re-reads state each run, so re-checking "does this concern still hold" for previously-flagged items is cheap to add as a step). At minimum, have each run auto-close a concern about an unknown directory once that directory gets a `CLAUDE.md` — that's directly checkable and would have auto-resolved the MoneyMachine item above.

---

## 5. Report volume has no rotation or compaction plan

94 files in a flat `reports/` directory after ~2 weeks of hourly cadence, growing indefinitely, all read individually by the web viewer with no pagination. This isn't urgent, but "production-grade" implies a plan before it's a problem rather than after.

**Recommendation:** Consider a daily rollup (e.g., a single `reports/YYYY-MM-DD.md` digest, with hourly detail either dropped after the digest is written or moved to a dated subdirectory). Low priority relative to §1–4, but worth deciding on now rather than retrofitting once there are 1,000+ files.

---

## 6. Isolation is enforced only by prose, not by permissions

This connects back to §1 but deserves its own line: `USER-MANUAL.md`'s troubleshooting section is explicit that `Write(*)` is "intentionally broad" and that "the permission allows it; the instructions constrain it." The evidence in this review is that the instructions do **not** reliably constrain it — the model has already, repeatedly, written files outside the one path it was told to use (still within `reports/`, so not a breach of the read-only-elsewhere guarantee, but a clear demonstration that the enforcement model has a real gap, not just a theoretical one).

**Recommendation:** Given the demonstrated drift, tighten `.claude/settings.json` to name-specific paths now rather than waiting for a future incident where the same looseness matters more (e.g. a write outside `~/monitor` entirely). This is the single highest-leverage change available, since it also directly fixes §1.

---

## Suggested priority order

1. **Tighten `Write` permissions to the two specific files** the monitor is actually supposed to touch (§1, §6) — fixes the naming chaos at its source.
2. **Fix `run-monitor.sh` to check exit code before saving output as a report**, and route failures to a distinct location (§2).
3. **Add self-failure escalation** so repeated broken runs generate their own concern (§2).
4. **Sync `~/monitor/CLAUDE.md`'s watch list to current active projects**, and decide whether to make that derived-not-duplicated going forward (§3).
5. **Add a resolve/status mechanism to `CONCERNS.md`** (§4).
6. Plan report rotation before it becomes urgent (§5).

None of these require new infrastructure — they're changes to the existing three files (`CLAUDE.md`, `run-monitor.sh`, `.claude/settings.json`) plus a lightweight convention change to `CONCERNS.md`. I've made no changes myself; this is written up for your review and, if you agree with the direction, for the monitor's own instance (or a session in this project directory) to implement.
