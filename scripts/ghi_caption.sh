#!/usr/bin/env bash
# Dán caption (du-an/<ten>/caption.txt) vào mô tả bản phát hành video-<ten>. Cần GH_TOKEN có quyền contents: write.
set -u
t="$1"; f="du-an/$t/caption.txt"
gh release view "video-$t" >/dev/null 2>&1 || { echo "chưa có bản phát hành video-$t"; exit 0; }
{
  echo "Video dựng tự động từ du-an/$t."
  if [ -s "$f" ]; then
    echo; echo "**Caption TikTok** (bấm nút copy ở góc khung):"; echo; echo '```'; cat "$f"; echo; echo '```'
  fi
} > /tmp/notes-$t.md
gh release edit "video-$t" --notes-file /tmp/notes-$t.md >/dev/null && echo "đã ghi caption cho video-$t"
