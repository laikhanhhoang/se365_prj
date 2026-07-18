# Đồ án cuối kì SE365

# Giới thiệu
- Tên đề tài: Trích xuất sự kiện tài chính từ báo chí và diễn đàn tài chính bằng NLP/LLM.
- Mô tả: Trong thực tế, báo cáo tài chính của doanh nghiệp chỉ được công bố theo quý hoặc theo năm, nên thông tin thường có độ trễ. Tuy nhiên, mỗi ngày trên các trang báo tài chính, diễn đàn đầu tư, mạng xã hội hoặc thông báo doanh nghiệp lại xuất hiện rất nhiều thông tin mới liên quan đến hoạt động của công ty. Các chuyên gia tài chính khi đọc các bài viết này có thể nhanh chóng nhận ra những sự kiện doanh nghiệp quan trọng (corporate events) có khả năng ảnh hưởng đến giá cổ phiếu hoặc triển vọng kinh doanh của công ty. Ví dụ: Công ty ra mắt sản phẩm mới, Doanh nghiệp ký hợp đồng lớn, Sáp nhập hoặc mua lại công ty khác (M&A), Công ty đầu tư vào lĩnh vực mới, Rút vốn khỏi dự án, Tăng vốn điều lệ, Phát hành cổ phiếu hoặc trái phiếu, Thay đổi ban lãnh đạo, Mở rộng nhà máy, mở rộng thị trường, Bị điều tra, kiện tụng hoặc gặp khủng hoảng, Công bố hợp tác chiến lược, Được cấp phép hoặc trúng thầu dự án lớn,...Những thông tin này thường xuất hiện sớm trên báo chí hoặc diễn đàn trước khi phản ánh đầy đủ trong báo cáo tài chính. 

    Mục tiêu của đề tài là xây dựng hệ thống có khả năng: 
    - Thu thập văn bản tài chính từ báo điện tử, diễn đàn hoặc mạng xã hội, 
    - Xây dựng mô hình deep learning tự động phát hiện và rút trích các sự kiện tài chính quan trọng 
    - Chuẩn hóa thông tin thành dạng có cấu trúc phục vụ phân tích đầu tư.
---
# Dataset
## Output schema

> JSON Format [`data_pipelines/labelling/data_schema.json`](data_pipelines/labelling/data_schema.json) luôn phải được cập nhật theo config bên dưới.

- Trường bắt buộc với từng sự kiện xác định được: 
    - `event_type`: loại sự kiện
    - `confidence` (high/medium/low): độ tin cậy của thông tin trích xuất được. Cụ thể, high **/** medium **/** low tương ứng với sự kiện được xác nhận đã xảy ra **/** sự kiện là kế hoạch, dự kiến do người viết dự báo, chưa xảy ra hoặc chưa được phê duyệt chính thức **/** sự kiện chỉ là lời đồn hoặc do model suy luận từ ngữ cảnh, không được nêu trực tiếp.

