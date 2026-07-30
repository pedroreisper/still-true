# Why the negative costs more

## The post-mortem

**30 July 2026.** A list of 76 open items, produced from session transcripts and memory files. Three items were wrong. All three were false negatives, and all three failed the same way.

| Reported | Reality | Gap |
|---|---|---|
| "€900 Boehringer invoice never issued" | sent 3-Jul to `fornecedores_bi_pt@reisswolf.pt` — FT 2026/12, PO 4701202998, PDF on disk | 27 days |
| "€60 ERKNet invoice still unsigned, needs returning" | signed and returned 16-Jul | 14 days |
| "Booking refund draft never sent" | sent 10-Jun | 50 days |

Three out of 76 is 4%. It reads like a good score. It isn't, for three reasons:

1. Each wrong item is an **instruction to redo work that is done**. The cost isn't the wrong sentence; it's the hour spent re-issuing an invoice that has been in the supplier's system for a month, or the embarrassment of chasing a client who already paid.
2. The user cannot tell *which* 4%. So the rational response is to re-check all 76. The list's value goes to zero.
3. The three errors were not random. They were **the same error three times**, which means the process — not the sample — was broken.

## The three layers of the failure

### Layer 1 — transcripts treated as state

The source was a `.jsonl` from 22 June containing the sentence "a fatura à Boehringer ainda não foi emitida". That sentence was **true on 22 June**. It was carried forward into a present-tense claim on 30 July without anyone asserting, or checking, that nothing happened in the intervening 38 days.

A transcript is a photograph. Photographs are evidence of a moment, not of now. The correct reading of that sentence is not "this is pending" but "**this was pending on 22 June — go and find out what happened since**".

### Layer 2 — the negative treated as cheap

There has long been an implicit discipline around positive claims: don't say "I sent it" without checking the Sent folder. There was no equivalent discipline for "it still needs sending".

This is exactly backwards. Compare the two errors:

| | False positive ("I sent it", but didn't) | False negative ("still needs sending", but sent) |
|---|---|---|
| Who discovers it | you, or the recipient's silence | nobody, until duplicated work lands |
| Cost of discovery | one follow-up | a duplicate invoice, a chased client, a re-signed form |
| Effect on the rest of the report | localised | contaminates every item |
| Feels like | carelessness | diligence |

The last row is the trap. A negative claim *feels* conservative — you're flagging a risk, being helpful, erring on the side of caution. But there is no "safe side" here. Flagging a done thing as undone is not caution; it is a false alarm with a work order attached.

### Layer 3 — subagent output accepted as fact

The finding "never issued" came from an agent that had read transcripts and nothing else. It never touched the Sent folder. Its report said "no evidence of the invoice being sent", which is true and useless, and it was relayed as "never issued", which is false. See `agent-findings.md`.

## The rule that would have caught all three

> **Before declaring anything pending, run a POSITIVE search using the strong keys of the subject, in at least two places.**

Not "search for evidence that it's still open" — that's unfalsifiable. Search for evidence that it **closed**, and fail to find it.

For the Boehringer item, the strong keys were sitting in the same memory file that produced the claim:

```
in:sent 4701202998            → 1 thread, 3-Jul          ← would have caught it
in:sent reisswolf.pt          → 1 thread, 3-Jul          ← would have caught it
find ~ -iname '*2026*12*.pdf' → the invoice PDF, mtime 3-Jul
```

Three seconds of tool calls. The information was not hard to reach; it was simply never asked for, because a negative claim didn't feel like it needed asking.

## Strong keys, by class

A "strong key" is a token that appears in the real artefact and nowhere else. Search on those, not on your own paraphrase.

| Class | Strong keys |
|---|---|
| invoice | invoice number, PO number, amount, supplier portal address |
| email | recipient domain, subject fragment, attachment filename |
| grant / application | call code, proposal number, funder domain, portal reference |
| document | filename stem, output directory, the exact title |
| payment | amount + date window, counterparty name as the bank writes it |
| code | branch name, commit subject, file path, issue number |

Your own description of the thing ("the Boehringer invoice") is a **weak key** — it is what you called it, not what it is called. Weak keys return zero hits and zero hits get misread as absence.

## Two places, and what "place" means

Two greps of the same transcript folder is one place. Two searches of Gmail with different queries is arguably one place — better than one, but the two-place rule means two *systems of record*:

- Gmail Sent **and** the filesystem.
- The bank statement **and** the invoicing portal.
- `git log origin/main` **and** the CI run list.
- The funder's portal **and** the inbox.

Different systems fail independently. That is the whole point.

## Phrases that require the drill

If you are about to type any of these, the drill is mandatory — positive search, strong key, two places, as-of stamp:

**PT** — falta, em falta, por enviar, por fazer, por assinar, por emitir, por submeter, por pagar, está pendente, continua pendente, nunca foi, não foi enviado, ainda não, sem resposta, não há registo, zero menções.

**EN** — never sent, was never, has never been, still pending, still open, still outstanding, hasn't been, haven't been, no evidence of, no record of, no trace of, not yet, outstanding, zero mentions.

## What a compliant answer looks like

Bad:

> The €900 Boehringer invoice was never issued — you need to send it.

Good:

> Boehringer €900: **issued and sent** — Gmail Sent, 30-Jul 21:45 (FT 2026/12, PO 4701202998, to `fornecedores_bi_pt@reisswolf.pt`, 3-Jul). PDF also on disk, mtime 3-Jul. Nothing to do.

Also good, when the check genuinely can't be run:

> Boehringer €900: **last seen unissued 22-Jun** (transcript), not re-verified — Gmail is not authenticated in this session. One `in:sent 4701202998` would settle it.

The second one is honest about its own age. That is the whole deliverable of this skill.
