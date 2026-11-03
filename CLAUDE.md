# Ghép Hình Theo Ý — hướng dẫn cho Claude

Chỉ cần Python 3 + Pillow + ffmpeg (+ faster-whisper để căn giọng chính xác). Xem `README.md` cho người dùng.

## Cách làm chính: trang web trên GitHub Pages

Trang **https://maihaianh2911-bit.github.io/warhammer-40k/** (nguồn `web/index.html`, đăng bằng workflow `trang-web.yml`).
Người dùng đăng nhập bằng mã GitHub (fine-grained, Contents: Read and write); trang đọc/ghi thẳng file trong repo:

- `du-an/<ten>/trang-thai.json`: `ten`, `trang_thai`, `loi_nhan` (hiện thành băng trên trang), `video {url, ten}`, `cap_nhat`.
  Ghi bằng `python3 trang.py trang-thai <ten> <gia_tri> [--loi-nhan "…"] [--video URL]`.
- `du-an/<ten>/kich-ban.txt`, `du-an/<ten>/voice.<đuôi>`: người dùng dán trên trang.
- `du-an/<ten>/hinh/NN-…/`: ảnh/video người dùng thả vào từng ý (tên file `01-<tên gốc>`, `02-…`).
- `trang_thai`: `nhap` → `cho_chia_y` (người dùng bấm gửi) → `dang_chia_y` → `chia_y_xong` → `cho_dung` (bấm “Dựng video”)
  → `dang_dung` → `xong` / `loi`.

**Chia ý (việc của Claude)** — người dùng nhắn “đã gửi”: `git pull` → dự án nào `cho_chia_y` → `trang-thai … dang_chia_y`
(commit + push để trang hiện) → chia ý, viết `y.json` → `python3 ghep.py can <ten>` (tạo `thoi-gian.json`, `y.md`, ô `hinh/NN-…/`)
→ `trang-thai … chia_y_xong` → commit + push. Trang tự hiện các ý (tự kiểm tra mỗi 20 giây).
Tác vụ Claude Code tự chạy (workflow `bao-claude.yml` gọi qua secret `CLAUDE_TASK_URL`/`CLAUDE_TASK_TOKEN`) làm đúng việc này
cho mọi dự án `cho_chia_y`, đẩy thẳng lên `main`, rồi dừng; không có dự án nào chờ thì dừng ngay. Không hỏi lại người dùng:
thiếu kịch bản/giọng → ghi `loi_nhan` giải thích trong `trang-thai.json` và trả về `nhap`.

**Chia ý trước khi có giọng** (người dùng nhờ Claude viết kịch bản): tạo `du-an/<ten>/` với `kich-ban.txt`, `y.json`,
`caption.txt`, `trang-thai.json` = `chia_y_xong` + `loi_nhan` nhắc tải giọng, chạy `python3 ghep.py bang <ten>` (tạo ô dán),
push. Trang cho tải giọng ở phần 1 cả khi đã chia ý; tải giọng mới thì trang xóa `thoi-gian.json`, `ghep.py dung` tự
chạy `can` lúc dựng. Giọng phải đọc đúng từng chữ kịch bản.

**Dựng video (tự động)**: bấm “Dựng video” → workflow `tu-dung.yml` dựng (`ghep.py dung --cho-phep-thieu`), đăng MP4 vào
bản phát hành `video-<ten>`, ghi `xong` + link. Người dùng muốn chỉnh (zoom, phụ đề, video lấy từ giây…) → Claude sửa
`y.json`, commit, rồi `trang-thai … cho_dung` + push để workflow dựng lại. Workflow lỗi → `trang_thai: loi` + `loi_nhan`.

## Trang phụ: Xưởng Ghép Hình trên claude.ai (cần đăng nhập Claude)

Người dùng làm mọi thứ trên trang **https://claude.ai/artifact/7HEbk3SNPfywFCm2dW2m8u** (nguồn: `trang/xuong-ghep-hinh.html`;
sửa trang → publish lại đúng URL đó). Họ chỉ nhắn trong chat kiểu “đã gửi”. Dữ liệu ở db của trang (công cụ `ArtifactData`):

- `du_an/<ten>`: `ten`, `kich_ban`, `voice` `{id, ten, b64}`, `trang_thai`, `loi_nhan` (Claude nhắn hiện thành băng trên trang),
  `video` `{id, ten, ghi_chu}`. `<ten>` của dự án trên trang = tên thư mục `du-an/<ten>/`.
- `du_an/<ten>/y/NN`: `so, loi, nghia, y_chinh, goi_y_hinh, phuong_an_khac, tu_khoa, tu_khoa_en, bat_dau, ket_thuc,
  media[{id, ten, kieu: anh|video, b64, type}]`.
