#!/usr/bin/env python3
"""
stale_claim.py — Stop hook for the `still-true` skill.

Reads the latest assistant message + the current turn's tool-call transcript.
If the message asserts that something is PENDING / NEVER HAPPENED / STILL OPEN
(a negative status claim) AND the turn contains zero calls to a live authority
(Gmail sent folder, drafts, filesystem, git, a portal, the calendar), it blocks
the Stop and tells the model which authority to check.

Hook spec (Claude Code Stop hook):
  - Receives JSON on stdin: { transcript_path, stop_hook_active, ... }
  - May print a JSON response to stdout: { "decision": "block", "reason": "..." }
  - Otherwise exits 0 silently (allow).

Calibration is deliberately lenient — a stale-claim hook that fires on every list
of open items is a hook that gets uninstalled. It blocks ONLY on the shape that
actually burned us: several negative claims, no verification at all. One claim
passes. One verification passes. Set STILL_TRUE_DISABLE=1 to turn it off entirely.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Negative / pending status-claim catalogue (case-insensitive, PT + EN).
# These are claims about the CURRENT state of the world whose truth decays.
# ---------------------------------------------------------------------------
CLAIM_PATTERNS: list[re.Pattern[str]] = [
    # Portuguese
    re.compile(r"\bfalta(?:m|va|vam)?\b", re.I),
    re.compile(r"\bem falta\b", re.I),
    re.compile(r"\bpor enviar\b", re.I),
    re.compile(r"\bpor fazer\b", re.I),
    re.compile(r"\bpor assinar\b", re.I),
    re.compile(r"\bpor emitir\b", re.I),
    re.compile(r"\bpor submeter\b", re.I),
    re.compile(r"\bpor pagar\b", re.I),
    re.compile(r"\bpor responder\b", re.I),
    re.compile(r"\b(?:est[áa]|est[ãa]o|continua|continuam|permanece|permanecem)\s+pendente(?:s)?\b", re.I),
    re.compile(r"\bnunca (?:foi|foram|chegou|chegaram|se)\b", re.I),
    re.compile(r"\bn[ãa]o (?:foi|foram) enviad", re.I),
    re.compile(r"\bn[ãa]o (?:foi|foram) emitid", re.I),
    re.compile(r"\bainda n[ãa]o\b", re.I),
    re.compile(r"\bsem resposta\b", re.I),
    re.compile(r"\bn[ãa]o h[áa] (?:registo|prova|vest[íi]gio|sinal)\b", re.I),
    re.compile(r"\bzero (?:men[çc][õo]es|registos|resultados)\b", re.I),
    # English
    re.compile(r"\bnever sent\b", re.I),
    re.compile(r"\bnever (?:issued|signed|submitted|filed|paid|replied|happened|arrived)\b", re.I),
    re.compile(r"\bwas never\b", re.I),
    re.compile(r"\b(?:has|have) never been\b", re.I),
    re.compile(r"\bstill pending\b", re.I),
    re.compile(r"\bstill (?:open|outstanding|unanswered|unsigned|unsent|unpaid)\b", re.I),
    re.compile(r"\b(?:hasn|haven|wasn|weren|didn)['’]?t been\b", re.I),
    re.compile(r"\b(?:hasn|haven)['’]?t (?:sent|signed|issued|submitted|paid|replied)\b", re.I),
    re.compile(r"\bno evidence of\b", re.I),
    re.compile(r"\bno record of\b", re.I),
    re.compile(r"\bno trace of\b", re.I),
    re.compile(r"\bnot yet\b", re.I),
    re.compile(r"\boutstanding\b", re.I),
    re.compile(r"\bzero (?:mentions|hits|results|matches)\b", re.I),
]

# ---------------------------------------------------------------------------
# Live-authority classifier.
#
# A tool call counts as verification when it touches something that reflects the
# world AS IT IS NOW. Transcripts, memory files and subagent summaries are
# snapshots and hypotheses — they are exactly what produced the bad claims, so
# they must never satisfy the gate.
# ---------------------------------------------------------------------------
SNAPSHOT_PATH_RE = re.compile(
    r"\.jsonl\b|/\.claude/projects/|[/\\]memory[/\\]|\.claude/history",
    re.I,
)

# MCP families that read a live system of record.
LIVE_MCP_HINTS: tuple[str, ...] = (
    "gmail", "calendar", "drive", "github", "gocardless", "playwright",
    "computer", "fetch", "vercel", "slack",
)
# MCP families that are snapshots of what we already believed.
SNAPSHOT_MCP_HINTS: tuple[str, ...] = ("memory",)

LIVE_BASH_HINTS: tuple[str, ...] = (
    "git ", "gh ", "ls ", "find ", "mdfind", "curl ", "stat ", "open ",
    "osascript", "shasum", "du ", "test -f", "[ -f",
)


def _input_blob(event: dict) -> str:
    """Flatten a tool-call input to a searchable string."""
    payload = event.get("input") or event.get("tool_input") or {}
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(payload)


def classify_verification(event: dict) -> str | None:
    """Return a live-authority label for a tool-call event, else None."""
    name = event.get("name") or event.get("tool_name") or ""
    if not name:
        return None

    blob = _input_blob(event)

    if name.startswith("mcp__"):
        low = name.lower()
        if any(h in low for h in SNAPSHOT_MCP_HINTS):
            return None
        if any(h in low for h in LIVE_MCP_HINTS):
            return "mcp"
        return "mcp"

    if name in ("WebFetch", "WebSearch"):
        return "web"

    if name in ("Read", "Grep", "Glob", "NotebookRead"):
        # Reading last month's transcript is re-reading the snapshot that caused
        # the problem. It is not a check against the live world.
        if SNAPSHOT_PATH_RE.search(blob):
            return None
        return "filesystem"

    if name == "Bash":
        cmd = (event.get("input") or {}).get("command", "") or ""
        if SNAPSHOT_PATH_RE.search(cmd):
            return None
        if any(h in cmd for h in LIVE_BASH_HINTS):
            return "shell"
        return "shell"

    # A subagent's conclusion is a hypothesis, not evidence — hard rule 3.
    if name in ("Agent", "Task"):
        return None

    return None


def read_transcript(path: str) -> list[dict]:
    """Read the Claude Code session transcript (JSONL). Return list of events."""
    events: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (OSError, FileNotFoundError):
        pass
    return events


def latest_assistant_text(events: list[dict]) -> str:
    """Best-effort extraction of the most recent assistant text content."""
    for ev in reversed(events):
        if ev.get("role") != "assistant" and ev.get("type") != "assistant":
            continue
        content = ev.get("content") or ev.get("message", {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    chunks.append(block.get("text", ""))
            if chunks:
                return "\n".join(chunks)
    return ""


def _current_question_events(events: list[dict]) -> list[dict]:
    """Slice events down to the CURRENT question — everything after the last genuine
    user text prompt (ignoring tool-result user events). Verification done for an
    earlier, unrelated question must not vouch for this one's claims."""
    last_user = -1
    for i, ev in enumerate(events):
        if ev.get("role") == "user" or ev.get("type") == "user":
            content = ev.get("content") or ev.get("message", {}).get("content")
            if isinstance(content, str) and content.strip() and not content.lstrip().startswith("<"):
                last_user = i
    return events[last_user:] if last_user >= 0 else events


