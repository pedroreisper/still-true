#!/usr/bin/env bash
# run-tests.sh — assert the still-true Stop hook blocks/allows correctly.
# Builds tiny transcript fixtures and feeds them to the hook via a Stop payload.
#
# The fixtures below deliberately contain typographic quotes (“ ” ‘ ’ « ») and
# literal backticks inside single-quoted strings — that is exactly what the hook
# has to parse. shellcheck reads them as mistakes, so silence those two checks
# for this file only.
# shellcheck disable=SC1112,SC2016
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/stale_claim.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

# build_transcript <file> <assistant_text> [tool_name] [tool_input_json] ...
# Emits a user prompt then an assistant message carrying <assistant_text> plus N
# tool_use blocks (so we can simulate live-authority checks in the current turn).
build_transcript() {
  python3 - "$@" <<'PY'
import json, sys
args = sys.argv[1:]
path, text = args[0], args[1]
content = [{"type": "text", "text": text}]
i = 2
while i + 1 < len(args):
    content.append({"type": "tool_use", "name": args[i], "input": json.loads(args[i + 1])})
    i += 2
recs = [
    {"type": "user", "message": {"content": "what is still open?"}},
    {"type": "assistant", "message": {"content": content}},
]
with open(path, "w") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")
PY
}

run_hook() {  # <transcript> [stop_hook_active] [ENV=VALUE]
  local t="$1" active="${2:-false}" envassign="${3:-}"
  if [ -n "$envassign" ]; then
    printf '{"transcript_path":"%s","stop_hook_active":%s}' "$t" "$active" \
      | env "$envassign" python3 "$HOOK" 2>/dev/null
  else
    printf '{"transcript_path":"%s","stop_hook_active":%s}' "$t" "$active" \
      | python3 "$HOOK" 2>/dev/null
  fi
}

assert_block() {  # <name> <transcript> [active] [env]
  local out; out="$(run_hook "$2" "${3:-false}" "${4:-}")"
  if printf '%s' "$out" | grep -q '"decision": *"block"'; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); printf '\033[31mFAIL\033[0m %s — expected BLOCK, got: %s\n' "$1" "${out:-<empty>}"
  fi
}
assert_allow() {  # <name> <transcript> [active] [env]
  local out; out="$(run_hook "$2" "${3:-false}" "${4:-}")"
  if printf '%s' "$out" | grep -q '"decision": *"block"'; then
    fail=$((fail+1)); printf '\033[31mFAIL\033[0m %s — expected ALLOW, got block\n' "$1"
  else
    pass=$((pass+1))
  fi
}

PT2="A fatura de 900 € à Boehringer nunca foi emitida. O invoice do ERKNet está por assinar."
EN2="The Boehringer invoice was never issued and the ERKNet form is still pending."

# 1. PT — two negative claims, ZERO verification → block
build_transcript "$TMP/t1.jsonl" "$PT2"
assert_block "pt-two-claims-no-verification" "$TMP/t1.jsonl"

# 2. EN — two negative claims, ZERO verification → block
build_transcript "$TMP/t2.jsonl" "$EN2"
assert_block "en-two-claims-no-verification" "$TMP/t2.jsonl"

# 3. two claims + Gmail `in:sent` search → allow (the authority was consulted)
build_transcript "$TMP/t3.jsonl" "$PT2" \
  "mcp__claude_ai_Gmail__search_threads" '{"q":"in:sent 4701202998"}'
assert_allow "claims-with-in-sent-search" "$TMP/t3.jsonl"

# 4. two claims + list_drafts → allow
build_transcript "$TMP/t4.jsonl" "$EN2" \
  "mcp__claude_ai_Gmail__list_drafts" '{"max_results":20}'
assert_allow "claims-with-list-drafts" "$TMP/t4.jsonl"