- `trang_thai`: `nhap` → `cho_chia_y` (người dùng bấm gửi) → `dang_chia_y` → `chia_y_xong` (Claude ghi xong các ý)
  → `cho_dung` (người dùng bấm gửi hình) → `dang_dung` → `xong` (có video). Gửi lại hình sau `xong` → `cho_dung` lần nữa.
- Asset: trang lưu png/jpeg/gif/webp/mp4/webm nguyên dạng; còn lại (giọng đọc, .mov, .heic…) lưu dạng **base64 text**
  (`b64: true`). Tải: `Artifact` `action: read`, `url`, `path: <id>` → file trong scratchpad; giải: `python3 trang.py giai`.

**Khi người dùng nhắn “đã gửi”**: `ArtifactData list du_an` → dự án nào `cho_chia_y` / `cho_dung`.

- `cho_chia_y`: ghi `trang_thai: dang_chia_y` → tải giọng, giải base64 thành `du-an/<ten>/voice.<đuôi>`, lưu `kich_ban`
  thành `du-an/<ten>/kich-ban.txt` → chia ý, viết `y.json`, `python3 ghep.py can <ten>` →
  `python3 trang.py day-y <ten> <thư mục>` → `ArtifactData batch` set `du_an/<ten>/y/NN` (file_path từng file) cùng
  `du_an/<ten>` `trang_thai: chia_y_xong`. Commit + push repo.
- `cho_dung`: ghi `dang_dung` → `ArtifactData list du_an/<ten>/y` với `out_dir` → tải mọi `media[].id` (Artifact read
  `path`) vào một thư mục → `python3 trang.py nhan-y <ten> <dump/du_an/<ten>/y> <thư mục asset>` → soát (`tobia`) →
  `python3 ghep.py dung <ten> --toi-da-mb 19` (thiếu hình: thêm `--nhap`) → tải MP4 lên trang
  (`Artifact` publish `url`, `file_path`, `asset: true`) → update `du_an/<ten>`: `video {id, ten}`, `trang_thai: xong`.
  Gửi MP4 cả trong chat (SendUserFile). Commit + push (hình vào repo, MP4 không).
- Có vấn đề (hình không khớp, file hỏng) → ghi `loi_nhan` cho người dùng thấy trên trang, và nói trong chat.

Cách cũ (dán qua thư mục GitHub) vẫn dùng được, xem bên dưới.

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
   `can` (và `bang`) tự tạo **ô dán** cho từng ý: thư mục `hinh/NN-<ten-y>/` có `README.md` ghi lời, nghĩa,
   thời lượng, gợi ý hình, từ khóa — người dùng mở ô trên GitHub là thấy cần tìm gì và tải lên ngay tại đó.
   Commit + push ngay để ô dán hiện trên GitHub. Trả lời người dùng bằng bảng ngắn: số ý, giây, nghĩa, gợi ý hình.

3. **Người dùng tự tìm ảnh / video và dán vào ô của từng ý** (`hinh/NN-…/`, tên file tùy ý; nhiều file → chạy theo
   thứ tự tên, chia đều thời lượng ý). Hình gửi trong chat thì Claude lưu vào đúng ô. `git pull`, chạy `python3 ghep.py kiem <ten>`,
   rồi `python3 ghep.py tobia <ten>` và **xem `xuat/to-bia.jpg`**: hình nào không khớp ý / mờ / có chữ watermark /
   sai hướng thì báo người dùng trước khi dựng.

4. **Claude edit = dựng video.** `python3 ghep.py dung <ten>` (bản nháp nhanh: `--nhap`, ý thiếu hình hiện ô trống).
   Soát kết quả: trích vài khung (`ffmpeg -ss <giây> -i xuat/<ten>.mp4 -frames:v 1 f.jpg`) ở giữa mỗi ý và ngay sau
   mỗi lần cắt, xem phụ đề có che mặt/chữ trong hình không, hình có khớp lời không. Chỉnh `y.json`
   (`chuyen_dong`, `vua_khung`, `vi_tri_phu_de`…) rồi dựng lại. Gửi MP4 cho người dùng (SendUserFile),
   commit các file của dự án (MP4 trong `xuat/` không commit — quá nặng).

Người dùng góp ý sau khi xem ("ý 4 đổi hình", "phụ đề lên cao", "ý 7 zoom ra") → sửa `y.json` / thay hình → dựng lại.
Đổi lời trong `y.json` hoặc thay giọng → chạy lại `can` trước khi dựng.