def verifications_this_turn(events: list[dict], window: int = 80) -> set[str]:
    """Collect distinct live-authority classes touched during the CURRENT question."""
    seen: set[str] = set()
    scoped = _current_question_events(events)
    for ev in scoped[-window:]:
        label = classify_verification(ev)
        if label:
            seen.add(label)
        content = ev.get("content") or ev.get("message", {}).get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    label = classify_verification(
                        {"name": block.get("name"), "input": block.get("input")}
                    )
                    if label:
                        seen.add(label)
    return seen


# ---------------------------------------------------------------------------
# False-positive defences — same stripping discipline as `resourceful`'s
# pre_capitulation.py (hardened against ReDoS: every span is line-bounded and
# built from negated character classes, never `.*?` across newlines).
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"```.*?```", re.S)

_SYMMETRIC_SPANS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("`", re.compile(r"``([^\n]+?)``")),
    ("`", re.compile(r"`([^`\n]+)`")),
    ('"', re.compile(r'"([^"\n]+)"')),
)
# The single-quote form demands non-word boundaries so apostrophes inside words
# (don't, hasn't, it's) never open or close a span.
_SINGLE_QUOTE_SPAN = re.compile(r"(?<!\w)'([^'\n]+)'(?!\w)")
_ASYMMETRIC_SPANS: tuple[re.Pattern[str], ...] = (
    re.compile(r"“([^”\n]+)”"),
    re.compile(r"„([^“\n]+)“"),
    re.compile(r"(?<!\w)‘([^’\n]+)’(?!\w)"),
    re.compile(r"«([^»\n]+)»"),
)
# Markdown emphasis is unwrapped, never dropped: `_` is a word character, so
# _ainda não_ would otherwise defeat the \b anchors in CLAIM_PATTERNS.
_MD_EMPHASIS_RE = re.compile(r"(?<!\w)([_*]{1,3})([^\n]+?)\1(?!\w)")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")
# A span is a MENTION only when the claim phrase is essentially the whole span.
_MENTION_COVERAGE = 0.6


def _is_mention(inner: str) -> bool:
    body = inner.strip()
    if not body:
        return False
    for pat in CLAIM_PATTERNS:
        hit = pat.search(body)
        if hit and len(hit.group(0)) >= _MENTION_COVERAGE * len(body):
            return True
    return False


