import json
import sys
from pathlib import Path

import tqdm

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from data_pipelines.utils.dir_processor import get_project_abs_dir_str_from_env
from data_pipelines.utils.file_processor import process_write_run_log, process_merge_output_files


def _get_dataset_schema(schema_path: Path) -> tuple[list[str], str]:
    """
    - Summary: Đọc dataset.schema/strict_required từ data_schema.json.
    - Args:
        - schema_path: Đường dẫn data_schema.json.
    - Output:
        - tuple[list[str], str]: List field cần giữ, và "yes"/"no" của strict_required.
    """
    dataset = json.loads(schema_path.read_text(encoding='utf-8'))["dataset"]
    return dataset["schema"], dataset["strict_required"]


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


def _build_content_field(record: dict) -> str:
    """
    - Summary: Gộp toàn bộ field (trừ id) thành content.
    - Args:
        - record: Dict dữ liệu gốc của 1 sample (chưa cắt theo schema).
    - Output:
        - str: Chuỗi content nối từ mọi giá trị field, ngăn bằng "\\n".
    """
    return '\n'.join(str(v) for k, v in record.items() if k != "id" and v not in (None, ""))


def _build_dataset_record(record: dict, schema: list[str], next_id: int) -> tuple[dict, int]:
    """
    - Summary: Sinh id/content còn thiếu, cắt record theo schema.
    - Args:
        - record:  Dict dữ liệu gốc của 1 sample.
        - schema:  List field cần giữ lại (VD: ["id", "content"]).
        - next_id: Giá trị id dùng nếu record chưa có "id".
    - Output:
        - tuple[dict, int]: Record đã cắt theo schema, next_id đã cập nhật.
    """
    has_own_id = record.get("id") not in (None, "")

    normalized = dict(record)
    if not has_own_id:
        normalized["id"] = next_id
    if "content" in schema and not normalized.get("content"):
        normalized["content"] = _build_content_field(record)

    formatted_record = {field: normalized.get(field) for field in schema}
    next_id_out       = next_id if has_own_id else next_id + 1
    return formatted_record, next_id_out


def _get_field_diff(record: dict, schema: list[str]) -> tuple[set[str], set[str]]:
    """
    - Summary: So khớp field của record với schema.
    - Args:
        - record: Dict 1 record gốc.
        - schema: List field kỳ vọng.
    - Output:
        - tuple[set[str], set[str]]: Tập field bị thiếu, tập field thừa.
    """
    expected_fields = set(schema)
    actual_fields   = set(record.keys())
    return expected_fields - actual_fields, actual_fields - expected_fields


def _preprocess_file(
    in_path:          Path,
    out_path:         Path,
    schema:           list[str],
    strict_required:  str,
) -> list[str]:
    """
    - Summary:
        1. Tải records từ input (_get_records()).
        2. Chuẩn hoá từng record theo schema (_build_dataset_record()) hoặc validate (_get_field_diff()).
        3. Ghi kết quả ra output.
    - Args:
        - in_path:         Đường dẫn file input JSONL.
        - out_path:        Đường dẫn file output JSONL.
        - schema:           List field cần giữ lại.
        - strict_required: "yes" (validate, giữ nguyên) hoặc "no" (tự sinh id/content).
    - Output:
        - list[str]: List dòng log tóm tắt của file này.
    """
    records = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    auto_id_count    = 0
    field_diff_count = 0
    next_id          = 1
    with out_path.open('w', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'preprocess {in_path.name}', ncols=100):
            if strict_required == "yes":
                missing_fields, extra_fields = _get_field_diff(record, schema)
                if missing_fields or extra_fields:
                    field_diff_count += 1
                    print(f"[WARN] Sample {record.get('id')}: thiếu {missing_fields or '{}'}, thừa {extra_fields or '{}'}")
                formatted_record = record
            else:
                had_own_id                = record.get("id") not in (None, "")
                formatted_record, next_id = _build_dataset_record(record, schema, next_id)
                if not had_own_id:
                    auto_id_count += 1
            fout.write(json.dumps(formatted_record, ensure_ascii=False) + '\n')

    summary = (
        f'  preprocess: {len(records)} record '
        f'(id tự sinh: {auto_id_count}, lệch field: {field_diff_count}) → {out_path.name}'
    )
    print(summary)
    return [summary]