## Biên tập (Claude edit) — làm sau khi người dùng đã dán hình

Máy tự biên tập được (không có `canh`) nhưng chỉ ở mức khá. Khi người dùng nhờ “edit”, Claude **xem từng hình**
(`tobia`, hoặc mở ảnh gốc) rồi viết `y[].canh` cho từng ý (cú pháp đầy đủ ở đầu `bien_tap.py`):
- Ý dài > 4 s: 2–3 cảnh, cắt bằng `tu_chu` đúng từ quan trọng (toàn cảnh → cận mặt/chi tiết được nhắc tới).
- `tu`/`den` nhắm vào chủ thể thật trong ảnh (mặt, mắt, vũ khí…), không mặc định giữa khung. Ảnh nhỏ (< 700 px)
  zoom tối đa ~1.4; ảnh lớn được tới 2–2.5. Ảnh ngang lớn: lia ngang (`tu` x 0.3 → `den` x 0.7). Ảnh ngang nhỏ: `vua: contain`.
- `vao`: phần lớn `cat`; `flash` cho khoảnh khắc đảo chiều/ánh sáng; `giat` cho từ nhấn (chết, không bao giờ…);
  `lia` cho chuỗi liệt kê nhanh; `mo` cho câu chậm/suy tư; `toi` khi sang đoạn mới. Không lặp một kiểu liên tục.
- `rung` 0.4–0.8 ở chỗ kịch tính/chiến trận. Chuyển động mặc định đều (tuyến tính); `muot: true` chỉ cho cảnh chậm.
- Dựng nháp (`--nhap`), trích khung ở mỗi lần cắt để soát, rồi `trang-thai … cho_dung` + push để GitHub dựng bản thật.
**Kiểu mặc định người dùng chọn: `kieu_edit: "theo_mau"`** (đo chuyển động từ video mẫu bằng ORB + affine):
xen kẽ `zoom_ra` (vào cảnh phóng ~1.45, lùi ra nhanh rồi chậm dần tới đứng yên trong ~2–3 s) và `troi` (trôi ngang
đều ~3.5% bề ngang/giây, không zoom); ý có khói/nhòe/chớp/giật luôn `zoom_ra`; video giữ nguyên. Claude đặt `chu_the`
(điểm dừng của zoom/giữa quãng trôi) cho từng ảnh; đổi riêng bằng `y[].chuyen`. Người dùng chê zoom-vào-đều là máy móc.
Kiểu cũ `kieu_edit: "lia_xen_ke"`: mỗi ảnh lấp đầy khung, xen kẽ dịch trái→phải /
phải→trái, zoom dần vào `chu_the` của ý; video giữ nguyên. Claude chỉ cần đặt `chu_the` đúng chủ thể của từng ảnh.
Toàn video: `vien_toi` (0.32), `hat_phim` (0 — bật 0.03 sẽ làm file nặng gấp nhiều lần), `tuong_phan` (1.07), `mo_cuoi` (0.7 s tối dần cuối video).

## Chữ nhấn + chuyển cảnh khói/nhòe (theo video mẫu người dùng thích)

Người dùng thích kiểu video lore tiếng Việt: không phụ đề cả câu, chỉ **chữ nhấn** 1–3 từ khóa (Montserrat Black Italic,
từ chính màu xanh ngọc to, chữ phụ trắng nhỏ, bật lên đúng lúc giọng đọc tới), chuyển cảnh **khói cam** và **nhòe**.
- `y[].chu_nhan`: `[{"tu_chu": "Perpetual", "chu": "ein sogenannter|*PERPETUAL*"}]` — dòng ngăn `|`, VIẾT HOA = to,
  `*…*` = màu nhấn. Chọn từ khóa đúng ngôn ngữ giọng đọc; 1–3 khối mỗi ý, mỗi khối ≤ 3 dòng. Cú pháp đủ ở đầu `chu.py`.
- Bật kiểu này thì đặt `phu_de: false`. `mau_nhan` (màu nhấn), `co_chu` (cỡ chữ).
- `y[].vao: "khoi"` ở chỗ sang đoạn/đảo ý (2–4 lần một video), `"nhoe"` cho chuyển ý thường; còn lại cắt thẳng.
  `mau_khoi` đổi màu khói (mặc định cam [255,110,25]).

## Tiêu đề mở đầu + màu