def _defuse_span(m: re.Match[str]) -> str:
    inner = m.group(1)
    return " " if _is_mention(inner) else f" {inner} "


def _strip_inline_spans(line: str) -> str:
    line = _MD_EMPHASIS_RE.sub(lambda m: f" {m.group(2)} ", line)
    for delim, pat in _SYMMETRIC_SPANS:
        if line.count(delim) % 2:
            continue  # unbalanced: stripping would eat prose outside the span
        line = pat.sub(_defuse_span, line)
    line = _SINGLE_QUOTE_SPAN.sub(_defuse_span, line)
    for pat in _ASYMMETRIC_SPANS:
        line = pat.sub(_defuse_span, line)
    return line


def _strip_quotes_and_fences(text: str) -> str:
    """Drop ```fenced``` blocks, `> ` quote lines and quoted mentions of claim
    phrases, so quoting the user — or documenting this skill's own catalogue —
    doesn't self-trigger the hook.

    Known trade-off: a genuine claim written inside quotes escapes the hook.
    Mentioning beats using; a meta-discussion that can't be had is worse than a
    stale claim that slips through.
    """
    text = _FENCE_RE.sub(" ", text)
    kept = [
        _strip_inline_spans(ln)
        for ln in text.splitlines()
        if not ln.lstrip().startswith(">")
    ]
    return _MULTISPACE_RE.sub(" ", "\n".join(kept))


def find_claims(text: str) -> list[str]:
    """Return the distinct negative/pending claims in `text`.

    Overlapping matches are merged: "ainda não foi enviada" trips both
    `ainda não` and `não foi enviad`, but it is ONE claim about one fact, and
    counting it twice would block a single-item answer.
    """
    scan = _strip_quotes_and_fences(text)
    spans: list[tuple[int, int]] = []
    for pat in CLAIM_PATTERNS:
        for m in pat.finditer(scan):
            spans.append((m.start(), m.end()))
    if not spans:
        return []
    spans.sort()
    merged: list[tuple[int, int]] = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return [scan[s:e].strip() for s, e in merged]


BLOCK_TEMPLATE = """\
Blocked by still-true: this reply makes {n} pending/negative status claims and ZERO checks against a live authority in this turn.

Claims caught:
{claims}

A negative claim costs more than a positive one — it sends the user to redo work that may already be done, and one wrong item discredits the whole list. Absence of evidence is not evidence of absence.

Check the LIVE authority for the class of fact, never a transcript or a memory file:
  email sent / unsent    → Gmail in:sent + list_drafts      (not a transcript, not the draft existing)
  document produced      → filesystem: find / ls            (not "I generated it" in an old session)
  payment made/received  → bank statement, bank email       (not the invoice having been issued)
  code shipped           → git log of the remote + CI       (not a green local working tree)
  form submitted         → the portal, confirmation email   (not the file being filled in)
  event / deadline       → Calendar API                     (not memory)
  application decided    → the funder's portal              (not the absence of an email)

Run a POSITIVE search with the strong keys of the subject — PO number, invoice number, proposal number, recipient domain, filename — in at least two places. Then re-state with an as-of stamp: "checked Sent, 30-Jul 21:45".

Full table: references/authority-table.md · disable with STILL_TRUE_DISABLE=1
Do not retry the same reply unchanged."""


def main() -> int:
    if os.environ.get("STILL_TRUE_DISABLE", "").strip() not in ("", "0", "false", "no"):
        return 0

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    # One block per stop chain: when our previous block re-invoked the model and it
    # stopped again, Claude Code sets stop_hook_active. Without this guard a claim
    # the model refuses to drop would loop forever.
    if payload.get("stop_hook_active"):
        return 0

    transcript_path = payload.get("transcript_path") or payload.get("transcriptPath")
    if not transcript_path or not Path(transcript_path).exists():
        return 0

    events = read_transcript(transcript_path)
    text = latest_assistant_text(events)
    if not text:
        return 0

    claims = find_claims(text)
    # Calibration: a single pending item is normal conversation. Two or more is a
    # status report, and a status report with no verification is the failure mode.
    if len(claims) < 2:
        return 0

    verified = verifications_this_turn(events)
    if verified:
        print(
            f"[still-true] {len(claims)} pending claim(s) allowed: "
            f"live authority touched = {sorted(verified)}",
            file=sys.stderr,
        )
        return 0

    shown = claims[:6]
    listing = "\n".join(f'  - "{c}"' for c in shown)
    if len(claims) > len(shown):
        listing += f"\n  - … and {len(claims) - len(shown)} more"

    print(json.dumps({
        "decision": "block",
        "reason": BLOCK_TEMPLATE.format(n=len(claims), claims=listing),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
