# The authority table

For every class of fact there is exactly one system that changes when the world changes. That is the **live authority**. Everything else — transcripts, memory files, your own recollection of a session, the existence of an artefact that *implies* an action — is derived, dated, or circumstantial.

Rule of thumb for finding the authority yourself: **ask what would have changed if the thing had happened.** If the answer is "a row would appear in X", then X is the authority. If the answer is "nothing observable", you are about to assert something unfalsifiable — say so instead.

---

## Communication

| Claim | Live authority | Exact check | Not proof |
|---|---|---|---|
| email sent | Gmail Sent | `mcp__claude_ai_Gmail__search_threads` with `in:sent <strong-key>` | a transcript saying you drafted it |
| email *not* sent | Gmail Sent **and** Drafts | `in:sent <key>` (empty) **plus** `list_drafts` (still there) | absence in one of the two |
| draft still open | `mcp__claude_ai_Gmail__list_drafts` | list, match on subject/recipient | "I created a draft" in an old turn |
| reply received | `in:inbox from:<domain>` **and** the thread itself | `get_thread` on the thread id | your inbox summary from last week |
| message read by them | nothing — unfalsifiable | — | read receipts you don't have |

**Strong keys for email**: recipient domain (`fornecedores_bi_pt@reisswolf.pt`), invoice number (`FT 2026/12`), PO number (`4701202998`), amount (`900`), attachment filename. Search on the key, not on your own description of the message. Your description was written by the same process that got the state wrong.

---

## Documents and files

| Claim | Live authority | Exact check | Not proof |
|---|---|---|---|
| document produced | filesystem | `find ~ -iname '*<key>*' -newermt '-90 days'` | "I generated it" in an earlier session |
| document is current | `stat` / `ls -l` mtime | compare mtime against the event it should follow | the file existing |
| PDF actually renders | open it / read it | `Read` the file, or render page 1 | a successful build log |
| uploaded to Drive | Drive MCP | `mcp__claude_ai_Google_Drive__search_files` | a local copy existing |
| signed | the signed artefact itself | open it, look for the signature block | an email saying you'd sign it |

---

## Money

| Claim | Live authority | Exact check | Not proof |
|---|---|---|---|
| payment made | bank statement / bank notification email | statement export, or `in:inbox from:<bank> <amount>` | the invoice having been issued |
| payment received | bank statement | same | the client saying "paid today" |
| invoice issued | the invoicing system + the sent email | portal listing, `in:sent <invoice-no>` | the PDF existing on disk |
| direct debit active | the bank's DD list, or the vendor's portal | portal check | the mandate having been signed |
| tax obligation open | the tax portal | log in, read the current position | last year's letter |

The invoice PDF on disk is the single most seductive false proof in this whole table. Producing a document and transmitting it are two different events, days apart, and only the second one discharges the obligation.

---

## Code and infrastructure

| Claim | Live authority | Exact check | Not proof |
|---|---|---|---|
| code shipped | `git log` of the **remote** default branch | `git log origin/main --oneline -5` after `git fetch` | a clean local working tree |
| change merged | the PR state on the host | `gh pr view <n> --json state,mergedAt` | the branch existing |
| build green | CI on the remote commit | `gh run list --branch main --limit 3` | tests passing locally |
| deployed | the production URL | `WebFetch` the live URL and look for the change | a successful deploy log line |
| package published | the registry | `npm view <pkg> version` / registry API | a green publish job |
| hook installed | `~/.claude/settings.json` **and** a real invocation | grep settings, then trigger it | the hook file existing |

---

## Process and bureaucracy

| Claim | Live authority | Exact check | Not proof |
|---|---|---|---|
| form submitted | the portal, or the confirmation email | log in; `in:inbox <portal-domain>` | the file being filled in |
| application decided | the funder's portal | log in and read the status | the absence of a decision email |
| application still open | the call page / portal deadline | fetch the page | your note of the deadline |
| registration done | the registry's public search | search the registry | the receipt of the fee |
| appointment booked | Calendar API | `mcp__claude_ai_Google_Calendar__search_events` | the email proposing a time |
| deadline still stands | Calendar + the source that set it | both | memory |

---

## Anti-proofs — the seven that keep recurring

1. **The artefact implies the act.** The PDF exists, therefore it was sent. It does not.
2. **The draft implies the send.** A draft in the folder is proof of the *opposite*.
3. **The local tree implies the remote.** Committed is not pushed; pushed is not merged; merged is not deployed.
4. **The intention implies the act.** "I'll do X next" in an old transcript says nothing about whether X happened.
5. **The absence of a reply implies no decision.** Portals decide silently all the time.
6. **One search implies exhaustion.** One query with the wrong key finds nothing and proves nothing.
7. **The agent's summary implies the fact.** See `agent-findings.md`.

---

## The as-of stamp

Once you have checked, say so in a form the reader can date:

```
<claim> — <source>, <timestamp> (<key you searched on>)
```

Examples:

- `Boehringer invoice: sent — Gmail Sent, 30-Jul 21:45 (PO 4701202998, 3-Jul, to fornecedores_bi_pt@reisswolf.pt)`
- `KEC manuscript: not on the remote — git log origin/main, 30-Jul 21:47 (no commits since 12-Jul)`
- `SPN grant: undecided — funder portal, 30-Jul 21:50 (status "em avaliação")`

And when you have **not** checked, stamp the stale evidence rather than upgrading it:

- `ERKNet invoice: last seen unsigned 22-Jun (transcript) — not re-verified`

That line is useful. "ERKNet invoice still needs signing" is a fabrication wearing the same clothes.