# 5. two claims + a Gmail search WITHOUT in:sent → allow (deliberately lenient)
build_transcript "$TMP/t5.jsonl" "$EN2" \
  "mcp__claude_ai_Gmail__search_threads" '{"q":"reisswolf.pt"}'
assert_allow "claims-with-any-gmail-search" "$TMP/t5.jsonl"

# 6. two claims + `git log` of the remote → allow
build_transcript "$TMP/t6.jsonl" "The change was never pushed and CI is still pending." \
  "Bash" '{"command":"git log origin/main --oneline -5"}'
assert_allow "claims-with-git-log" "$TMP/t6.jsonl"

# 7. two claims + WebFetch to a portal → allow
build_transcript "$TMP/t7.jsonl" "$EN2" \
  "WebFetch" '{"url":"https://portal.funder.example/status"}'
assert_allow "claims-with-portal-fetch" "$TMP/t7.jsonl"

# 8. two claims + a real file Read → allow (filesystem is a live authority)
build_transcript "$TMP/t8.jsonl" "$PT2" \
  "Read" '{"file_path":"/Users/x/Documents/FT-2026-12.pdf"}'
assert_allow "claims-with-real-file-read" "$TMP/t8.jsonl"

# 9. ONE claim only → allow (single pending item is normal conversation)
build_transcript "$TMP/t9.jsonl" "A fatura da Boehringer ainda não foi enviada."
assert_allow "single-claim-allowed" "$TMP/t9.jsonl"

# 10. overlapping patterns on ONE fact must merge into ONE claim → allow
#     "ainda não" + "não foi emitido" are two patterns describing one fact.
build_transcript "$TMP/t10.jsonl" "O invoice do ERKNet ainda não foi emitido."
assert_allow "overlapping-patterns-merge-pt" "$TMP/t10.jsonl"
#     "was never" + "never issued" likewise.
build_transcript "$TMP/t10b.jsonl" "The Boehringer invoice was never issued."
assert_allow "overlapping-patterns-merge-en" "$TMP/t10b.jsonl"

# 11. no claims at all → allow
build_transcript "$TMP/t11.jsonl" "Every item on the list is closed — checked Sent, 30-Jul 21:45."
assert_allow "no-claims" "$TMP/t11.jsonl"