`tieu_de_mo` trong y.json (`{"chu": "WARHAMMER|40K", "phu": "IST DER IMPERATOR TOT?", "den": 3.6}`, xem `tieu_de.py`):
chữ kim loại trên dải tối viền vàng đập vào màn hình (rung + chớp + tiếng va), trôi chậm rồi vụt ra; người dùng tải
`logo.png` trên trang thì dùng logo đó. Không vẽ lại logo chính thức của Games Workshop. Chữ nhấn trong lúc tiêu đề hiện
tự dời ra sau. Màu: `bao_hoa` (1.15, rực như art chính thức), `vien_toi` (0.18), `tuong_phan` (1.06).
Nút tìm ảnh trên trang chỉ lấy ảnh cỡ lớn (Google `isz:l`) và có thêm “<từ khóa> wallpaper 4k”.

## Nhân vật kênh (Otto der Archivar)

Linh vật chung cho mọi video: ông cụ thủ thư người Đức (mũ Pickelhaube, ria mép trắng, kính tròn, áo choàng đỏ, sách
xích). Câu lệnh vẽ cho Gemini/ChatGPT: `kenh/nhan-vat/README.md`. Người dùng tải ảnh lên trang → `kenh/nhan-vat/goc/`;
`python3 nhan_vat.py` (workflow tự chạy) tách 6 biểu cảm + xóa nền → `kenh/nhan-vat/<bieu_cam>.png`.
Khi edit, Claude đặt `y[].nhan_vat` ở 4–7 chỗ có cảm xúc rõ (ngạc nhiên ở chi tiết bất ngờ, sợ ở chỗ chết chóc,
cười ở câu đùa, suy nghĩ ở câu hỏi, chỉ tay khi giới thiệu), xen kẽ `ben` trái/phải, không đặt ở ý có chủ thể nằm sát
đáy khung. Cú pháp ở đầu `nhan_vat.py`. Chưa có ảnh nhân vật thì máy bỏ qua.
Đoạn mở luôn có Otto (người dùng muốn): đứng giữa dưới tiêu đề suốt lúc tiêu đề hiện (`nhan_vat_mo`). Các lần sau do Claude chọn.

## Caption

Mỗi video có `du-an/<ten>/caption.txt` (tiếng của khán giả: câu móc + 1–2 câu tóm tắt + câu hỏi gọi bình luận + 8–12
hashtag). Claude viết khi edit. Workflow `caption.yml` (và `tu-dung.yml` sau khi dựng) dán nó vào mô tả bản phát hành
`video-<ten>` bằng `scripts/ghi_caption.sh` — phiên Claude không tự sửa release được (bị chặn), phải qua workflow.

## Âm thanh

`am_thanh.py` (gọi từ `ghep.py dung`): giọng + nhạc nền (tự nhỏ khi có giọng) + hiệu ứng tự đặt theo cách chuyển cảnh
(`lia`→vút, `giat`→va + bùm, `flash`→dồn ngược + ngân, sang ý mới→vút nhẹ, đầu video→bùm), master −9 LUFS, đỉnh ≈ −0.5 dB
(người dùng muốn to). Nhạc: `du-an/<ten>/nhac.*` (người dùng tải trên trang) hoặc `nhac` trong y.json
(`cinematic_suspense` mặc định · `mystery` · `horror_tension` · `false`). Hiệu ứng thêm ở từ nhấn: `y[].am`
(`[{"loai": "boom", "tu_chu": "Tod"}]`). Kho CC0 ở `am-thanh/` (`thu-vien.json`, `CREDITS.md`). Giọng được ép + nâng 3 kHz cho rõ. Chỉnh: `do_to`, `giong_db` (+5 mặc định — người dùng yêu cầu), `nhac_db` (−5 mặc định ≈ nhạc 10 LU dưới giọng; người dùng chê cả nhạc quá nhỏ ở 29 LU lẫn giọng quá nhỏ ở 6 LU), `sfx_db` (−2).

## Làm nét ảnh nhỏ (AI)

`python3 lam_net.py <ten>` (Real-ESRGAN ×4, cần `pip install torch`): ảnh có cạnh dài < 1400 px → `hinh/NN-…/.net/<tên>.jpg`,
`ghep.py` tự dùng bản đó. Workflow `tu-dung.yml` tự chạy trước khi dựng và commit `.net/` (chỉ làm một lần mỗi ảnh).
Model `x4plus` (mặc định, giữ nét vẽ, ~20–60 s/ảnh trên CPU) hoặc `--model general` (nhanh ~10 lần, mịn hơn).
Ảnh gốc to vẫn đẹp hơn mọi cách phóng. Trang web báo ngay ảnh “sẽ vỡ” (phải phóng > 1.5 lần mới lấp đầy khung) ở từng ý,
kèm link tải ảnh gốc; người dùng tự làm nét bằng Gemini/ChatGPT rồi dán lại. `python3 ghep.py vo <ten>` liệt kê cùng danh sách.

