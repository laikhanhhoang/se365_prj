import json
import sys
from pathlib import Path

import numpy as np
from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from data_pipelines.utils.dir_processor import get_project_abs_dir_str_from_env
from data_pipelines.utils.file_processor import process_write_run_log

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
        - list[dict]: Danh sách record hợp lệ.
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


def _get_field_diff(event: dict, events_fields: dict[str, list[str]]) -> tuple[set[str], set[str]]:
    """
    - Summary: So khớp field của event với data_schema.json.
    - Args:
        - event:         Dict 1 event đã parse từ model.
        - events_fields: Dict tên sự kiện → list field kỳ vọng.
    - Output:
        - tuple[set[str], set[str]]: Tập field bị thiếu, tập field thừa.
    """
    expected_fields = set(_COMMON_FIELDS) | set(events_fields.get(event.get("event_type"), []))
    actual_fields   = set(event.keys())
    return expected_fields - actual_fields, actual_fields - expected_fields


def _get_validation_issues(record: dict, events_fields: dict[str, list[str]]) -> list[str]:
    """
    - Summary: Kiểm tra event_type lạ và field thiếu/thừa của 1 record.
    - Args:
        - record:        Dict record đã đọc từ JSONL (có field "events").
        - events_fields: Dict tên sự kiện → list field kỳ vọng.
    - Output:
        - list[str]: List mô tả lỗi phát hiện được, rỗng nếu record hợp lệ.
    """
    issues: list[str] = []
    for event in record.get("events") or []:
        event_type = event.get("event_type")
        if event_type not in events_fields:
            issues.append(f"event_type lạ: '{event_type}'")
            continue
        missing_fields, extra_fields = _get_field_diff(event, events_fields)
        if missing_fields or extra_fields:
            issues.append(f"event '{event_type}': thiếu {missing_fields or '{}'}, thừa {extra_fields or '{}'}")
    return issues


def _validate_records(records: list[dict], events_fields: dict[str, list[str]]) -> list[str]:
    """
    - Summary:
        1. Kiểm tra event_type lạ + field thiếu/thừa từng record (_get_validation_issues()).
        2. In warning cho record có lỗi.
    - Args:
        - records:      List record cần kiểm tra.
        - events_fields: Dict tên sự kiện → list field kỳ vọng.
    - Output:
        - list[str]: List dòng log tóm tắt kết quả kiểm tra.
    """
    invalid_count = 0
    for record in records:
        issues = _get_validation_issues(record, events_fields)
        if issues:
            invalid_count += 1
            print(f"[WARN] Sample {record.get('id')}: {'; '.join(issues)}")

    summary = f'  validate: {len(records)} record, {invalid_count} record có event lỗi (event_type lạ hoặc thiếu/thừa field)'
    print(summary)
    return [summary]


def _build_label_matrix(records: list[dict], event_type_names: list[str]) -> np.ndarray:
    """
    - Summary: Build ma trận multi-hot presence event_type + no-event.
    - Args:
        - records:          List record cần build label.
        - event_type_names: List tên loại sự kiện theo schema.
    - Output:
        - np.ndarray: Ma trận N x (len(event_type_names) + 1), cột cuối là no-event.
    """
    labels = np.zeros((len(records), len(event_type_names) + 1), dtype=int)
    for row_idx, record in enumerate(records):
        events = record.get("events") or []
        if not events:
            labels[row_idx, -1] = 1
            continue
        present_types = {event.get("event_type") for event in events}
        for col_idx, event_type_name in enumerate(event_type_names):
            if event_type_name in present_types:
                labels[row_idx, col_idx] = 1
    return labels


