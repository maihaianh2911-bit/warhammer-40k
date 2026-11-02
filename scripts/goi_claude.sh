#!/usr/bin/env bash
# Gọi tác vụ Claude Code ngay (API trigger của tác vụ) khi trang web vừa gửi kịch bản cần chia ý.
# Cần secret CLAUDE_TASK_URL (Fire URL của tác vụ) và CLAUDE_TASK_TOKEN. Không bao giờ làm workflow lỗi.
set -u
[ -n "${CLAUDE_TASK_URL:-}" ] && [ -n "${CLAUDE_TASK_TOKEN:-}" ] || { echo "Chưa cài CLAUDE_TASK_URL / CLAUDE_TASK_TOKEN — nhắn Claude “đã gửi” trong chat"; exit 0; }
WHY=$(printf '%s' "${1:-}" | python3 -c 'import json,sys;print(json.dumps({"text":sys.stdin.read()[:300]}))')
CODE=$(curl -s -o /tmp/goi.json -w '%{http_code}' --max-time 30 -X POST "$CLAUDE_TASK_URL" \
  -H "Authorization: Bearer $CLAUDE_TASK_TOKEN" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" -d "$WHY")
case "$CODE" in
  2*) echo "Đã gọi Claude: $(python3 -c "import json;print(json.load(open('/tmp/goi.json')).get('claude_code_session_url',''))" 2>/dev/null)" ;;
  *)  echo "::warning::Gọi Claude không được (HTTP $CODE)"; head -c 300 /tmp/goi.json; echo ;;
esac
exit 0