## Cách chia ý

- Một ý = một hình ảnh trên màn hình = một khoảnh khắc người xem *thấy* một điều mới.
  Cắt khi chủ thể / địa điểm / thời gian / cảm xúc đổi, khi có con số, nhân vật, đồ vật mới được nhắc tới.
- Độ dài mục tiêu **3–7 giây** lời đọc (khoảng 8–20 từ tiếng Việt, 7–16 từ tiếng Đức/Anh).
  Câu dài > 8 s → tách thành 2 ý; câu rất ngắn liền mạch → gộp. Câu móc (hook) đầu video nên là ý riêng, ngắn.
- `loi` của các ý ghép lại phải **đúng nguyên văn toàn bộ kịch bản, đúng thứ tự, không thiếu không thừa**
  (máy dùng nó để khớp với giọng đọc). Được tách giữa câu tại dấu phẩy nếu cần.
- Không có tiêu đề/ghi chú trong `loi` — chỉ những gì giọng đọc nói.
- **Video dùng nhiều clip** (vd kênh vũ trụ — người dùng dán clip NASA/Pexels): chia ý **dài hơn, 6–10 s**, gom theo
  đoạn nội dung; mỗi ý gợi ý 2–3 clip ngắn nối nhau (nguồn: NASA SVS svs.gsfc.nasa.gov, images.nasa.gov, Pexels, Pixabay).

## Cách gợi ý hình

Người dùng **tự tìm ảnh/video** — KHÔNG viết prompt tạo ảnh AI. Mọi chữ cho người dùng đều bằng tiếng Việt.
Mỗi ý viết:
- `nghia`: nghĩa tiếng Việt của `loi` (khi kịch bản không phải tiếng Việt) — dịch sát, dễ hiểu.
- `y_chinh`: ý chính trong 3–8 chữ (tiếng Việt).
- `goi_y_hinh`: mô tả **một khung hình cụ thể** bằng tiếng Việt — chủ thể, hành động, bối cảnh, góc máy,
  ánh sáng/tâm trạng. Cụ thể đến mức người dùng đi tìm/tạo là ra ngay ("cận mặt cô gái 25 tuổi nhìn gương
  phòng tắm, đèn vàng buổi sáng, vẻ mệt mỏi"), không chung chung ("hình về sự mệt mỏi").
  Hình phải *minh họa đúng lời đang đọc*, không chỉ đúng chủ đề. Câu trừu tượng → hình ẩn dụ cụ thể.
- `phuong_an_khac` (không bắt buộc): phương án dễ kiếm hơn (ảnh stock, ảnh tư liệu thật, chữ lớn trên nền).
- `tu_khoa`: từ khóa tìm ảnh **bằng tiếng Việt** (Google Ảnh, Pinterest…); tên riêng giữ nguyên (Guilliman, Nurgle).
- `tu_khoa_en` (không bắt buộc): cùng từ khóa bằng tiếng Anh — với chủ đề nước ngoài thường ra nhiều ảnh hơn.
- Sự kiện/người/địa điểm có thật → ưu tiên gợi ý ảnh tư liệu thật, ghi rõ nên tìm ảnh gì.
- Có thể gợi ý video (cảnh trong game, trailer, cảnh quay) khi chuyển động giúp ý rõ hơn.

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
      "nghia": "Nghĩa tiếng Việt (khi kịch bản không phải tiếng Việt).",
      "y_chinh": "Câu hỏi mở đầu",
      "goi_y_hinh": "…",
      "phuong_an_khac": "…",
      "tu_khoa": "chiếc loa, suy nghĩ",
      "tu_khoa_en": "speaker, thoughts",
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
| `y[].video_tu` | giây bắt đầu lấy trong video của ý (mặc định 0; mảng nếu ý có nhiều file) |
| `y[].chuyen_dong` | `zoom-in` · `zoom-out` · `pan-left` · `pan-right` · `pan-up` · `pan-down` · `none`; hoặc mảng, một cái cho mỗi hình của ý. Bỏ trống = tự xoay vòng. Video không có hiệu ứng này |

## Môi trường

`pip install -r requirements.txt` (faster-whisper cần `av<16`). Lần đầu tải model Whisper `small` (~500 MB).
Không có Whisper / không tải được model → `can` tự ước lượng theo độ dài chữ + khoảng lặng (kém chính xác hơn,
báo `do_chinh_xac: uoc-luong`). Font phụ đề: Inter (có dấu tiếng Việt), dự phòng DejaVu Sans.
