# Ghép Hình Theo Ý — hướng dẫn cho Claude

Chỉ cần Python 3 + Pillow + ffmpeg (+ faster-whisper để căn giọng chính xác). Xem `README.md` cho người dùng.

## Quy trình 4 bước (người dùng làm việc với Claude trong chat)

1. **Người dùng dán kịch bản + giọng đọc** — thường vào hai thư mục nhận: `1-kich-ban/kich-ban.txt` và
   `2-voice/<file âm thanh>` (có thể dán thẳng trong chat). `git pull` trước.
   `python3 ghep.py moi <ten>` → chép kịch bản vào `du-an/<ten>/kich-ban.txt` (giữ nguyên từng chữ),
   `git mv` giọng đọc thành `du-an/<ten>/voice.<đuôi>`. Rồi **làm trống thư mục nhận**: `1-kich-ban/kich-ban.txt`
   thành file rỗng, `2-voice/` chỉ còn `README.md` — để lần sau dán video mới không lẫn.
   Tên dự án: người dùng đặt, nếu không thì Claude đặt theo nội dung — chữ thường không dấu, gạch nối (vd `loa-suy-nghi`).
   Thiếu một trong hai (kịch bản rỗng / chưa có file giọng) → nhắc người dùng, đừng đoán.

2. **Claude phân tích kịch bản → chia ý → gợi ý hình → viết `y.json`**, rồi chạy
   `python3 ghep.py can <ten>` (căn giọng, ra thời lượng từng ý + tự viết `y.md`).
   Trả lời người dùng bằng bảng ngắn: số ý, thời lượng, lời, gợi ý hình. Nhắc cách đặt tên hình (`03.jpg`).

3. **Người dùng dán hình cho từng ý.** Lưu thành `du-an/<ten>/hinh/NN.<đuôi>` theo đúng số ý
   (ý có nhiều hình: `03.jpg`, `03b.jpg`, `03c.jpg` — thời lượng ý chia đều). Chạy `python3 ghep.py kiem <ten>`,
   rồi `python3 ghep.py tobia <ten>` và **xem `xuat/to-bia.jpg`**: hình nào không khớp ý / mờ / có chữ watermark /
   sai hướng thì báo người dùng trước khi dựng.

4. **Claude edit = dựng video.** `python3 ghep.py dung <ten>` (bản nháp nhanh: `--nhap`, ý thiếu hình hiện ô trống).
   Soát kết quả: trích vài khung (`ffmpeg -ss <giây> -i xuat/<ten>.mp4 -frames:v 1 f.jpg`) ở giữa mỗi ý và ngay sau
   mỗi lần cắt, xem phụ đề có che mặt/chữ trong hình không, hình có khớp lời không. Chỉnh `y.json`
   (`chuyen_dong`, `vua_khung`, `vi_tri_phu_de`…) rồi dựng lại. Gửi MP4 cho người dùng (SendUserFile),
   commit các file của dự án (MP4 trong `xuat/` không commit — quá nặng).

Người dùng góp ý sau khi xem ("ý 4 đổi hình", "phụ đề lên cao", "ý 7 zoom ra") → sửa `y.json` / thay hình → dựng lại.
Đổi lời trong `y.json` hoặc thay giọng → chạy lại `can` trước khi dựng.

## Cách chia ý

- Một ý = một hình ảnh trên màn hình = một khoảnh khắc người xem *thấy* một điều mới.
  Cắt khi chủ thể / địa điểm / thời gian / cảm xúc đổi, khi có con số, nhân vật, đồ vật mới được nhắc tới.
- Độ dài mục tiêu **3–7 giây** lời đọc (khoảng 8–20 từ tiếng Việt, 7–16 từ tiếng Đức/Anh).
  Câu dài > 8 s → tách thành 2 ý; câu rất ngắn liền mạch → gộp. Câu móc (hook) đầu video nên là ý riêng, ngắn.
- `loi` của các ý ghép lại phải **đúng nguyên văn toàn bộ kịch bản, đúng thứ tự, không thiếu không thừa**
  (máy dùng nó để khớp với giọng đọc). Được tách giữa câu tại dấu phẩy nếu cần.
- Không có tiêu đề/ghi chú trong `loi` — chỉ những gì giọng đọc nói.

## Cách gợi ý hình