- Với từng loại sự kiện phát hiện, cần trích xuất kèm theo các trường thông tin sau:
    | Loại sự kiện (`event_type`) | Mô tả | Các trường trích xuất |
    | :--- | :--- | :--- |
    | **— Cổ tức —** | | |
    | **01. Chi trả cổ tức** | Doanh nghiệp phân phối một phần lợi nhuận sau thuế cho cổ đông theo tỷ lệ sở hữu cổ phần. | `ten_to_chuc` · `hinh_thuc_co_tuc` (tiền mặt/cổ phiếu/hỗn hợp) · `ty_le` · `ngay_gd_khong_huong_quyen` · `ngay_thanh_toan` |
    | **— Cổ phiếu —** | | |
    | **02. Phát hành thêm cổ phiếu** | Doanh nghiệp tăng vốn điều lệ bằng cách phát hành cổ phiếu mới ra thị trường hoặc cho các đối tượng cụ thể. | `ten_to_chuc` · `phuong_thuc_phat_hanh` · `loai_co_phieu` (phổ thông/ưu đãi) · `so_luong` · `gia_phat_hanh` · `ngay_chot_quyen` |
    | **03. Niêm yết** | Cổ phiếu của doanh nghiệp được cơ quan quản lý chấp thuận đưa vào giao dịch chính thức trên một sở giao dịch chứng khoán (HOSE/HNX/UPCoM). | `ten_to_chuc` · `ma_co_phieu` · `san_giao_dich` (HOSE/HNX/UPCoM) · `so_luong_co_phieu` · `ngay_hieu_luc` |
    | **04. Hủy niêm yết** | Cổ phiếu của doanh nghiệp bị đưa ra khỏi sở giao dịch chứng khoán, không còn được giao dịch chính thức trên sàn đó nữa. | `ten_to_chuc` · `ma_co_phieu` · `san_giao_dich` (HOSE/HNX/UPCoM) · `ngay_hieu_luc` |
    | **— Trái phiếu —** | | |
    | **05. Phát hành trái phiếu** | Doanh nghiệp huy động vốn vay bằng cách phát hành trái phiếu cho nhà đầu tư, cam kết trả lãi định kỳ và hoàn trả gốc khi đáo hạn. | `ten_to_chuc` · `loai_trai_phieu` (doanh nghiệp/chuyển đổi/có bảo đảm) · `tong_gia_tri` · `lai_suat` · `ky_han` · `ngay_phat_hanh` |
    | **— Cổ đông —** | | |
    | **06. Cổ đông thay đổi tỷ lệ sở hữu** | Một cổ đông của doanh nghiệp mua vào hoặc bán ra cổ phiếu, làm thay đổi tỷ lệ sở hữu của cổ đông đó tại doanh nghiệp. | `ten_to_chuc` · `ten_co_dong` · `chieu_thay_doi` (tăng/giảm) · `ty_le_truoc` · `ty_le_sau` · `so_cp_thay_doi` · `ngay_bat_dau` |
    | **— Nhân sự —** | | |
    | **07. Thay đổi nhân sự chủ chốt** | Doanh nghiệp bổ nhiệm, miễn nhiệm, cho từ chức hoặc bầu lại nhân sự giữ vị trí lãnh đạo chủ chốt (HĐQT, Ban Tổng giám đốc, Ban kiểm soát...). | `ten_to_chuc` · `ten_nhan_su` · `trang_thai` (bổ nhiệm/từ chức/miễn nhiệm/bầu) · `chuc_vu` · `nguoi_thay_the` |
    | **— Đầu tư / Kiếm tiền —** | | |
    | **08. M&A** | Một tổ chức bên ngoài mua lại hoặc sáp nhập vào doanh nghiệp, dẫn đến thay đổi quyền kiểm soát doanh nghiệp. | `ten_to_chuc` · `ben_mua` · `loai_giao_dich` (mua lại/sáp nhập) · `ty_le_so_huu_truoc` · `ty_le_so_huu_sau` · `gia_tri_thuong_vu` · `ngay_hoan_tat` |
    | **09. Đầu tư** | Doanh nghiệp dùng vốn để đầu tư hoặc góp vốn vào một công ty khác, nhằm mở rộng lĩnh vực kinh doanh, tìm kiếm lợi nhuận hoặc thiết lập quan hệ hợp tác chiến lược. Chỉ áp dụng khi doanh nghiệp có được tỷ lệ sở hữu/cổ phần (phân biệt với mục 10). | `ten_to_chuc` · `ten_cong_ty_dau_tu_vao` · `ty_le_so_huu` · `gia_tri_dau_tu` · `muc_dich` · `ngay_thuc_hien` |
    | **10. Hợp đồng lớn** | Doanh nghiệp trúng thầu hoặc ký kết hợp đồng có giá trị lớn với đối tác, phản ánh năng lực cạnh tranh và triển vọng doanh thu trong tương lai. Áp dụng khi doanh nghiệp là bên thực hiện/cung cấp dịch vụ, không sở hữu cổ phần (phân biệt với mục 09). | `ten_to_chuc` · `ten_doi_tac` · `loai_hop_dong` (EPC/tư vấn/cung cấp...) · `ten_du_an` · `gia_tri_hop_dong` ·  `ngay_ky` |
    | **11. Vay vốn** | Doanh nghiệp vay vốn từ ngân hàng hoặc tổ chức tín dụng để phục vụ hoạt động kinh doanh, đầu tư dự án hoặc tái cơ cấu nợ. | `ten_to_chuc` · `ben_cho_vay` · `tong_gia_tri_khoan_vay` · `muc_dich` · `ky_han` · `ben_bao_lanh` · `ngay_ky` |
    | **— Tổn thất —** | | |
    | **12. Tổn thất tài sản nghiêm trọng** | Doanh nghiệp phải chịu một khoản thiệt hại/tổn thất tài sản hoặc tài chính có giá trị lớn, phát sinh từ một sự cố/biến cố cụ thể xác định được nguyên nhân (vật chất hoặc phi vật chất) — khác với kết quả kinh doanh thua lỗ thông thường theo chu kỳ. | `ten_to_chuc` · `mo_ta_su_co` · `gia_tri_ton_that` · `ngay_cong_bo` |
    | **13. Bồi thường lớn cho bên ngoài** | Doanh nghiệp phải chi trả một khoản bồi thường lớn cho bên thứ ba, do vi phạm hợp đồng, gây thiệt hại hoặc theo phán quyết của tòa án/trọng tài. | `ten_to_chuc` · `ben_nhan_boi_thuong` · `so_tien` · `ly_do` · `ngay_cong_bo` |
    | **— Pháp lý —** | | |
    | **14. Vấn đề pháp lý** | Một tổ chức và/hoặc cá nhân liên quan đến doanh nghiệp (lãnh đạo, cổ đông...) bị cơ quan quản lý nhà nước hoặc cơ quan thực thi pháp luật xử phạt, thanh tra, cưỡng chế, khởi tố, bắt tạm giam, điều tra hoặc xét xử do vi phạm pháp luật. | `ten_to_chuc` · `ca_nhan_chiu_trach_nhiem` (dạng: "Tên - Chức vụ", nhiều người cách nhau bởi dấu phẩy) · `noi_dung_vi_pham` · `co_quan_xu_ly` · `hinh_thuc_xu_phat` (phạt tiền/đình chỉ/thu hồi GCN...) · `ngay_ra_quyet_dinh` |
    | **15. Phá sản** | Doanh nghiệp mất khả năng thanh toán các khoản nợ đến hạn và bị tòa án ra quyết định mở thủ tục phá sản, tái cơ cấu bắt buộc hoặc tự nguyện thanh lý. | `ten_to_chuc` · `loai_hanh_dong` (phá sản/tái cơ cấu/thanh lý tự nguyện) · `nganh_nghe` · `toa_an_thu_ly` · `ngay_cong_bo` · `ngay_phan_quyet` |


