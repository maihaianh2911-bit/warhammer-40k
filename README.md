# Ghép Hình Theo Ý

Kịch bản + giọng đọc + hình của bạn → video MP4 (dọc 9:16 mặc định), mỗi hình hiện đúng lúc giọng đọc tới ý của nó,
có chuyển động nhẹ (zoom/lia), hòa hình khi chuyển và phụ đề chạy theo giọng.

## Cách làm (chat với Claude)

1. **Dán kịch bản + giọng đọc** vào chat (giọng: file mp3/wav/m4a). Đặt tên dự án nếu muốn.
2. **Claude phân tích kịch bản, chia ý, gợi ý hình cho từng ý** — mỗi ý có: lời đọc, thời lượng (đo từ giọng thật),
   mô tả hình nên dùng, phương án dễ kiếm hơn, prompt tiếng Anh để tạo ảnh AI. Bảng đầy đủ: `du-an/<ten>/y.md`.
3. **Dán hình cho từng ý** — trong chat ghi “ý 3” kèm hình, hoặc tải lên GitHub vào
   `du-an/<ten>/hinh/` với tên theo số ý: `01.jpg`, `02.png`, … Một ý nhiều hình: `03.jpg`, `03b.jpg`.
   Hình dọc, ngang, vuông đều được (hình lệch khung nhiều sẽ giữ trọn hình trên nền mờ).
4. **Claude soát hình rồi dựng video**, gửi MP4. Muốn sửa thì nhắn theo số ý:
   “ý 4 đổi hình này”, “ý 7 zoom ra”, “phụ đề cao lên”, “bỏ phụ đề”, “làm bản 16:9”, “thêm nhạc nền” (gửi file nhạc).

Chưa đủ hình vẫn xem thử được: Claude dựng **bản nháp**, ý thiếu hình hiện ô ghi gợi ý.

## Thư mục một dự án

```
du-an/<ten>/
  kich-ban.txt     kịch bản bạn dán
  voice.mp3        giọng đọc
  y.json           các ý + gợi ý hình (Claude viết)
  y.md             bảng ý + gợi ý hình để đọc
  thoi-gian.json   thời điểm từng từ, từng ý trong giọng đọc (máy đo)
  hinh/01.jpg …    hình của từng ý
  nhac.mp3         (không bắt buộc) nhạc nền
  xuat/            video + ảnh soát (không lưu lên GitHub)
```

## Dựng không cần chat

**Actions → “Ghép Hình Theo Ý — dựng video” → Run workflow** → nhập tên dự án → video ở mục *Artifacts* của lượt chạy.

Trên máy riêng:

```bash
pip install -r requirements.txt     # cần ffmpeg
python3 ghep.py can <ten>           # căn giọng → thời lượng từng ý
python3 ghep.py kiem <ten>          # ý nào còn thiếu hình
python3 ghep.py tobia <ten>         # ảnh soát tất cả ý
python3 ghep.py dung <ten>          # dựng video (--nhap: bản nháp nhanh)
```

Tùy chỉnh (khung hình, phụ đề, chuyển động, nhạc…): các khóa trong `y.json`, xem bảng ở `CLAUDE.md`.
