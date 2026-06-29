import json
import sys
from pathlib import Path

import tqdm

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from data_pipelines.utils.dir_processor import get_project_abs_dir_str_from_env


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


def _build_formatted_record(record: dict, formatted_fields: list, deleted_fields: list) -> dict:
    """
    - Summary: Tạo trường mới từ template, xóa trường không cần thiết.
    - Args:
        - record:           Dict dữ liệu của một record.
        - formatted_fields: List config tạo trường mới (name, template, fields).
        - deleted_fields:   List tên trường cần xóa.
    - Output:
        - dict: Record đã được cập nhật.
    """
    for field_cfg in formatted_fields:
        field_values             = {f: record.get(f, '') or '' for f in field_cfg["fields"]}
        record[field_cfg["name"]] = field_cfg["template"].format(**field_values)
    for field_name in deleted_fields:
        record.pop(field_name, None)
    return record


def _process_file(
    in_path:          Path,
    out_path:         Path,
    formatted_fields: list,
    deleted_fields:   list,
):
    """
    - Summary:
        1. Tải id đã xử lý (_get_existing_ids()).
        2. Tải records từ input (_get_records()).
        3. Build và ghi từng record (_build_formatted_record()).
    - Args:
        - in_path:          Đường dẫn file input JSONL.
        - out_path:         Đường dẫn file output JSONL.
        - formatted_fields: List config tạo trường mới.
        - deleted_fields:   List tên trường cần xóa.
    - Output:
        - None. Ghi kết quả vào out_path (append).
    """
    existing_ids = _get_existing_ids(out_path)
    records      = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_count = 0
    with out_path.open('a', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'format {in_path.name}', ncols=100):
            if record.get("id") in existing_ids:
                continue
            formatted_record = _build_formatted_record(dict(record), formatted_fields, deleted_fields)
            fout.write(json.dumps(formatted_record, ensure_ascii=False) + '\n')
            new_count += 1

    print(f'  format: {new_count} mới / {len(records)} tổng → {out_path.name}')


def process_files(
    formatted_fields: list,
    deleted_fields:   list,
    in_out_pairs:     list,
    project_dir:      str,
):
    """
    - Summary:
        1. Resolve đường dẫn từng cặp in/out.
        2. Xử lý từng file (_process_file()).
    - Args:
        - formatted_fields: List config tạo trường mới.
        - deleted_fields:   List tên trường cần xóa.
        - in_out_pairs:     List các cặp [input_path_str, output_path_str].
        - project_dir:      Đường dẫn tuyệt đối thư mục gốc dự án.
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
            in_path          = in_path,
            out_path         = out_path,
            formatted_fields = formatted_fields,
            deleted_fields   = deleted_fields,
        )


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")

    format_config = {
        "formatted_fields": [
            {
                "name":     "content",
                "template": "Tiêu đề: {title}\nNội dung:{head}\n{body}",
                "fields":   ["title", "head", "body"]
            }
        ],
        "deleted_fields": ["title", "head", "body", "link", "rule_category"],
        "in_out": [
            ["data_pipelines/label/vietstock_crawled_data_20260601_20260601_CHUAN.jsonl",
             "data_pipelines/label/vietstock_preprocessed_20260601_20260601_CHUAN.jsonl"],
            ["data/processing/filter/config1/vietstock_filter_2023_2026.jsonl",
             "data/processing/preprocess/vietstock_preprocessed_filter_config1_2023_2026.jsonl"]
        ]
    }

    formatted_fields = format_config.get("formatted_fields", [])
    deleted_fields   = format_config.get("deleted_fields", [])
    in_out_pairs        = format_config.get("in_out", [])

    process_files(
        formatted_fields = formatted_fields,
        deleted_fields   = deleted_fields,
        in_out_pairs     = in_out_pairs,
        project_dir      = PROJECT_DIR,
    )
