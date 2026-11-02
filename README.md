# Ghép Hình Theo Ý

Kịch bản + giọng đọc + ảnh/video bạn tự tìm → video MP4 (dọc 9:16 mặc định). Mỗi ảnh/video hiện đúng lúc giọng đọc
tới ý của nó; ảnh có chuyển động nhẹ (zoom/lia), hòa hình khi chuyển, phụ đề chạy theo giọng.

## Cách làm (đơn giản nhất)

Mở trang **https://maihaianh2911-bit.github.io/warhammer-40k/** (lần đầu: dán mã GitHub theo hướng dẫn trên trang).

1. **+ Video mới** → dán kịch bản → chọn file giọng đọc → **Gửi cho Claude chia ý** → nhắn Claude “đã gửi”.
2. Các ý hiện ra, mỗi ý có gợi ý nên tìm hình gì → thả / dán (Ctrl+V) ảnh hoặc video vào khung của ý.
3. Bấm **Dựng video** → GitHub tự dựng (3–6 phút) → video hiện ở cuối trang, bấm **Tải MP4 về máy**.

Bật trang một lần: **Settings → Pages → Source: GitHub Actions**.

## Cách làm qua GitHub (cách cũ)

1. **Dán kịch bản** vào `1-kich-ban/kich-ban.txt` (bấm file → cây bút ✏️ → dán → **Commit changes**).
2. **Tải giọng đọc** vào `2-voice/` (**Add file → Upload files** → kéo file mp3/wav/m4a → **Commit changes**).
3. **Nhắn Claude “đã dán xong”.** Claude chuyển kịch bản + giọng vào một dự án `du-an/<ten>/`, làm trống lại hai
   thư mục trên (để lần sau dán video mới), rồi **phân tích kịch bản, chia ý, gợi ý hình cho từng ý**: lời đọc,
   nghĩa tiếng Việt, thời lượng (đo từ giọng thật), nên tìm hình gì, phương án dễ kiếm hơn, từ khóa tìm kiếm.
   Bảng tất cả ý: `du-an/<ten>/y.md`.
4. **Dán ảnh/video vào ô của từng ý.** Mỗi ý có một ô riêng: `du-an/<ten>/hinh/01-…`, `02-…`, …
   Bấm vào ô → đọc gợi ý ngay bên dưới → **Add file → Upload files** → kéo ảnh/video vào → **Commit changes**.
   - Tên file tùy ý. Một ô nhiều file → chạy lần lượt theo tên, chia đều thời lượng của ý.
   - Ảnh dọc, ngang, vuông đều được (lệch khung nhiều sẽ giữ trọn trên nền mờ).
   - Video: tắt tiếng, lấy từ đầu clip, ngắn hơn ý thì lặp lại. GitHub web nhận file tối đa 25 MB.
5. **Nhắn Claude “dán hình xong”** → Claude soát hình rồi dựng video, gửi MP4. Muốn sửa thì nhắn theo số ý:
   “ý 4 đổi hình”, “ý 7 video lấy từ giây 12”, “phụ đề cao lên”, “bỏ phụ đề”, “làm bản 16:9”, “thêm nhạc nền”.

Kịch bản, giọng, hình cũng có thể gửi thẳng trong chat.
Chưa đủ hình vẫn xem thử được: Claude dựng **bản nháp**, ý thiếu hình hiện ô ghi gợi ý.

## Thư mục một dự án

```
du-an/<ten>/
  kich-ban.txt     kịch bản
  voice.mp3        giọng đọc
  y.md             bảng tất cả ý + gợi ý hình
  hinh/01-…/       ô dán ý 1: README.md (lời, nghĩa, gợi ý) + ảnh/video bạn dán
  hinh/02-…/       ô dán ý 2 …
  y.json           dữ liệu các ý (Claude viết)
  thoi-gian.json   thời điểm từng từ, từng ý trong giọng đọc (máy đo)
  nhac.mp3         (không bắt buộc) nhạc nền
  xuat/            video + ảnh soát (không lưu lên GitHub)
```

## Dựng không cần chat

**Actions → “Ghép Hình Theo Ý — dựng video” → Run workflow** → nhập tên dự án → video ở mục *Artifacts* của lượt chạy.

Trên máy riêng:

```bash
pip install -r requirements.txt     # cần ffmpeg
python3 ghep.py can <ten>           # căn giọng → thời lượng từng ý (+ tạo ô dán)
python3 ghep.py kiem <ten>          # ý nào còn thiếu hình
python3 ghep.py tobia <ten>         # ảnh soát tất cả ý
python3 ghep.py dung <ten>          # dựng video (--nhap: bản nháp nhanh)
```

Tùy chỉnh (khung hình, phụ đề, chuyển động, nhạc…): các khóa trong `y.json`, xem bảng ở `CLAUDE.md`.
