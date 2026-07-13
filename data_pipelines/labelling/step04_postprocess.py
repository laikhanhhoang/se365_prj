import json
import re
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

_CODE_FENCE    = "```"
_COMMON_FIELDS = ["event_type", "confidence"]  # có ở mọi event, không tính riêng theo events_fields

_RECHECK_CATEGORY_LABELS = {
    "parse":      "lỗi parse",
    "event_type": "event_type lạ",
    "field":      "lệch field",
}  # thứ tự dict cũng là thứ tự ưu tiên phân loại 1 sample vào đúng 1 category


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


def _get_output_schema_fields(schema_path: Path) -> list[str]:
    """
    - Summary: Đọc output_schema từ data_schema.json.
    - Args:
        - schema_path: Đường dẫn data_schema.json.
    - Output:
        - list[str]: List tên field được giữ lại ở record output.
    """
    dataset = json.loads(schema_path.read_text(encoding='utf-8'))["dataset"]
    return dataset["output_schema"]


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


def _normalize_record_to_schema(
    events:        list[dict],
    events_fields: dict[str, list[str]],
    sample_id:     str,
) -> tuple[list[dict], int, int]:
    """
    - Summary: Chuẩn hoá list event theo schema, tự sửa field thiếu/thừa.
    - Args:
        - events:        List event đã parse từ model.
        - events_fields: Dict tên sự kiện → list field kỳ vọng.
        - sample_id:     Id sample, dùng để log warning.
    - Output:
        - tuple[list[dict], int, int]: List event đã chuẩn hoá, số event_type lạ bị bỏ, số event bị lệch field.
    """
    normalized_events: list[dict] = []
    unknown_type_count            = 0
    field_issue_count             = 0

    for event in events:
        event_type = event.get("event_type")
        if event_type not in events_fields:
            unknown_type_count += 1
            print(f"[WARN] Sample {sample_id} - event_type lạ, không có trong schema: "
                  f"'{event_type}' → đã bỏ")
            continue

        missing_fields, extra_fields = _get_field_diff(event, events_fields)
        if missing_fields or extra_fields:
            field_issue_count += 1
            print(f"[WARN] Sample {sample_id} - event '{event_type}': "
                  f"thiếu {missing_fields or '{}'}, thừa {extra_fields or '{}'}")

        expected_fields  = set(_COMMON_FIELDS) | set(events_fields[event_type])
        normalized_event = {field: value for field, value in event.items() if field in expected_fields}  # bỏ field thừa
        for field in missing_fields:
            normalized_event[field] = "medium" if field == "confidence" else None  # điền default cho field thiếu
        normalized_events.append(normalized_event)

    return normalized_events, unknown_type_count, field_issue_count


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

def _recheck_record(written_events: list[dict] | None, events_fields: dict[str, list[str]]) -> str | None:
    """
    - Summary: Recheck record sau khi đã ghi ra output, không tác động vào workflow chính.
    - Args:
        - written_events: List event đã ghi ra output (post-filter), None nếu parse lỗi.
        - events_fields:  Dict tên sự kiện → list field kỳ vọng.
    - Output:
        - str | None: Category lỗi phát hiện được ("parse"/"event_type"/"field"), None nếu record hợp lệ.
    """
    if written_events is None:
        return "parse"
    for event in written_events:
        if event.get("event_type") not in events_fields:
            return "event_type"  # về lý thuyết không xảy ra vì đã lọc trước khi ghi, giữ lại để phòng regression
    for event in written_events:
        missing_fields, extra_fields = _get_field_diff(event, events_fields)
        if missing_fields or extra_fields:
            return "field"
    return None