def _build_stratified_split(
    labels:       np.ndarray,
    val_ratio:    float,
    test_ratio:   float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    - Summary: Chia index train/val/test, giữ tỷ lệ label (multi-label stratify).
    - Args:
        - labels:       Ma trận multi-hot label (N x K).
        - val_ratio:    Tỷ lệ tập val trên tổng dataset.
        - test_ratio:   Tỷ lệ tập test trên tổng dataset.
        - random_state: Seed để split lặp lại được.
    - Output:
        - tuple[np.ndarray, np.ndarray, np.ndarray]: Index của train, val, test.
    """
    indices = np.arange(len(labels))

    splitter_test         = MultilabelStratifiedShuffleSplit(n_splits=1, test_size=test_ratio, random_state=random_state)
    trainval_idx, test_idx = next(splitter_test.split(indices, labels))

    val_ratio_of_remainder     = val_ratio / (1 - test_ratio)
    splitter_val                = MultilabelStratifiedShuffleSplit(n_splits=1, test_size=val_ratio_of_remainder, random_state=random_state)
    train_idx_rel, val_idx_rel  = next(splitter_val.split(trainval_idx, labels[trainval_idx]))

    train_idx = trainval_idx[train_idx_rel]
    val_idx   = trainval_idx[val_idx_rel]
    return train_idx, val_idx, test_idx


def _get_distribution_summary(records: list[dict], event_type_names: list[str]) -> dict:
    """
    - Summary: Tính số lượng và tỷ lệ no-event, từng loại sự kiện.
    - Args:
        - records:          List record cần thống kê.
        - event_type_names: List tên loại sự kiện theo schema.
    - Output:
        - dict: Thống kê tổng, no-event, và từng loại sự kiện.
    """
    total           = len(records)
    no_event_count  = sum(1 for record in records if not (record.get("events") or []))
    has_event_count = total - no_event_count

    per_type_counts = {name: 0 for name in event_type_names}
    for record in records:
        present_types = {event.get("event_type") for event in (record.get("events") or [])}
        for name in present_types:
            if name in per_type_counts:
                per_type_counts[name] += 1

    return {
        "total":           total,
        "no_event_count":  no_event_count,
        "no_event_ratio":  (no_event_count / total) if total else 0.0,
        "has_event_count": has_event_count,
        "per_type": {
            name: {
                "count": count,
                "ratio": (count / has_event_count) if has_event_count else 0.0,
            }
            for name, count in per_type_counts.items()
        },
    }


def _build_distribution_log(split_name: str, records: list[dict], event_type_names: list[str]) -> list[str]:
    """
    - Summary: Build log tỷ lệ no-event và từng loại sự kiện của 1 tập.
    - Args:
        - split_name:       Tên tập (VD: "Tổng dataset", "Train", "Val", "Test").
        - records:          List record của tập này.
        - event_type_names: List tên loại sự kiện theo schema.
    - Output:
        - list[str]: List dòng log của tập này.
    """
    summary = _get_distribution_summary(records, event_type_names)
    lines = [
        f'[{split_name}] {summary["total"]} mẫu',
        f'  Không sự kiện: {summary["no_event_count"]} ({summary["no_event_ratio"]:.2%} trên tổng {summary["total"]} mẫu)',
        f'  Có sự kiện: {summary["has_event_count"]} mẫu — tỷ lệ từng loại tính trên {summary["has_event_count"]} mẫu này:',
    ]
    for name, stat in sorted(summary["per_type"].items(), key=lambda item: item[1]["count"], reverse=True):
        lines.append(f'    {name}: {stat["count"]} ({stat["ratio"]:.2%})')
    return lines


def _process_write_records(records: list[dict], out_path: Path) -> None:
    """
    - Summary: Ghi list record ra file JSONL.
    - Args:
        - records: List record cần ghi.
        - out_path: Đường dẫn file output.
    - Output:
        - None. Ghi file JSONL tại out_path.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def process_split_dataset(
    in_paths:     list[Path],
    out_dir:      Path,
    schema_path:  Path,
    val_ratio:    float,
    test_ratio:   float,
    random_state: int,
) -> list[str]:
    """
    - Summary:
        1. Đọc field từng loại sự kiện (_get_events_fields()).
        2. Đọc và gộp record từ các file input (_get_records()).
        3. Kiểm tra event_type lạ + field thiếu/thừa (_validate_records()).
        4. Build ma trận multi-hot label (_build_label_matrix()).
        5. Chia train/val/test giữ tỷ lệ label (_build_stratified_split()).
        6. Ghi 3 file train/val/test (_process_write_records()).
        7. Build log tỷ lệ từng tập (_build_distribution_log()).
    - Args:
        - in_paths:     List đường dẫn file input JSONL (step04 output).
        - out_dir:      Thư mục ghi 3 file train/val/test.
        - schema_path:  Đường dẫn data_schema.json.
        - val_ratio:    Tỷ lệ tập val trên tổng dataset.
        - test_ratio:   Tỷ lệ tập test trên tổng dataset.
        - random_state: Seed để split lặp lại được.
    - Output:
        - list[str]: List dòng log tóm tắt (tỷ lệ + số mẫu từng tập).
    """
    events_fields     = _get_events_fields(schema_path)
    event_type_names  = list(events_fields.keys())

    records: list[dict] = []
    for in_path in in_paths:
        records += _get_records(in_path)

    summary_lines = _validate_records(records, events_fields)

    labels                        = _build_label_matrix(records, event_type_names)
    train_idx, val_idx, test_idx  = _build_stratified_split(labels, val_ratio, test_ratio, random_state)

    train_records = [records[i] for i in train_idx]
    val_records   = [records[i] for i in val_idx]
    test_records  = [records[i] for i in test_idx]

    _process_write_records(train_records, out_dir / "train.jsonl")
    _process_write_records(val_records,   out_dir / "val.jsonl")
    _process_write_records(test_records,  out_dir / "test.jsonl")
    print(f'Đã chia {len(records)} record → train: {len(train_records)}, val: {len(val_records)}, test: {len(test_records)}')

    summary_lines.append('')
    summary_lines += _build_distribution_log("Tổng dataset", records,        event_type_names)
    summary_lines.append('')
    summary_lines += _build_distribution_log("Train",        train_records, event_type_names)
    summary_lines.append('')
    summary_lines += _build_distribution_log("Val",          val_records,   event_type_names)
    summary_lines.append('')
    summary_lines += _build_distribution_log("Test",         test_records,  event_type_names)

    return summary_lines


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")
    SCHEMA_DIR  = Path(__file__).parent / "data_schema.json"

    split_config = {
        "in_paths":     ["data/processing/step04_postprocess/vietstock_labelling_step04_2023_2026.jsonl"],
        "out_dir":      "data/processed",
        "val_ratio":    0.08,
        "test_ratio":   0.12,
        "random_state": 42,
        "log":          "data/processed/_split_data.log.txt",
    }

    in_paths, out_dir     = split_config.get("in_paths", []), split_config.get("out_dir", "data/processed")
    val_ratio, test_ratio = split_config.get("val_ratio", 0.1), split_config.get("test_ratio", 0.1)
    random_state          = split_config.get("random_state", 42)
    log_path_str          = split_config.get("log")

    summary_lines = process_split_dataset(
        in_paths     = [Path(PROJECT_DIR) / p for p in in_paths],
        out_dir      = Path(PROJECT_DIR) / out_dir,
        schema_path  = SCHEMA_DIR,
        val_ratio    = val_ratio,
        test_ratio   = test_ratio,
        random_state = random_state,
    )

    if log_path_str:
        process_write_run_log(Path(PROJECT_DIR) / log_path_str, summary_lines, SCHEMA_DIR)