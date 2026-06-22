# Đồ án cuối kì SE365

## Giới thiệu
- Tên đề tài: Trích xuất sự kiện tài chính từ báo chí và diễn đàn tài chính bằng NLP/LLM.
- Mô tả: Trong thực tế, báo cáo tài chính của doanh nghiệp chỉ được công bố theo quý hoặc theo năm, nên thông tin thường có độ trễ. Tuy nhiên, mỗi ngày trên các trang báo tài chính, diễn đàn đầu tư, mạng xã hội hoặc thông báo doanh nghiệp lại xuất hiện rất nhiều thông tin mới liên quan đến hoạt động của công ty. Các chuyên gia tài chính khi đọc các bài viết này có thể nhanh chóng nhận ra những sự kiện doanh nghiệp quan trọng (corporate events) có khả năng ảnh hưởng đến giá cổ phiếu hoặc triển vọng kinh doanh của công ty. Ví dụ: Công ty ra mắt sản phẩm mới, Doanh nghiệp ký hợp đồng lớn, Sáp nhập hoặc mua lại công ty khác (M&A), Công ty đầu tư vào lĩnh vực mới, Rút vốn khỏi dự án, Tăng vốn điều lệ, Phát hành cổ phiếu hoặc trái phiếu, Thay đổi ban lãnh đạo, Mở rộng nhà máy, mở rộng thị trường, Bị điều tra, kiện tụng hoặc gặp khủng hoảng, Công bố hợp tác chiến lược, Được cấp phép hoặc trúng thầu dự án lớn,...Những thông tin này thường xuất hiện sớm trên báo chí hoặc diễn đàn trước khi phản ánh đầy đủ trong báo cáo tài chính. Mục tiêu của đề tài là xây dựng hệ thống có khả năng: Thu thập văn bản tài chính từ báo điện tử, diễn đàn hoặc mạng xã hội, xây dựng mô hình deep learning Tự động phát hiện và rút trích các sự kiện tài chính quan trọng, sau đó Chuẩn hóa thông tin thành dạng có cấu trúc phục vụ phân tích đầu tư.
---
## Dataset
### Schema