Mỗi ý viết:
- `y_chinh`: ý chính trong 3–8 chữ (tiếng Việt).
- `goi_y_hinh`: mô tả **một khung hình cụ thể** bằng tiếng Việt — chủ thể, hành động, bối cảnh, góc máy,
  ánh sáng/tâm trạng. Cụ thể đến mức người dùng đi tìm/tạo là ra ngay ("cận mặt cô gái 25 tuổi nhìn gương
  phòng tắm, đèn vàng buổi sáng, vẻ mệt mỏi"), không chung chung ("hình về sự mệt mỏi").
  Hình phải *minh họa đúng lời đang đọc*, không chỉ đúng chủ đề. Câu trừu tượng → hình ẩn dụ cụ thể.
- `phuong_an_khac` (không bắt buộc): phương án dễ kiếm hơn (ảnh stock, ảnh tư liệu thật, chữ lớn trên nền).
- `prompt`: prompt tạo ảnh AI **tiếng Anh**, một đoạn, kèm tỉ lệ khung (`vertical 9:16` / `16:9`),
  và phong cách thống nhất cho cả video (giống nhau ở mọi ý: cùng kiểu ảnh, bảng màu, ánh sáng, nhân vật
  lặp lại thì tả y hệt mỗi lần — tuổi, tóc, quần áo).
- `tu_khoa` (không bắt buộc): từ khóa tìm ảnh stock (tiếng Anh).
- Sự kiện/người/địa điểm có thật → ưu tiên gợi ý ảnh tư liệu thật, ghi rõ nên tìm ảnh gì.

## `y.json`

```json
{
  "tieu_de": "Chiếc loa suy nghĩ",
  "tom_tat": "1–2 câu: video nói gì, giọng điệu, phong cách hình thống nhất",
  "ngon_ngu": "vi",
  "khung": "9:16",
  "phu_de": true,
  "y": [
    {
      "so": 1,
      "loi": "Nguyên văn đoạn lời của ý này.",
      "y_chinh": "Câu hỏi mở đầu",
      "goi_y_hinh": "…",
      "phuong_an_khac": "…",
      "prompt": "…, vertical 9:16",
      "tu_khoa": "speaker, thoughts",
      "chuyen_dong": "zoom-in"
    }
  ]
}
```

Bắt buộc: `y[].so`, `y[].loi`. Còn lại không bắt buộc (mặc định trong ngoặc):

| Khóa | Ý nghĩa |
|---|---|
| `ngon_ngu` | `vi`, `de`, `en`… cho Whisper (tự nhận nếu bỏ trống) |
| `khung` | `9:16` (mặc định) · `16:9` · `1:1` · `4:5` |
| `fps` | 30 |
| `phu_de` | `true` — phụ đề từng cụm 2–4 từ theo đúng giọng |
| `kieu_phu_de` | `vien` (chữ trắng viền đen, mặc định) · `hop` (chữ trên hộp đen mờ) |
| `vi_tri_phu_de` | 0.72 — tâm phụ đề tính theo chiều cao (0 = trên cùng, 1 = dưới cùng) |
| `do_chuyen_dong` | 0.10 — mức zoom/lia của hiệu ứng Ken Burns |
| `chuyen_canh` | 0.3 — giây hòa hình giữa hai hình (0 = cắt thẳng) |
| `vua_khung` | `auto` · `cover` (lấp đầy, cắt bớt) · `contain` (giữ trọn hình, nền mờ). `auto` = `contain` khi tỉ lệ hình lệch nhiều so với khung. Đặt được cho từng ý |
| `duoi_giay` | 0.6 — giây giữ hình sau khi giọng kết thúc |
| `am_luong_nhac` | 0.12 — nếu có `nhac.mp3` trong thư mục dự án thì trộn làm nhạc nền |
| `y[].chuyen_dong` | `zoom-in` · `zoom-out` · `pan-left` · `pan-right` · `pan-up` · `pan-down` · `none`; hoặc mảng, một cái cho mỗi hình của ý. Bỏ trống = tự xoay vòng |

## Môi trường

`pip install -r requirements.txt` (faster-whisper cần `av<16`). Lần đầu tải model Whisper `small` (~500 MB).
Không có Whisper / không tải được model → `can` tự ước lượng theo độ dài chữ + khoảng lặng (kém chính xác hơn,
báo `do_chinh_xac: uoc-luong`). Font phụ đề: Inter (có dấu tiếng Việt), dự phòng DejaVu Sans.
