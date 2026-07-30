---
name: still-true
description: Forces Claude to re-verify the CURRENT state of a fact against its live authority before asserting it — and doubly so when the assertion is negative ("falta", "está pendente", "nunca foi enviado", "still pending", "never sent", "no evidence of"). Transcripts, memory files and old sessions are dated snapshots, not state; a subagent's negative finding is a hypothesis, not evidence. Use when the user says "ainda é verdade", "isto ainda está pendente?", "verifica o estado", "estado actual", "confirma antes de dizer", "is this still true", "still open?", "re-check the status", "as of when", or whenever producing a list of open/pending items. Also fires proactively (Stop hook) and blocks a status report that makes several negative claims with zero checks against a live source. NOT a request-fidelity verifier (that's did-it-actually), NOT a destination check for your own work (that's landed), NOT a ban on capitulation (that's resourceful) — this is purely about the TEMPORAL VALIDITY of state claims.
license: MIT
metadata:
  version: "1.0.0"
  priority: "9"
  audience: "claude-code"
---

# still-true — a fact has a timestamp, and yours has expired

On 30 July 2026 this assistant handed Pedro a list of 76 open items. Three were wrong, all the same way:

- *"the €900 Boehringer invoice was never issued"* — it went out on 3 July to `fornecedores_bi_pt@reisswolf.pt`, FT 2026/12, PO 4701202998, with the PDF sitting on disk.
- *"the €60 ERKNet invoice still needs signing and returning"* — signed and returned on 16 July.
- *"the Booking refund draft was never sent"* — sent on 10 June.

Nothing in that list was invented. Every claim was *true on the day the transcript was written*, and false on the day it was reported. Three bad items out of 76 is a 4% error rate — and it destroyed confidence in the other 73, because the user now has to re-check all of them.

## The core rule

**Before asserting the current state of anything — and with redoubled force when the assertion is NEGATIVE ("falta", "está pendente", "nunca foi", "ainda não", "never sent", "still open") — confirm it against the LIVE authority for that class of fact.**

The live authority is the system of record that changes when the world changes. A transcript does not change when the invoice gets paid. Your memory file does not change when the email gets sent.

## The authority table

This is the centre of the skill. Find the row for your claim; check that column; do not accept the third column as proof.

| Claim | Live authority | Does NOT count as proof |
|---|---|---|
| email sent / not sent | Gmail `in:sent` search + `list_drafts` | a transcript, a memory file, the draft existing |
| document produced | filesystem (`find`, `ls`, `stat`) | "I generated it" in an earlier session |
| payment made / received | bank statement, bank notification email | the invoice having been issued |
| code shipped | `git log` of the **remote** + CI status | a green local working tree |
| form submitted | the portal itself, or the confirmation email | the file being filled in |
| event / deadline | Calendar API | memory |
| application decided | the funder's portal | the absence of a rejection email |

The expanded table — with the exact query to run per row — is in `references/authority-table.md`.

## Three hard rules

### 1. The negative demands the same proof as the positive — and costs more

There is a long-standing rule against saying "I sent X" without checking. There was never a rule against saying "X still needs sending". That asymmetry is backwards. A false positive makes you look careless; a **false negative sends the user to redo work that is already done**, and it poisons every neighbouring item on the list.

Absence of evidence is not evidence of absence. Before declaring anything pending, run a **positive** search using the strong keys of the subject — PO number, invoice number, proposal number, recipient domain, filename, amount — in **at least two places**. "I searched and found nothing" is only a finding when you can name the two queries you ran.

Detail and worked cases: `references/negative-claims.md`.

### 2. Transcripts and memories are photographs, not state

A `.jsonl` from 22 June saying "not yet issued" is true *for 22 June*. Converting it into "pending today" silently asserts that nothing happened in the 38 days since — an assertion nobody made and nobody checked.

- Every snapshot has a date. Treat that date as an **expiry**, not a footnote.
- Never promote a sentence from a transcript straight into a pending item. The transcript tells you what to go and check; it is the *question*, not the *answer*.
- The older the snapshot, the more the burden shifts. A three-day-old note about a slow process may hold. A five-week-old note about anything with an email attached almost certainly doesn't.

### 3. A subagent's finding is a hypothesis

Especially a negative one: "never", "doesn't exist", "zero mentions". The agent that produced the Boehringer error had read only transcripts — it never opened the Sent folder, and it reported its absence of hits as a fact.

