#!/usr/bin/env bash
# doctor.sh — verify the still-true skill install + hook wiring.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS="${HOME}/.claude/settings.json"

PASS="\033[32m✓\033[0m"
WARN="\033[33m⚠\033[0m"
FAIL="\033[31m✗\033[0m"

ok=0; warn=0; bad=0

check () {
  local cond="$1" msg="$2" hint="${3:-}"
  if eval "$cond"; then
    printf '%b %s\n' "$PASS" "$msg"
    ok=$((ok+1))
  else
    printf '%b %s\n' "$FAIL" "$msg"
    [ -n "$hint" ] && printf '    hint: %s\n' "$hint"
    bad=$((bad+1))
  fi
}

soft_check () {
  local cond="$1" msg="$2" hint="${3:-}"
  if eval "$cond"; then
    printf '%b %s\n' "$PASS" "$msg"
    ok=$((ok+1))
  else
    printf '%b %s\n' "$WARN" "$msg"
    [ -n "$hint" ] && printf '    hint: %s\n' "$hint"
    warn=$((warn+1))
  fi
}

printf '── still-true doctor ──\n\n'

check "[ -f '$SKILL_DIR/SKILL.md' ]" "SKILL.md present"
check "[ -f '$SKILL_DIR/references/authority-table.md' ]" "authority-table reference present"
check "[ -f '$SKILL_DIR/references/negative-claims.md' ]" "negative-claims reference present"
check "[ -f '$SKILL_DIR/references/agent-findings.md' ]" "agent-findings reference present"
check "[ -f '$SKILL_DIR/hooks/stale_claim.py' ]" "stale_claim.py hook present"
check "[ -x '$SKILL_DIR/hooks/stale_claim.py' ]" "stale_claim.py is executable" "chmod +x $SKILL_DIR/hooks/stale_claim.py"
check "python3 -c \"import ast,sys; ast.parse(open('$SKILL_DIR/hooks/stale_claim.py').read())\"" "stale_claim.py parses"

if [ -f "$SETTINGS" ]; then
  if grep -q 'stale_claim.py' "$SETTINGS" 2>/dev/null; then
    printf '%b Stop hook wired in %s\n' "$PASS" "$SETTINGS"
    ok=$((ok+1))
  else
    printf '%b Stop hook NOT wired (proactive blocking disabled)\n' "$WARN"
    printf '    hint: bash %s/hooks/install_hook.sh\n' "$SKILL_DIR"
    warn=$((warn+1))
  fi
else
  printf '%b ~/.claude/settings.json missing (skill works manually, hook disabled)\n' "$WARN"
  warn=$((warn+1))
fi

if [ "${STILL_TRUE_DISABLE:-}" = "" ]; then
  printf '%b STILL_TRUE_DISABLE unset (hook active)\n' "$PASS"
  ok=$((ok+1))
else
  printf '%b STILL_TRUE_DISABLE=%s — hook is disabled in this shell\n' "$WARN" "$STILL_TRUE_DISABLE"
  warn=$((warn+1))
fi

soft_check "python3 -c 'import re,json,sys,os' 2>/dev/null" "python3 stdlib OK"

printf '\n'
printf 'summary: %s pass, %s warn, %s fail\n' "$ok" "$warn" "$bad"
[ "$bad" -eq 0 ]