def _postprocess_file(
    in_path:              Path,
    out_path:             Path,
    raw_field:            str,
    output_field:         str,
    events_fields:        dict[str, list[str]],
    output_schema_fields: list[str],
) -> list[str]:
    """
    - Summary:
        1. Tải records từ input (_get_records()).
        2. Parse và ghi từng record (_build_formatted_record()).
        3. Chuẩn hóa record theo schema (_normalize_record_to_schema()): Bỏ event có event_type lạ và field thừa trong từng event - Nếu thiếu "confidence", điền "medium'. Còn nếu field cần extracted nào bị thiếu thì điền null. 
        4. Recheck độc lập record sau khi đã ghi (_recheck_record()), phân loại lỗi theo category.
        5. Trả về log tóm tắt, kèm id từng sample lỗi theo từng category recheck.
    - Args:
        - in_path:              Đường dẫn file input JSONL.
        - out_path:             Đường dẫn file output JSONL.
        - raw_field:            Tên trường chứa JSON thô cần parse.
        - output_field:         Tên trường sẽ chứa kết quả đã parse.
        - events_fields:        Dict tên sự kiện → list field kỳ vọng.
        - output_schema_fields: List field được giữ lại ở record output.
    - Output:
        - list[str]: List dòng log tóm tắt của file này.
    """
    records = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    failed_count       = 0
    unknown_type_count = 0
    field_issue_count  = 0
    recheck_ids_by_category: dict[str, list[str]] = {category: [] for category in _RECHECK_CATEGORY_LABELS}
    with out_path.open('w', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'postprocess {in_path.name}', ncols=100):
            formatted_record = _build_formatted_record(dict(record), raw_field, output_field)
            events           = formatted_record[output_field]
            if events is None:
                failed_count += 1
                print(f"[WARN] Parse lỗi sample {record.get('id')}")
            else:
                normalized_events, record_unknown_count, record_field_issue_count = _normalize_record_to_schema(
                    events        = events,
                    events_fields = events_fields,
                    sample_id     = record.get('id'),
                )
                unknown_type_count             += record_unknown_count
                field_issue_count              += record_field_issue_count
                formatted_record[output_field]  = normalized_events
            formatted_record = {field: formatted_record[field] for field in output_schema_fields if field in formatted_record}
            fout.write(json.dumps(formatted_record, ensure_ascii=False) + '\n')

            recheck_category = _recheck_record(formatted_record.get(output_field), events_fields)
            if recheck_category:
                recheck_ids_by_category[recheck_category].append(str(record.get('id')))
                print(f"[WARN] Recheck lỗi sample {record.get('id')}: {_RECHECK_CATEGORY_LABELS[recheck_category]}")

    total_recheck_count = sum(len(ids) for ids in recheck_ids_by_category.values())
    summary_lines = [
        f'  postprocess: {len(records)} record '
        f'(lỗi parse: {failed_count}, event_type lạ: {unknown_type_count}, lệch field: {field_issue_count}) → {out_path.name}'
    ]
    if total_recheck_count:
        counts_str = ', '.join(f'{label}: {len(recheck_ids_by_category[category])}'
                                for category, label in _RECHECK_CATEGORY_LABELS.items())
        summary_lines.append(f'  recheck lỗi ({total_recheck_count} sample) ({counts_str})')
        for category, label in _RECHECK_CATEGORY_LABELS.items():
            ids = recheck_ids_by_category[category]
            if ids:
                summary_lines.append(f'      {label}: {", ".join(ids)}')
    else:
        summary_lines.append(f'  RECHECK: không phát hiện lỗi')
    print('\n'.join(summary_lines))
    return summary_lines


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
        2. Đọc output_schema (_get_output_schema_fields()).
        3. Resolve đường dẫn từng cặp in/out.
        4. Xử lý từng file (_postprocess_file()).
    - Args:
        - raw_field:    Tên trường chứa JSON thô cần parse.
        - output_field: Tên trường sẽ chứa kết quả đã parse.
        - in_out_pairs: List các cặp [input_path_str, output_path_str].
        - project_dir:  Đường dẫn tuyệt đối thư mục gốc dự án.
        - schema_path:  Đường dẫn data_schema.json.
    - Output:
        - list[str]: List dòng log tóm tắt của toàn bộ lần chạy.
    """
    project_path         = Path(project_dir)
    events_fields        = _get_events_fields(schema_path)
    output_schema_fields = _get_output_schema_fields(schema_path)

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
            in_path              = in_path,
            out_path             = out_path,
            raw_field            = raw_field,
            output_field         = output_field,
            events_fields        = events_fields,
            output_schema_fields = output_schema_fields,
        )

    return summary_lines


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")
    SCHEMA_DIR  = Path(__file__).parent / "data_schema.json"

    # TEST
    postprocess_config_test = {
        "raw_field":                "label_raw",
        "output_field":             "events",
        "log":                      "data_pipelines/samples/vietstock_labelling_step04_20260601_20260601_CHUAN.log.txt",
        "merge_output_files_into":  "",
        "in_out": [
            ["data_pipelines/samples/vietstock_labelling_step03_20260601_20260601_CHUAN.jsonl",
             "data_pipelines/samples/vietstock_labelling_step04_20260601_20260601_CHUAN.jsonl"]
        ]
    }

    raw_field, output_field = postprocess_config_test.get("raw_field", "label_raw"), postprocess_config_test.get("output_field", "events")
    in_out_pairs            = postprocess_config_test.get("in_out", [])
    log_path_str            = postprocess_config_test.get("log")
    merge_output_files_into = postprocess_config_test.get("merge_output_files_into")

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



    # PROD 23-26
    postprocess_config = {
        "raw_field":                "label_raw",
        "output_field":             "events",
        "log":                      "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026.log.txt",
        "merge_output_files_into":  "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026.jsonl",
        "in_out": [
            ["data/processing/step03_autolabel_v2/vietstock_labelling_step03_2023_2026_PART_1.jsonl",
             "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026_PART_1.jsonl"],
            ["data/processing/step03_autolabel_v2/vietstock_labelling_step03_2023_2026_PART_2.jsonl",
             "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026_PART_2.jsonl"],
            ["data/processing/step03_autolabel_v2/vietstock_labelling_step03_2023_2026_PART_3.jsonl",
             "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026_PART_3.jsonl"],
            ["data/processing/step03_autolabel_v2/vietstock_labelling_step03_2023_2026_PART_4.jsonl",
             "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026_PART_4.jsonl"],
            ["data/processing/step03_autolabel_v2/vietstock_labelling_step03_2023_2026_PART_5.jsonl",
             "data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026_PART_5.jsonl"]
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


    # EXTERNAL (22)
    postprocess_config_22 = {
        "raw_field":                "label_raw",
        "output_field":             "events",
        "log":                      "data/processing/step04_postprocess/vietstock_labelling_step04_2022.log.txt",
        "merge_output_files_into":  "",
        "in_out": [
            ["data/processing/step03_autolabel_v2/vietstock_labelling_step03_2022.jsonl",
             "data/processing/step04_postprocess/vietstock_labelling_step04_2022.jsonl"]
        ]
    }

    raw_field, output_field = postprocess_config_22.get("raw_field", "label_raw"), postprocess_config_22.get("output_field", "events")
    in_out_pairs            = postprocess_config_22.get("in_out", [])
    log_path_str            = postprocess_config_22.get("log")
    merge_output_files_into = postprocess_config_22.get("merge_output_files_into")

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