# Hướng dẫn chạy



## 1. Cào dữ liệu

> Chi tiết tham số và lệnh debug xem tại [data_pipelines/_HOW_TO_RUN.md](data_pipelines/_HOW_TO_RUN.md)

### 1.1. [Vietstock / `Doanh nghiệp`](https://vietstock.vn/doanh-nghiep.htm)

- **Cào link:**

    ```bash
    # Windows (PowerShell)
    python data_pipelines/crawl/vietstock_crawl_links.py `
        --start 01-06-2026 `
        --end   05-06-2026 `
        --output data_pipelines/crawl/vietstock_links_01062026_05062026.txt

    # Linux / macOS
    python3 data_pipelines/crawl/vietstock_crawl_links.py \
        --start 01-06-2026 \
        --end   05-06-2026 \
        --output data_pipelines/crawl/vietstock_links_01062026_05062026.txt
    ```

- **Cào data từ link:**

    ```bash
    # Windows (PowerShell)
    python data_pipelines/crawl/vietstock_crawl_data_from_links.py `
        --links_file data_pipelines/crawl/vietstock_links_01062026_05062026.txt

    # Linux / macOS
    python3 data_pipelines/crawl/vietstock_crawl_data_from_links.py \
        --links_file data_pipelines/crawl/vietstock_links_01062026_05062026.txt
    ```

## 2. Chuẩn hoá, lọc, gán nhãn, hậu xử lý

> Chi tiết tham số xem tại [data_pipelines/_HOW_TO_RUN.md](data_pipelines/_HOW_TO_RUN.md)

Toàn bộ 4 bước còn lại nằm trong [data_pipelines/labelling/](data_pipelines/labelling/), đọc taxonomy sự kiện trực tiếp từ `data_schema.json`:

```bash
python data_pipelines/labelling/step01_preprocess.py            # chuẩn hoá dataset (id, content)
python data_pipelines/labelling/step02_filter.py                # lọc bài viết theo keyword
python data_pipelines/labelling/step03_auto_label_openai.py     # gán nhãn bằng OpenAI
python data_pipelines/labelling/step04_postprocess.py           # parse + validate output
```

## 3. Huấn luyện và inference các model
Thực hiện chạy các file notebook đối với từng phương pháp trong [ml/approaches/](ml/approaches/).
Trọng số của các model được lưu trữ trong các thư mục weights. Thời gian trung bình để chạy infer cho file test là 2 tiếng.


# Tài liệu tham khảo
- [DCFEE: A Document-level Chinese Financial Event Extraction System
based on Automatically Labeled Training Data](https://aclanthology.org/P18-4009.pdf) - [Source Github](https://github.com/tongzhou21/DocFEE)