# 12. claims only inside a fenced code block → allow
build_transcript "$TMP/t12.jsonl" "The catalogue the hook matches on:
\`\`\`
nunca foi emitida
está por assinar
never sent
\`\`\`
All handled."
assert_allow "claims-inside-fence" "$TMP/t12.jsonl"

# 13. claims only inside a \`> \` quote line → allow
build_transcript "$TMP/t13.jsonl" "You wrote:
> a fatura nunca foi emitida e o form está por submeter
and I have now confirmed both went out."
assert_allow "claims-inside-quote-line" "$TMP/t13.jsonl"

# 14. claims only inside inline code spans → allow (meta-discussion)
build_transcript "$TMP/t14.jsonl" 'O catálogo lista `ainda não` e `por assinar` como padrões.'
assert_allow "claims-inside-backticks" "$TMP/t14.jsonl"

# 15. claims only inside double quotes → allow
build_transcript "$TMP/t15.jsonl" 'The catalogue lists "never sent" and "still pending" as patterns.'
assert_allow "claims-inside-double-quotes" "$TMP/t15.jsonl"

# 16. claims only inside smart quotes / guillemets → allow
build_transcript "$TMP/t16.jsonl" 'O catálogo lista “por emitir” e «por assinar» como padrões.'
assert_allow "claims-inside-smart-and-guillemets" "$TMP/t16.jsonl"

# 17. a quoted MENTION must not swallow a real claim on the same line → block
build_transcript "$TMP/t17.jsonl" 'O catálogo lista `ainda não` — mas a fatura nunca foi emitida e o formulário está por submeter.'
assert_block "mention-does-not-swallow-line" "$TMP/t17.jsonl"

# 18. unbalanced delimiter (inch mark) must NOT bracket the claims away → block
build_transcript "$TMP/t18.jsonl" 'The 24" monitor invoice was never issued and the form is still pending.'
assert_block "unbalanced-double-quote" "$TMP/t18.jsonl"

# 19. markdown emphasis must not defeat the \b anchors → block
build_transcript "$TMP/t19.jsonl" '**A fatura nunca foi emitida** e o formulário **está por submeter**.'
assert_block "markdown-emphasis-claims" "$TMP/t19.jsonl"

# 20. typographic apostrophe still reads as a claim → block
build_transcript "$TMP/t20.jsonl" 'The invoice hasn’t been issued and the refund hasn’t been paid.'
assert_block "curly-apostrophe-claims" "$TMP/t20.jsonl"

# 21. Read of a session TRANSCRIPT is a snapshot, not a live authority → block
build_transcript "$TMP/t21.jsonl" "$PT2" \
  "Read" '{"file_path":"/Users/x/.claude/projects/-Users-x/9f2c.jsonl"}'
assert_block "transcript-read-is-not-verification" "$TMP/t21.jsonl"

# 22. Grep of a memory/ file is a snapshot too → block
build_transcript "$TMP/t22.jsonl" "$EN2" \
  "Grep" '{"pattern":"Boehringer","path":"/Users/x/.claude/projects/-Users-x/memory/"}'
assert_block "memory-grep-is-not-verification" "$TMP/t22.jsonl"

# 23. Bash grepping the transcript folder is a snapshot too → block
build_transcript "$TMP/t23.jsonl" "$PT2" \
  "Bash" '{"command":"grep -rl Boehringer ~/.claude/projects/"}'
assert_block "bash-transcript-grep-is-not-verification" "$TMP/t23.jsonl"

# 24. a subagent finding is a hypothesis, not evidence → block
build_transcript "$TMP/t24.jsonl" "$EN2" \
  "Agent" '{"prompt":"scan transcripts for open items"}'
assert_block "agent-output-is-not-verification" "$TMP/t24.jsonl"

# 25. the memory-graph MCP is a snapshot, not a live authority → block
build_transcript "$TMP/t25.jsonl" "$PT2" \
  "mcp__memory__search_nodes" '{"query":"Boehringer"}'
assert_block "memory-mcp-is-not-verification" "$TMP/t25.jsonl"

# 26. STILL_TRUE_DISABLE=1 turns the hook off entirely → allow
build_transcript "$TMP/t26.jsonl" "$PT2"
assert_allow "disable-env-var" "$TMP/t26.jsonl" "false" "STILL_TRUE_DISABLE=1"

# 27. STILL_TRUE_DISABLE=0 is NOT a disable → block
build_transcript "$TMP/t27.jsonl" "$EN2"
assert_block "disable-env-var-zero-is-off" "$TMP/t27.jsonl" "false" "STILL_TRUE_DISABLE=0"

# 28. stop_hook_active guard → allow (no infinite loop)
build_transcript "$TMP/t28.jsonl" "$PT2"
assert_allow "stop-hook-active-guard" "$TMP/t28.jsonl" "true"

# 29. mixed PT + EN claims in one report → block
build_transcript "$TMP/t29.jsonl" "Falta o mapa de kms. The ERKNet invoice was never signed."
assert_block "mixed-pt-en-claims" "$TMP/t29.jsonl"

# 30. the block message names the claims and the authority table
build_transcript "$TMP/t30.jsonl" "$PT2"
msg="$(run_hook "$TMP/t30.jsonl")"
if printf '%s' "$msg" | grep -q 'authority-table.md' \
   && printf '%s' "$msg" | grep -q 'Claims caught'; then
  pass=$((pass+1))
else
  fail=$((fail+1)); printf '\033[31mFAIL\033[0m block-message-content — got: %s\n' "${msg:-<empty>}"
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