- When you dispatch an agent, **instruct it to cross-check against the live source**, and to state which one it used.
- If the agent's report doesn't name a live source, its negative doesn't count. Re-run one direct query yourself before relaying it.
- Never launder an agent's confidence into your own. "The agent found nothing" is not "there is nothing".

How to write the instruction and how to re-test: `references/agent-findings.md`.

## The as-of stamp

Every state claim you make carries an implicit timestamp. Make it explicit so the reader can judge its age:

> "Boehringer invoice: **sent** — checked Gmail Sent, 30-Jul 21:45 (FT 2026/12, to `fornecedores_bi_pt@reisswolf.pt`, 3-Jul)."

> "ERKNet invoice: **status unknown as of my last check, 22-Jun** — not re-verified this turn."

The second form is honest and useful. "ERKNet invoice still needs signing" is neither. When you have not checked, say the date of the evidence you *do* have — never round a stale observation up to a present-tense claim.

Format rules: source + timestamp + the key you searched on. Three tokens, one parenthesis.

## When to use

- **Manually** — invoke `/still-true` (or any trigger phrase) before producing a status report, a list of open items, a "what's left" summary, or an answer to "is X done yet".
- **Proactively** — the Stop hook at `hooks/stale_claim.py` scans the outgoing message for pending/negative claims and blocks when there are several with no verification behind them. Install with `bash hooks/install_hook.sh`.
- **Per-task** — any time you are about to convert something you *read* into something you *assert*.

## When NOT to use

- Claims about the past that cannot decay ("the invoice was issued on 3 July" — a dated historical fact, not a state claim).
- Facts the user has just supplied in this turn; they are the authority.
- Pure computation, opinion, or design discussion with no state claim in it.
- Real-time work where you already checked the authority two minutes ago — one check per turn, not one per sentence.

## Hook calibration

The Stop hook is deliberately hard to trip. It blocks **only** when both hold:

1. The message contains **≥2** distinct pending/negative claims, and
2. The turn contains **zero** tool calls against a live authority.

One claim passes. One verification passes — even partial verification passes. This is on purpose: an always-blocking hook gets uninstalled within a day, and the failure mode we care about is the unverified *list*, not the passing remark.

What does **not** count as verification, by design:

- `Read`/`Grep` of a `.jsonl` transcript, `~/.claude/projects/…`, or a `memory/` file — that is re-reading the snapshot that caused the problem.
- The memory-graph MCP — same reason.
- An `Agent` call — hard rule 3; a delegated finding is a hypothesis.

Set `STILL_TRUE_DISABLE=1` to turn the hook off for a session.

## Anti-gaming

- The hook checks the *transcript* for tool calls, not the model's claim that it checked. Writing "I verified in Sent" with no Gmail call in the turn does not satisfy the gate.
- Fenced code blocks, `> ` quote lines and inline quoted mentions (`` `ainda não` ``, `"never sent"`, `«por assinar»`) are stripped before the scan, so quoting the user or documenting this catalogue doesn't self-trigger. A span counts as a *mention* only when the claim phrase is essentially the whole span; scare quotes inside a real claim (`the invoice was never "issued"`) still trip it.
- Overlapping matches merge into one claim: "ainda não foi enviada" is one fact, not two, and a single-item answer is never blocked.
- Two greps in the same transcript file are one snapshot, not two sources. Rule 1 asks for two *places*, and a place means a different system of record.

## Interaction with other skills

- **`did-it-actually`** verifies output against the *request* — did you do what was asked. `still-true` verifies claims against the *world* — is what you're saying about state currently true. A `did-it-actually` PASS on a status report full of stale items is a hollow pass.
- **`landed`** asks "did MY work reach its real destination". `still-true` asks "is my statement about ANY fact still valid". `landed` covers your own artefacts; `still-true` covers everyone's.
- **`resourceful`** bans premature surrender — the sin of not looking. `still-true` bans premature assertion — the sin of looking once, long ago. They stack: `resourceful` makes you climb, `still-true` makes you re-climb before you speak.
- **`briefing`** is a live-authority climb by construction (calendar + inbox, read fresh each morning). It is what a compliant `still-true` answer looks like.

## Reference index

- `references/authority-table.md` — the full class→authority table with the exact query per row.
- `references/negative-claims.md` — why the negative costs more, with the Boehringer / ERKNet / Booking post-mortem.
- `references/agent-findings.md` — how to instruct subagents and how to re-test their negatives.
- `scripts/doctor.sh` — verifies install + hook wiring.
- `hooks/stale_claim.py` — Stop hook that intercepts unverified pending claims.
- `hooks/install_hook.sh` — wires the hook into `~/.claude/settings.json`.
