# Subagent findings are hypotheses

An agent returns a summary, not evidence. You did not watch it work, you cannot see which tools it used unless it tells you, and its conclusion arrives in confident prose regardless of how thin the search behind it was. Relaying that prose as fact is how "no evidence of the invoice in the transcripts" became "the invoice was never issued".

## The failure, concretely

The agent that produced the Boehringer error was asked to scan session transcripts for open items. It did exactly that, correctly. It reported:

> "€900 Boehringer invoice — no mention of it being issued; appears still pending."

Two defects, neither the agent's fault:

1. **The brief never named a live authority.** It was pointed at transcripts, so transcripts are what it searched. A search of the wrong corpus returns a true statement about the wrong corpus.
2. **The hedge was stripped in relay.** "No mention … appears still pending" became "never issued". Every rewrite of a negative finding tends to lose its qualifier, because qualifiers read as noise in a 76-item list.

## Rule: instruct the cross-check in the brief

Never dispatch a status-scanning agent without naming the authority it must consult and requiring it to report which one it used.

Bad brief:

```
Scan my session transcripts and list everything still pending.
```

Good brief:

```
Scan my session transcripts for candidate open items.

For EACH candidate, before listing it as pending, cross-check the LIVE authority:
  - email/invoice/document sent  → Gmail `in:sent <strong key>` AND `list_drafts`
  - file produced                → find/ls on disk
  - payment                      → bank notification email
  - code                         → git log origin/main
Search on the STRONG KEY (PO number, invoice number, recipient domain, filename),
not on my description of the item.

Report each item in this form:
  <item> | <status> | <authority checked> | <query run> | <as-of timestamp>

If you could not reach the live authority for an item, mark it
UNVERIFIED-SINCE <date of the snapshot>. Do not write "pending" for it.
```

The last paragraph matters most. Given no other option, an agent will resolve "couldn't check" into "pending", because "pending" is the shape the deliverable wants. Give it a third bucket and it will use it.

## Rule: re-test the negatives yourself

Positives you can usually take on trust — an agent that says "found it, here's the thread id" has handed you a falsifiable artefact. Negatives you cannot: "never", "doesn't exist", "zero mentions", "no evidence of", "nunca", "não há registo" are claims about the whole search space, and their truth depends entirely on the query and the corpus, neither of which you saw.

Before relaying any negative from an agent:

1. **Is there a live authority for this class?** If yes and the agent didn't name it, the finding doesn't count.
2. **Which key did it search on?** If it searched your paraphrase instead of the invoice number, re-run with the number.
3. **Run one direct query yourself.** One. That is the whole cost of not being wrong.

If the agent's report doesn't name a live source, treat the item as UNVERIFIED, not as pending.

## Rule: don't launder confidence

An agent's certainty is an artefact of its prose style, not of its evidence. Three specific launderings to watch for:

| Agent said | Do not write | Write |
|---|---|---|
| "no mention in the transcripts" | "was never issued" | "not mentioned in transcripts since 22-Jun; Sent folder not checked" |
| "appears to still be open" | "is still open" | "open as of the 22-Jun snapshot; unverified" |
| "I found no evidence of payment" | "unpaid" | "no payment evidence in <corpus>; bank statement not checked" |
| "zero mentions of X" | "X doesn't exist" | "zero mentions in <corpus> searched on <key>" |

The pattern: keep the corpus and the key in the sentence. A negative that names its corpus is a finding. A negative that has shed its corpus is a fabrication.

## Fan-out doesn't fix it

Spawning five agents in parallel produces five summaries with the same defect, and their agreement is not corroboration — they read the same transcripts. Independence requires *different corpora*, not different context windows.

If you want real corroboration from a fan-out, split by authority, not by topic:

- agent A → the transcripts (candidate generation)
- agent B → Gmail Sent + Drafts (the send authority)
- agent C → filesystem (the artefact authority)

Then an item is pending only when A flags it **and** B and C fail to find it, each naming the query it ran.

## The one-line test

Before relaying any negative finding from an agent, ask:

> **What query, against what live system, at what time, produced this absence?**

If you can't answer all three, you don't have a finding. You have a hypothesis wearing a report's formatting.
