import json
import re
import sys
from pathlib import Path

import tqdm

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from data_pipelines.utils.dir_processor import get_project_abs_dir_str_from_env

_CODE_FENCE     = "```"
_COMMON_FIELDS  = ["event_type", "confidence"]  # có ở mọi event, không tính riêng theo EVENTS_FIELDS

EVENTS_FIELDS = {
    "Chi trả cổ tức":                ["ten_to_chuc", "hinh_thuc_co_tuc", "ty_le", "ngay_gd_khong_huong_quyen", "ngay_thanh_toan"],
    "Phát hành thêm cổ phiếu":       ["ten_to_chuc", "phuong_thuc_phat_hanh", "loai_co_phieu", "so_luong", "gia_phat_hanh", "tong_gia_tri", "ngay_chot_quyen"],
    "Chia tách cổ phiếu":            ["ten_to_chuc", "ty_le_thuc_hien", "ngay_gd_khong_huong_quyen"],
    "Gộp cổ phiếu":                  ["ten_to_chuc", "ty_le_thuc_hien", "ngay_gd_khong_huong_quyen"],
    "Niêm yết":                      ["ten_to_chuc", "ma_co_phieu", "san_giao_dich", "so_luong_co_phieu", "ngay_hieu_luc"],
    "Hủy niêm yết":                  ["ten_to_chuc", "ma_co_phieu", "san_giao_dich", "ngay_hieu_luc"],
    "Chuyển sàn":                    ["ten_to_chuc", "ma_co_phieu", "san_giao_dich", "san_giao_dich_cu", "so_luong_co_phieu", "ngay_hieu_luc"],
    "Phát hành trái phiếu":          ["ten_to_chuc", "loai_trai_phieu", "tong_gia_tri", "lai_suat", "ky_han", "ngay_phat_hanh"],
    "Cổ đông thay đổi tỷ lệ sở hữu": ["ten_to_chuc", "ten_co_dong", "chieu_thay_doi", "ty_le_truoc", "ty_le_sau", "so_cp_thay_doi", "ngay_bat_dau"],
    "Cổ đông cầm cố cổ phiếu":       ["ten_to_chuc", "ben_cam_co", "ben_nhan_cam_co", "so_luong_cp", "ngay_bat_dau", "ngay_ket_thuc"],
    "Cổ đông phong tỏa cổ phiếu":    ["ten_to_chuc", "ten_co_dong", "so_luong_cp", "ngay_bat_dau", "ngay_ket_thuc", "co_quan_ra_lenh"],
    "Thay đổi nhân sự chủ chốt":     ["ten_to_chuc", "ten_nhan_su", "trang_thai", "chuc_vu", "nguoi_thay_the"],
    "Lãnh đạo cấp cao qua đời":      ["ten_to_chuc", "ten_lanh_dao", "chuc_vu", "con_lien_quan", "ngay_ghi_nhan"],
    "M&A":                           ["ben_mua", "ten_to_chuc", "loai_giao_dich", "ty_le_so_huu_truoc", "ty_le_so_huu_sau", "gia_tri_thuong_vu", "ngay_hoan_tat"],
    "Đầu tư":                        ["ten_to_chuc", "ten_cong_ty_dau_tu_vao", "ty_le_so_huu", "gia_tri_dau_tu", "muc_dich", "ngay_thuc_hien"],
    "Hợp đồng lớn":                  ["ten_to_chuc", "ten_doi_tac", "loai_hop_dong", "ten_du_an", "gia_tri_hop_dong", "thoi_gian_thuc_hien", "ngay_ky"],
    "Tổn thất tài sản nghiêm trọng": ["ten_to_chuc", "mo_ta_su_co", "gia_tri_ton_that", "bao_hiem_boi_thuong", "ngay_cong_bo"],
    "Bồi thường lớn cho bên ngoài":  ["ten_to_chuc", "ben_nhan_boi_thuong", "so_tien", "ly_do", "ngay_cong_bo"],
    "Vấn đề pháp lý với tổ chức":    ["thuc_the_bi_xu_ly", "co_quan_xu_phat", "ly_do_vi_pham", "hinh_thuc_xu_phat", "so_tien_phat", "ngay_quyet_dinh"],
    "Vấn đề pháp lý với cá nhân":    ["ten_ca_nhan", "ten_to_chuc", "chuc_vu", "toi_danh", "loai_hanh_dong", "co_quan_thuc_thi", "ngay_thuc_thi"],
    "Phá sản":                       ["ten_to_chuc", "loai_hanh_dong", "nganh_nghe", "toa_an_thu_ly", "ngay_cong_bo", "ngay_phan_quyet"],
}


def _get_existing_ids(out_path: Path) -> set[str]:
    """
    - Summary: Đọc file output, trả về tập id đã xử lý.
    - Args:
        - out_path: Đường dẫn file output JSONL.
    - Output:
        - set[str]: Tập id đã tồn tại trong output.
    """
    existing_ids: set[str] = set()
    if not out_path.exists():
        return existing_ids
    with out_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    existing_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    return existing_ids


def _get_records(in_path: Path) -> list[dict]:
    """
    - Summary: Đọc toàn bộ record hợp lệ từ file JSONL.
    - Args:
        - in_path: Đường dẫn file input JSONL.
    - Output:
        - list[dict]: Danh sách các record hợp lệ.
    """
    records: list[dict] = []
    with in_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records


