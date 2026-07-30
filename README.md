# still-true

> A Claude Code skill that stops Claude asserting stale state. A fact read from a transcript was true *then*; before saying it's true *now* — especially when the claim is negative ("still pending", "never sent", "falta") — check the live authority. Enforced by a Stop hook.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## The pain it solves

On 30 July 2026, Claude handed me a list of 76 open items. Three were wrong, all the same way:

| Reported | Reality |
|---|---|
| "€900 Boehringer invoice never issued" | sent 3-Jul to `fornecedores_bi_pt@reisswolf.pt` — FT 2026/12, PO 4701202998, PDF on disk |
| "€60 ERKNet invoice still unsigned, needs returning" | signed and returned 16-Jul |
| "Booking refund draft never sent" | sent 10-Jun |

Nothing was invented. Every claim was true *on the day the source transcript was written*, and false on the day it was reported. Three wrong out of 76 sounds like a good score — except each wrong item is an instruction to redo work that is already done, and since you can't tell which three, you now have to re-check all 76. The list's value goes to zero.

The root cause has three layers:

1. **Transcripts treated as state.** A `.jsonl` from 22 June saying "ainda não foi emitida" is true *for 22 June*. It was promoted to "pending today" without anyone checking the 38 days in between.
2. **The negative treated as cheap.** There was a rule against saying "I sent X" without checking. There was none against "X still needs sending" — and the negative costs *more*, because it sends you to duplicate finished work and it discredits the whole report.
3. **Subagent output accepted as fact.** The agent concluded "never issued" from transcripts alone. It never opened the Sent folder.

**still-true** is the rule those three layers were missing.

## The core rule

> Before asserting the current state of anything — doubly so when the assertion is NEGATIVE — confirm it against the LIVE authority for that class of fact.

| Claim | Live authority | Does NOT count as proof |
|---|---|---|
| email sent / not sent | Gmail `in:sent` + `list_drafts` | a transcript, a memory file, the draft existing |
| document produced | filesystem (`find`, `ls`) | "I generated it" in an old session |
| payment made / received | bank statement, bank email | the invoice having been issued |
| code shipped | `git log` of the **remote** + CI | a green local working tree |
| form submitted | the portal, the confirmation email | the file being filled in |
| event / deadline | Calendar API | memory |
| application decided | the funder's portal | the absence of an email |

Three hard rules follow from it:

1. **The negative demands the same proof as the positive.** Absence of evidence is not evidence of absence. Before declaring anything pending, run a *positive* search on the subject's strong keys — PO number, invoice number, recipient domain, filename — in **at least two systems of record**.
2. **Transcripts and memories are photographs, not state.** They carry a date. Treat that date as an expiry, not a footnote. Never promote a transcript sentence directly into a pending item; the transcript is the question, not the answer.
3. **A subagent's finding is a hypothesis.** Especially a negative one. Instruct agents to cross-check the live source and to name it; if they didn't, the negative doesn't count — re-run one direct query yourself.

And when you do report state, stamp it:

> `Boehringer invoice: sent — Gmail Sent, 30-Jul 21:45 (PO 4701202998, 3-Jul)`

The as-of stamp lets the reader judge the age of the claim instead of assuming it's fresh.

## Quick demo

```
You: what's still open on the Reisper invoicing side?

Claude (without still-true):
  "Three things are outstanding: the €900 Boehringer invoice was never issued,
   the €60 ERKNet invoice still needs signing, and the Booking refund draft
   was never sent."

──────────────────────────────────────────────────────

You: what's still open on the Reisper invoicing side?

Claude (with still-true):
  [Gmail  in:sent 4701202998            → 1 thread, 3-Jul]
  [Gmail  in:sent erknet                → 1 thread, 16-Jul, "signed" attached]
  [Gmail  in:sent booking refund        → 1 thread, 10-Jun]
  [Bash   find ~ -iname '*FT-2026-12*'  → invoice PDF, mtime 3-Jul]

  Nothing outstanding on those three — all sent (checked Gmail Sent, 30-Jul 21:45).
  Boehringer FT 2026/12 went out 3-Jul, ERKNet signed 16-Jul, Booking 10-Jun.
```

Four tool calls. Three items of duplicated work avoided, and 73 other items that stay credible.

## Install

Inspect-then-run:

```bash
git clone https://github.com/pedroreisper/still-true
cd still-true
less install.sh           # short, no obfuscation
bash install.sh --hook    # installs skill + wires the Stop hook
```

Or one-liner (trust the URL):

```bash
curl -fsSL https://raw.githubusercontent.com/pedroreisper/still-true/main/install.sh | bash -s -- --hook
```

Then `/reload` your Claude Code session.

### Manual install

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/pedroreisper/still-true ~/.claude/skills/still-true
bash ~/.claude/skills/still-true/hooks/install_hook.sh
```

### Uninstall

```bash
bash install.sh --uninstall   # removes the skill
# remove the Stop hook entry in ~/.claude/settings.json (search for stale_claim.py)
```

## How the hook works

`hooks/stale_claim.py` runs on `Stop` events. It:

1. Reads the latest assistant message from the session transcript.
2. Strips fenced blocks, `> ` quote lines and quoted mentions, then matches a PT+EN catalogue of pending/negative claim phrases (`falta`, `por enviar`, `por assinar`, `está pendente`, `nunca foi`, `ainda não`, `never sent`, `still pending`, `hasn't been`, `no evidence of`, `not yet`, `outstanding`, …). Overlapping matches merge, so one fact is one claim.
3. Walks the **current turn** for tool calls against a live authority.
4. **Blocks** the Stop only if there are **≥2 claims** and **zero** verifications.

