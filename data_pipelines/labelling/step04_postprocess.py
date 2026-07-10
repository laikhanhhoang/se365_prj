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
from data_pipelines.utils.file_processor import process_write_run_log, process_merge_output_files

_CODE_FENCE    = "```"
_COMMON_FIELDS = ["event_type", "confidence"]  # có ở mọi event, không tính riêng theo events_fields


def _get_events_fields(schema_path: Path) -> dict[str, list[str]]:
    """
    - Summary: Đọc field từng loại sự kiện từ data_schema.json.
    - Args:
        - schema_path: Đường dẫn data_schema.json.
    - Output:
        - dict[str, list[str]]: Dict tên sự kiện → list field.
    """
    events = json.loads(schema_path.read_text(encoding='utf-8'))["events"]
    return {event["name"]: event["fields"] for event in events}


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


def _get_field_diff(event: dict, events_fields: dict[str, list[str]]) -> tuple[set[str], set[str]]:
    """
    - Summary: So khớp field của event với data_schema.json.
    - Args:
        - event:         Dict 1 event đã parse từ model.
        - events_fields: Dict tên sự kiện → list field kỳ vọng.
    - Output:
        - tuple[set[str], set[str]]: Tập field bị thiếu, tập field thừa (model bịa).
    """
    expected_fields = set(_COMMON_FIELDS) | set(events_fields.get(event.get("event_type"), []))
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


def _postprocess_file(
    in_path:       Path,
    out_path:      Path,
    raw_field:     str,
    output_field:  str,
    events_fields: dict[str, list[str]],
) -> list[str]:
    """
    - Summary:
        1. Tải records từ input (_get_records()).
        2. Parse và ghi từng record (_build_formatted_record()).
        3. Bỏ event có event_type lạ, không có trong data_schema.json.
        4. Check field thiếu/thừa từng event còn lại (_get_field_diff()).
    - Args:
        - in_path:       Đường dẫn file input JSONL.
        - out_path:      Đường dẫn file output JSONL.
        - raw_field:     Tên trường chứa JSON thô cần parse.
        - output_field:  Tên trường sẽ chứa kết quả đã parse.
        - events_fields: Dict tên sự kiện → list field kỳ vọng.
    - Output:
        - list[str]: List dòng log tóm tắt của file này.
    """
    records = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    failed_count       = 0
    unknown_type_count = 0
    field_issue_count  = 0
    with out_path.open('w', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'postprocess {in_path.name}', ncols=100):
            formatted_record = _build_formatted_record(dict(record), raw_field, output_field)
            events           = formatted_record[output_field]
            if events is None:
                failed_count += 1
                print(f"[WARN] Parse lỗi sample {record.get('id')}")
            else:
                known_events = []
                for event in events:
                    event_type = event.get("event_type")
                    if event_type not in events_fields:
                        unknown_type_count += 1
                        print(f"[WARN] Sample {record.get('id')} - event_type lạ, không có trong schema: "
                              f"'{event_type}' → đã bỏ")
                        continue
                    missing_fields, extra_fields = _get_field_diff(event, events_fields)
                    if missing_fields or extra_fields:
                        field_issue_count += 1
                        print(f"[WARN] Sample {record.get('id')} - event '{event_type}': "
                              f"thiếu {missing_fields or '{}'}, thừa {extra_fields or '{}'}")
                    known_events.append(event)
                formatted_record[output_field] = known_events
            fout.write(json.dumps(formatted_record, ensure_ascii=False) + '\n')

    summary = (
        f'  postprocess: {len(records)} record '
        f'(lỗi parse: {failed_count}, event_type lạ: {unknown_type_count}, lệch field: {field_issue_count}) → {out_path.name}'
    )
    print(summary)
    return [summary]


def postprocess_files(
    raw_field:    str,
    output_field: str,
    in_out_pairs: list,
    project_dir:  str,
    schema_path:  Path,
) -> list[str]:
    """
    - Summary:
        1. Đọc field từng loại sự kiện (_get_events_fields()).
        2. Resolve đường dẫn từng cặp in/out.
        3. Xử lý từng file (_postprocess_file()).
    - Args:
        - raw_field:    Tên trường chứa JSON thô cần parse.
        - output_field: Tên trường sẽ chứa kết quả đã parse.
        - in_out_pairs: List các cặp [input_path_str, output_path_str].
        - project_dir:  Đường dẫn tuyệt đối thư mục gốc dự án.
        - schema_path:  Đường dẫn data_schema.json.
    - Output:
        - list[str]: List dòng log tóm tắt của toàn bộ lần chạy.
    """
    project_path  = Path(project_dir)
    events_fields = _get_events_fields(schema_path)

    summary_lines: list[str] = []
    for in_path_str, out_path_str in in_out_pairs:
        in_path  = project_path / in_path_str
        out_path = project_path / out_path_str

        if not in_path.exists():
            print(f"[SKIP] Không tìm thấy: {in_path}")
            summary_lines.append(f'[SKIP] Không tìm thấy: {in_path}')
            continue

        summary_lines.append(f'[{in_path.name}]')
        summary_lines += _postprocess_file(
            in_path       = in_path,
            out_path      = out_path,
            raw_field     = raw_field,
            output_field  = output_field,
            events_fields = events_fields,
        )

    return summary_lines


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")
    SCHEMA_DIR  = Path(__file__).parent / "data_schema.json"

    postprocess_config = {
        "raw_field":                "label_raw",
        "output_field":             "events",
        "log":                      "data_pipelines/labelling/logs/step04_postprocess.log.txt",
        "merge_output_files_into":  "",
        "in_out": [
            #["data_pipelines/labelling/samples/vietstock_labeled_raw_prompt1_20260601_20260601_CHUAN.jsonl",
            # "data_pipelines/labelling/samples/vietstock_labeled_20260601_20260601_CHUAN.jsonl"],
            ["data/processing/label/prompt1/vietstock_labeled_raw_prompt1_filter_config1_2023_2026_PART_1.jsonl",
             "data/processing/label/prompt1/vietstock_labeled_2023_2026_PART_1.jsonl"]
        ]
    }

    raw_field, output_field = postprocess_config.get("raw_field", "label_raw"), postprocess_config.get("output_field", "events")
    in_out_pairs            = postprocess_config.get("in_out", [])
    log_path_str            = postprocess_config.get("log")
    merge_output_files_into = postprocess_config.get("merge_output_files_into")

    summary_lines = postprocess_files(
        raw_field    = raw_field,
        output_field = output_field,
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
        schema_path  = SCHEMA_DIR,
    )

    if log_path_str:
        process_write_run_log(Path(PROJECT_DIR) / log_path_str, summary_lines, SCHEMA_DIR)

    if merge_output_files_into:
        out_paths = [Path(PROJECT_DIR) / out_path_str for _, out_path_str in in_out_pairs]
        process_merge_output_files(out_paths, Path(PROJECT_DIR) / merge_output_files_into)