def preprocess_files(
    in_out_pairs: list,
    project_dir:  str,
    schema_path:  Path,
):
    """
    - Summary:
        1. Đọc dataset schema (_get_dataset_schema()).
        2. Resolve đường dẫn từng cặp in/out.
        3. Xử lý từng file (_preprocess_file()).
    - Args:
        - in_out_pairs: List các cặp [input_path_str, output_path_str].
        - project_dir:  Đường dẫn tuyệt đối thư mục gốc dự án.
        - schema_path:  Đường dẫn data_schema.json.
    - Output:
        - list[str]: List dòng log tóm tắt của toàn bộ lần chạy.
    """
    project_path             = Path(project_dir)
    schema, strict_required  = _get_dataset_schema(schema_path)

    summary_lines = [f'Schema: {schema} (strict_required={strict_required})']
    for in_path_str, out_path_str in in_out_pairs:
        in_path  = project_path / in_path_str
        out_path = project_path / out_path_str

        if not in_path.exists():
            print(f"[SKIP] Không tìm thấy: {in_path}")
            summary_lines.append(f'[SKIP] Không tìm thấy: {in_path}')
            continue

        summary_lines.append(f'[{in_path.name}]')
        summary_lines += _preprocess_file(
            in_path         = in_path,
            out_path        = out_path,
            schema          = schema,
            strict_required = strict_required,
        )

    return summary_lines


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")
    SCHEMA_DIR  = Path(__file__).parent / "data_schema.json"

    # TEST
    preprocess_config_test = {
        "log":                      "data_pipelines/samples/vietstock_labelling_step01_20260601_20260601_CHUAN.log.txt",
        "merge_output_files_into":  "",
        "in_out": [
            ["data_pipelines/samples/vietstock_data_20260601_20260601_CHUAN.jsonl",
             "data_pipelines/samples/vietstock_labelling_step01_20260601_20260601_CHUAN.jsonl"]
        ]
    }

    in_out_pairs             = preprocess_config_test.get("in_out", [])
    log_path_str             = preprocess_config_test.get("log")
    merge_output_files_into  = preprocess_config_test.get("merge_output_files_into")

    summary_lines = preprocess_files(
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
        schema_path  = SCHEMA_DIR,
    )

    if log_path_str:
        process_write_run_log(Path(PROJECT_DIR) / log_path_str, summary_lines, SCHEMA_DIR)

    if merge_output_files_into:
        out_paths = [Path(PROJECT_DIR) / out_path_str for _, out_path_str in in_out_pairs]
        process_merge_output_files(out_paths, Path(PROJECT_DIR) / merge_output_files_into)


    # PROD 23-26
    preprocess_config_23_26 = {
        "log":                      "data/processing/step01_preprocess/vietstock_labelling_step01_2023_2026.log.txt",
        "merge_output_files_into":  "",
        "in_out": [
            ["data/raw/vietstock/vietstock_data_2023_2026.jsonl",
             "data/processing/step01_preprocess/vietstock_labelling_step01_2023_2026.jsonl"]
        ]
    }

    in_out_pairs             = preprocess_config_23_26.get("in_out", [])
    log_path_str             = preprocess_config_23_26.get("log")
    merge_output_files_into  = preprocess_config_23_26.get("merge_output_files_into")

    summary_lines = preprocess_files(
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
        schema_path  = SCHEMA_DIR,
    )

    if log_path_str:
        process_write_run_log(Path(PROJECT_DIR) / log_path_str, summary_lines, SCHEMA_DIR)

    if merge_output_files_into:
        out_paths = [Path(PROJECT_DIR) / out_path_str for _, out_path_str in in_out_pairs]
        process_merge_output_files(out_paths, Path(PROJECT_DIR) / merge_output_files_into)

    # EXTERNAL (22)
    preprocess_config_22 = {
        "log":                      "data/processing/step01_preprocess/vietstock_labelling_step01_2022.log.txt",
        "merge_output_files_into":  "",
        "in_out": [
            ["data/raw/vietstock/vietstock_data_2022.jsonl",
             "data/processing/step01_preprocess/vietstock_labelling_step01_2022.jsonl"]
        ]
    }

    in_out_pairs             = preprocess_config_22.get("in_out", [])
    log_path_str             = preprocess_config_22.get("log")
    merge_output_files_into  = preprocess_config_22.get("merge_output_files_into")

    summary_lines = preprocess_files(
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
        schema_path  = SCHEMA_DIR,
    )

    if log_path_str:
        process_write_run_log(Path(PROJECT_DIR) / log_path_str, summary_lines, SCHEMA_DIR)

    if merge_output_files_into:
        out_paths = [Path(PROJECT_DIR) / out_path_str for _, out_path_str in in_out_pairs]
        process_merge_output_files(out_paths, Path(PROJECT_DIR) / merge_output_files_into)