### Calibration — why it rarely fires

An always-blocking hook gets uninstalled within a day. This one is deliberately hard to trip:

| Situation | Verdict |
|---|---|
| 2+ negative claims, zero live checks | **block** |
| 2+ negative claims, ≥1 live check (even partial) | allow |
| 1 negative claim, no checks | allow |
| claim inside a code fence, quote line, or `` `backticks` `` | allow |
| `STILL_TRUE_DISABLE=1` | allow (hook off) |
| `stop_hook_active` (our own re-prompt) | allow (no loop) |

What does **not** count as verification, on purpose:

- `Read`/`Grep` of a `.jsonl` transcript, `~/.claude/projects/…`, or a `memory/` file — that is re-reading the snapshot that caused the problem.
- The memory-graph MCP — same reason.
- An `Agent` call — a delegated finding is a hypothesis, not evidence.

### The block message

```
Blocked by still-true: this reply makes 2 pending/negative status claims and ZERO
checks against a live authority in this turn.

Claims caught:
  - "nunca foi"
  - "por assinar"

A negative claim costs more than a positive one — it sends the user to redo work
that may already be done, and one wrong item discredits the whole list. Absence of
evidence is not evidence of absence.

Check the LIVE authority for the class of fact, never a transcript or a memory file:
  email sent / unsent    → Gmail in:sent + list_drafts      (not a transcript, …)
  document produced      → filesystem: find / ls            (not "I generated it" …)
  payment made/received  → bank statement, bank email       (not the invoice …)
  code shipped           → git log of the remote + CI       (not a green local tree)
  form submitted         → the portal, confirmation email   (not the file being …)
  event / deadline       → Calendar API                     (not memory)
  application decided    → the funder's portal              (not the absence of …)

Run a POSITIVE search with the strong keys of the subject — PO number, invoice
number, proposal number, recipient domain, filename — in at least two places. Then
re-state with an as-of stamp: "checked Sent, 30-Jul 21:45".
```

## When to use

| Situation | How the skill fires |
|---|---|
| About to produce a list of open / pending items | Skill self-applies as a checklist. |
| User asks "ainda é verdade?", "is this still true", "still open?", "verifica o estado", "as of when" | Trigger phrase. |
| About to convert something you *read* into something you *assert* | Skill self-applies. |
| Claude types 2+ pending claims with no checks | Stop hook blocks. |

## When NOT to use

- Dated historical facts that cannot decay ("the invoice was issued on 3 July").
- Facts the user has just supplied this turn — they are the authority.
- Pure computation, opinion, or design discussion.
- You already checked the authority two minutes ago. One check per turn, not per sentence.

## Interaction with other Claude Code skills

- **`did-it-actually`** verifies output against the *request*. `still-true` verifies claims against the *world*. A PASS on a status report full of stale items is a hollow pass.
- **`landed`** asks "did MY work reach its real destination". `still-true` asks "is my statement about ANY fact still valid".
- **`resourceful`** bans premature surrender — not looking. `still-true` bans premature assertion — looking once, long ago.
- **`briefing`** is a live-authority climb by construction (calendar + inbox, read fresh). It's what a compliant answer looks like.

## File layout

```
still-true/
├── SKILL.md                                # main skill spec, loaded by Claude Code
├── README.md                               # this file
├── LICENSE                                 # MIT
├── install.sh                              # installer
├── references/
│   ├── authority-table.md                  # class → live authority, with the exact query
│   ├── negative-claims.md                  # why the negative costs more + the post-mortem
│   └── agent-findings.md                   # instructing and re-testing subagents
├── hooks/
│   ├── stale_claim.py                      # Stop hook
│   └── install_hook.sh                     # wires the hook into settings.json
├── scripts/
│   └── doctor.sh                           # verify install + hook wiring
└── tests/
    └── run-tests.sh                        # 31 block/allow assertions over fixtures
```

## Limitations

- The hook is a regex pass — creatively phrased staleness slips through. Fenced blocks, `> ` lines and quoted mentions are stripped so meta-discussion doesn't self-trigger; the flip side is that a genuine claim written inside quotes escapes.
- "Verification" is classified from the tool name and its arguments. A Gmail search with the wrong key counts as a check even though it proves nothing — the hook enforces that you *looked*, not that you looked well. Rules 1–3 in `SKILL.md` are what enforce looking well.
- Vocabulary is English + Portuguese. Add patterns to `CLAIM_PATTERNS` in `hooks/stale_claim.py` for other languages.
- The hook reads the session transcript file directly. Format changes in future Claude Code versions may require a small update to `read_transcript()`.

## Contributing

PRs welcome. Useful additions:

- More claim patterns in other languages.
- More rows for `references/authority-table.md` — every domain has its own system of record.
- More snapshot-source classifiers (any store that is a photograph rather than state).

## License

MIT. See `LICENSE`.