def _build_parsed_events(label_raw: str) -> list[dict] | None:
    """
    - Summary: Parse chuỗi JSON thô của model thành list dict.
    - Args:
        - label_raw: Chuỗi phản hồi thô từ model (có thể kèm code fence, NULL không quote).
    - Output:
        - list[dict] | None: Danh sách event đã parse, None nếu parse lỗi.
    """
    cleaned = label_raw.strip()

    if cleaned.startswith(_CODE_FENCE):
        newline_idx = cleaned.find('\n')  # bỏ dòng mở fence, dù là ```json hay ``` trần
        cleaned     = cleaned[newline_idx + 1:] if newline_idx != -1 else cleaned[len(_CODE_FENCE):]
    if cleaned.endswith(_CODE_FENCE):
        cleaned = cleaned[:-len(_CODE_FENCE)]
    cleaned = cleaned.strip()

    cleaned = re.sub(r'\bnull\b', 'null', cleaned, flags=re.IGNORECASE)  # Null/NUll/NULL -> null

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _get_field_diff(event: dict) -> tuple[set[str], set[str]]:
    """
    - Summary: So khớp field của event với EVENTS_FIELDS.
    - Args:
        - event: Dict 1 event đã parse từ model.
    - Output:
        - tuple[set[str], set[str]]: Tập field bị thiếu, tập field thừa (model bịa).
    """
    expected_fields = set(_COMMON_FIELDS) | set(EVENTS_FIELDS.get(event.get("event_type"), []))
    actual_fields   = set(event.keys())
    return expected_fields - actual_fields, actual_fields - expected_fields


def _build_formatted_record(record: dict, raw_field: str, output_field: str) -> dict:
    """
    - Summary: Parse raw_field trong record, gán vào output_field.
    - Args:
        - record:       Dict dữ liệu của một record.
        - raw_field:    Tên trường chứa JSON thô cần parse.
        - output_field: Tên trường sẽ chứa kết quả đã parse.
    - Output:
        - dict: Record đã được cập nhật.
    """
    label_raw            = record.pop(raw_field, "")
    record[output_field] = _build_parsed_events(label_raw)
    return record


def _process_file(
    in_path:      Path,
    out_path:     Path,
    raw_field:    str,
    output_field: str,
):
    """
    - Summary:
        1. Tải id đã xử lý (_get_existing_ids()).
        2. Tải records từ input (_get_records()).
        3. Parse và ghi từng record (_build_formatted_record()).
        4. Check field thiếu/thừa từng event (_get_field_diff()).
    - Args:
        - in_path:      Đường dẫn file input JSONL.
        - out_path:     Đường dẫn file output JSONL.
        - raw_field:    Tên trường chứa JSON thô cần parse.
        - output_field: Tên trường sẽ chứa kết quả đã parse.
    - Output:
        - None. Ghi kết quả vào out_path (append).
    """
    existing_ids = _get_existing_ids(out_path)
    records      = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_count         = 0
    failed_count      = 0
    field_issue_count = 0
    with out_path.open('a', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'format {in_path.name}', ncols=100):
            if record.get("id") in existing_ids:
                continue
            formatted_record = _build_formatted_record(dict(record), raw_field, output_field)
            events           = formatted_record[output_field]
            if events is None:
                failed_count += 1
                print(f"[WARN] Parse lỗi sample {record.get('id')}")
            else:
                for event in events:
                    missing_fields, extra_fields = _get_field_diff(event)
                    if missing_fields or extra_fields:
                        field_issue_count += 1
                        print(f"[WARN] Sample {record.get('id')} - event '{event.get('event_type')}': "
                              f"thiếu {missing_fields or '{}'}, thừa {extra_fields or '{}'}")
            fout.write(json.dumps(formatted_record, ensure_ascii=False) + '\n')
            new_count += 1

    print(f'  format: {new_count} mới / {len(records)} tổng '
          f'(lỗi parse: {failed_count}, lệch field: {field_issue_count}) → {out_path.name}')


def process_files(
    raw_field:    str,
    output_field: str,
    in_out_pairs: list,
    project_dir:  str,
):
    """
    - Summary:
        1. Resolve đường dẫn từng cặp in/out.
        2. Xử lý từng file (_process_file()).
    - Args:
        - raw_field:    Tên trường chứa JSON thô cần parse.
        - output_field: Tên trường sẽ chứa kết quả đã parse.
        - in_out_pairs: List các cặp [input_path_str, output_path_str].
        - project_dir:  Đường dẫn tuyệt đối thư mục gốc dự án.
    - Output:
        - None. Ghi kết quả ra các file JSONL output.
    """
    project_path = Path(project_dir)

    for in_path_str, out_path_str in in_out_pairs:
        in_path  = project_path / in_path_str
        out_path = project_path / out_path_str

        if not in_path.exists():
            print(f"[SKIP] Không tìm thấy: {in_path}")
            continue

        _process_file(
            in_path      = in_path,
            out_path     = out_path,
            raw_field    = raw_field,
            output_field = output_field,
        )


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")

    format_output_config = {
        "raw_field":    "label_raw",
        "output_field": "events",
        "in_out": [
            ["data_pipelines/label/vietstock_labeled_raw_20260601_20260601_CHUAN.jsonl",
             "data_pipelines/label/vietstock_labeled_20260601_20260601_CHUAN.jsonl"],
        ]
    }

    raw_field, output_field = format_output_config.get("raw_field", "label_raw"), format_output_config.get("output_field", "events")
    in_out_pairs            = format_output_config.get("in_out", [])

    process_files(
        raw_field    = raw_field,
        output_field = output_field,
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
    )
