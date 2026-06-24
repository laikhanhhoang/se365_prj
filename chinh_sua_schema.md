# Thảo luận chỉnh sửa Schema

Ghi lại các vấn đề đang thảo luận. Chưa chốt — sẽ cập nhật README sau khi thống nhất.

---

# Vấn đề

## 1. Tách event 06 thành 3 event riêng

**Hiện tại:** Event 06 gộp chung `loai_hanh_dong` (niêm yết / hủy niêm yết / chuyển sàn) vào 1 schema.

**Vấn đề:** Các trường cần thiết khác nhau theo từng loại hành động → dẫn đến nhiều trường conditional → LLM dễ hallucinate.

**Đề xuất:** Tách thành 3 event riêng:

| | 06a. Niêm yết | 06b. Hủy niêm yết | 06c. Chuyển sàn |
|---|---|---|---|
| `ten_to_chuc` | ✓ | ✓ | ✓ |
| `ma_co_phieu` | ✓ | ✓ | ✓ |
| `san_giao_dich` | ✓ | ✓ | ✓ (sàn mới) |
| `san_giao_dich_cu` | ✗ | ✗ | ✓ |
| `so_luong_co_phieu` | ✓ | ✗ | ✓ |
| `ngay_hieu_luc` | ✓ | ✓ | ✓ |
| `ly_do` | ✗ | ✓ | ✗ |

---

## 2. Thêm trường `ma_co_phieu` và `so_luong_co_phieu` vào event 06

**Hiện tại:** Schema 06 không có `ma_co_phieu` và `so_luong_co_phieu`.

**Vấn đề:**
- `ma_co_phieu` (VD: BVB) khác với `ten_to_chuc` (BVBank) — cần để lookup, không nên bỏ qua.
- `so_luong_co_phieu` hầu như luôn có trong thông báo niêm yết chính thức.

**Đề xuất:** Thêm cả 2 trường, áp dụng theo bảng trên (optional với hủy niêm yết).

---

## 3. Định nghĩa trường `confidence`

**Hiện tại:** `confidence` (high/medium/low) không có tiêu chí rõ ràng.

**Đề xuất:** Định nghĩa theo trạng thái xác nhận của sự kiện:
- `high` — đã xảy ra / được xác nhận chính thức
- `medium` — kế hoạch / đang chờ phê duyệt
- `low` — tin đồn / chưa xác minh

---

## 4. Xử lý bài báo không có sự kiện

**Đề xuất:** Dùng 2 giá trị phân biệt thay vì `null`:
- `event_type: "NONE"` — bài thực sự không có sự kiện (phân tích thị trường, nhận định chung)
- `event_type: "UNCERTAIN"` — bài có thể có sự kiện nhưng LLM không extract được (bài mơ hồ, thiếu thông tin)

---

## 5. Không dùng trường `note` tự do

**Vấn đề:** Trường free-text → LLM dễ hallucinate, diễn giải thay vì trích dẫn.

**Đề xuất:** Thay bằng:
- `raw_quote` — copy nguyên văn từ bài, không tự sinh
- `missing_fields` — ghi lý do tại sao trường bị null (VD: `{"so_luong": "bài chưa công bố chính thức"}`)

---

## 7. Tách event 07 thành 2 event riêng

**Hiện tại:** Event 07 gộp chung M&A và Góp vốn chiến lược.

**Vấn đề:** 2 loại này khác nhau về bản chất, chiều hướng và trường cần thiết:
- M&A = **inbound** — bên ngoài mua/thâu tóm công ty niêm yết
- Góp vốn = **outbound** — công ty niêm yết đem vốn đầu tư vào chỗ khác

Gộp chung còn gây overlap với event 09 (Thay đổi tỷ lệ sở hữu cổ đông).

**Đề xuất:** Tách thành 2 event:

**07a. M&A** — bên ngoài mua/sáp nhập vào công ty niêm yết
```
ben_mua · ten_to_chuc · loai_giao_dich (mua lại/sáp nhập)
· ty_le_so_huu_truoc · ty_le_so_huu_sau · gia_tri_thuong_vu · ngay_hoan_tat
```

**07b. Đầu tư / Góp vốn ra ngoài** — công ty niêm yết đầu tư vào công ty khác
```
ten_to_chuc · ten_cong_ty_dau_tu_vao · ty_le_so_huu
· gia_tri_dau_tu · muc_dich · ngay_thuc_hien
```

**Ranh giới rõ sau khi tách:**
- **07a** — bên ngoài mua vào công ty niêm yết (thay đổi quyền kiểm soát)
- **07b** — công ty niêm yết đầu tư ra ngoài
- **09** — cổ đông hiện hữu mua thêm/bán bớt trên thị trường

---

## 6. Boundary case event 13 — Lãnh đạo cấp cao qua đời

**Vấn đề:** Bài đề cập cựu lãnh đạo qua đời — có nên label event 13 không?

**Đề xuất:** Chỉ label event 13 nếu người đó còn ít nhất 1 trong các điều kiện:
- Còn là cổ đông lớn
- Là sáng lập viên
- Còn giữ vai trò cố vấn chính thức

Thêm trường `con_lien_quan: bool` + `ly_do_lien_quan` để ghi nhận.

---

# Schema đề xuất

## Danh sách event

| id | Tên event |
|---|---|
| **— Cổ tức —** | |
| 01 | Chi trả cổ tức |
| **— Cổ phiếu —** | |
| 02 | Phát hành thêm cổ phiếu |
| 03 | Chia tách cổ phiếu |
| 04 | Gộp cổ phiếu |
| 05 | Niêm yết |
| 06 | Hủy niêm yết |
| 07 | Chuyển sàn |
| **— Trái phiếu —** | |
| 08 | Phát hành trái phiếu |
| **— Cổ đông —** | |
| 09 | Cổ đông thay đổi tỷ lệ sở hữu |
| 10 | Cổ đông cầm cố cổ phiếu |
| 11 | Cổ đông phong tỏa cổ phiếu |
| **— Nhân sự —** | |
| 12 | Thay đổi nhân sự chủ chốt |
| 13 | Lãnh đạo cấp cao qua đời |
| **— Đầu tư / Kiếm tiền —** | |
| 14 | M&A |
| 15 | Đầu tư |
| 16 | Hợp đồng lớn |
| **— Tổn thất —** | |
| 17 | Tổn thất tài sản nghiêm trọng |
| 18 | Bồi thường lớn cho bên ngoài |
| **— Pháp lý —** | |
| 19 | Vấn đề pháp lý với tổ chức |
| 20 | Vấn đề pháp lý với cá nhân |
| 21 | Phá sản |