| Loại sự kiện | Các trường trích xuất |
| :--- | :--- |
| **META (có trong mọi sự kiện)** | `source_url` · `published_date` · `event_type` · `confidence` (high/medium/low) · `event_date` |
| **01. Chi trả cổ tức** | `ten_to_chuc` · `hinh_thuc_co_tuc` (tiền mặt/cổ phiếu/hỗn hợp) · `ty_le` · `nguon_co_tuc` · `ngay_gd_khong_huong_quyen` · `ngay_thanh_toan` |
| **02. Phát hành thêm cổ phiếu** | `ten_to_chuc` · `phuong_thuc_phat_hanh` · `loai_co_phieu` (phổ thông/ưu đãi) · `so_luong` · `gia_phat_hanh` · `tong_gia_tri` · `ngay_chot_quyen` |
| **03. Chia tách cổ phiếu** | `ten_to_chuc` · `ty_le_thuc_hien` · `ngay_gd_khong_huong_quyen` |
| **04. Gộp cổ phiếu** | `ten_to_chuc` · `ty_le_thuc_hien` · `ngay_gd_khong_huong_quyen` |
| **05. Phát hành trái phiếu** | `ten_to_chuc` · `loai_trai_phieu` (doanh nghiệp/chuyển đổi/có bảo đảm) · `tong_gia_tri` · `lai_suat` · `ky_han` · `ngay_phat_hanh` |
| **06. Niêm yết / Hủy niêm yết** | `ten_to_chuc` · `loai_hanh_dong` (niêm yết/hủy niêm yết/chuyển sàn) · `san_giao_dich` (HOSE/HNX/UPCoM) · `ngay_hieu_luc` · `ly_do` |
| **07. M&A / Góp vốn chiến lược** | `ben_rot_von` · `ben_nhan_von` · `loai_giao_dich` (mua lại/sáp nhập/góp vốn/liên doanh) · `ty_le_so_huu_truoc` · `ty_le_so_huu_sau` · `gia_tri_thuong_vu` · `ngay_hoan_tat` |
| **08. Trúng thầu / Ký hợp đồng lớn** | `ten_to_chuc` · `ten_doi_tac` · `loai_hop_dong` (EPC/tư vấn/cung cấp...) · `ten_du_an` · `gia_tri_hop_dong` · `thoi_gian_thuc_hien` · `ngay_ky` |
| **09. Thay đổi tỷ lệ sở hữu cổ đông** | `ten_to_chuc` · `ten_co_dong` · `chieu_thay_doi` (tăng/giảm) · `ty_le_truoc` · `ty_le_sau` · `so_cp_thay_doi` · `ngay_bat_dau` |
| **10. Cầm cố cổ phần** | `ten_to_chuc` · `ben_cam_co` · `ben_nhan_cam_co` · `so_luong_cp` · `ngay_bat_dau` · `ngay_ket_thuc` · `muc_dich` (vay vốn/đảm bảo nghĩa vụ) |
| **11. Phong tỏa cổ phần** | `ten_to_chuc` · `ten_co_dong` · `so_luong_cp` · `ngay_bat_dau` · `ngay_ket_thuc` · `co_quan_ra_lenh` |
| **12. Thay đổi nhân sự chủ chốt** | `ten_to_chuc` · `ten_nhan_su` · `trang_thai` (bổ nhiệm/từ chức/miễn nhiệm/bầu) · `chuc_vu` · `ngay_hieu_luc` · `nguoi_thay_the` |
| **13. Lãnh đạo cấp cao qua đời** | `ten_to_chuc` · `ten_lanh_dao` · `chuc_vu` · `tuoi` · `ngay_ghi_nhan` |
| **14. Tổn thất tài sản nghiêm trọng** | `ten_to_chuc` · `mo_ta_thiet_hai` · `gia_tri_ton_that` · `bao_hiem_boi_thuong` (có/không/một phần) · `ngay_cong_bo` |
| **15. Sự cố an toàn nghiêm trọng** | `ten_to_chuc` · `mo_ta_su_co` · `quy_mo_thuong_vong` · `thiet_hai_tai_san` · `he_qua_hoat_dong` · `ngay_cong_bo` |
| **16. Bồi thường lớn cho bên ngoài** | `ten_to_chuc` · `ben_nhan_boi_thuong` · `so_tien` · `ly_do` · `ngay_cong_bo` |
| **17. Xử phạt vi phạm / Thanh tra** | `thuc_the_bi_xu_ly` · `co_quan_xu_phat` · `ly_do_vi_pham` · `hinh_thuc_xu_phat` (phạt tiền/đình chỉ/thu hồi GCN...) · `so_tien_phat` · `ngay_quyet_dinh` |
| **18. Khởi tố / Tạm giam lãnh đạo** | `ten_ca_nhan` · `ten_to_chuc` · `chuc_vu` · `toi_danh` · `loai_hanh_dong` (khởi tố/tạm giam/bắt tạm giam) · `co_quan_thuc_thi` · `ngay_thuc_thi` |
| **19. Phá sản / Thanh lý** | `ten_to_chuc` · `loai_hanh_dong` (phá sản/tái cơ cấu/thanh lý tự nguyện) · `nganh_nghe` · `toa_an_thu_ly` · `ngay_cong_bo` · `ngay_phan_quyet` |


## Hướng dẫn chạy
### 1. Cào dữ liệu

- Cào link từ Vietstock:

    ```bash
    # Script crawl test
    python data_pipelines/vietstock_crawl_link.py --debug --head
    # Output ra giống file data_pipelines/vietstock_links_20260601_20260601_CHUAN.txt là ổn

    # Script cào dữ liệu thật (chạy dưới nền, có thể chạy trên Colab, Kaggle,...)
    # Nếu sử dụng Window
    python ./data_pipelines/vietstock_crawl_link.py `
    --start 01-06-2026 `
    --end 05-06-2026 `
    --output data/vietstock_links.txt `

    # Nếu sử dụng Linux
    python3 ./data_pipelines/vietstock_crawl_link.py \
    --start 01-06-2026 \
    --end 05-06-2026 \
    --output data/vietstock_links.txt \
    ```


## Tài liệu tham khảo
- [DCFEE: A Document-level Chinese Financial Event Extraction System
based on Automatically Labeled Training Data](https://aclanthology.org/P18-4009.pdf) - [Source Github](https://github.com/tongzhou21/DocFEE)
