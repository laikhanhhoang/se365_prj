from pathlib import Path

from datasets import Dataset

import json


def _get_records(jsonl_path: Path) -> list[dict]:
    """
    - Summary: Đọc toàn bộ record hợp lệ từ 1 file JSONL.
    - Args:
        - jsonl_path: Đường dẫn file JSONL.
    - Output:
        - list[dict]: Danh sách record hợp lệ.
    """
    records: list[dict] = []
    with jsonl_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records


def _get_field_diff(record: dict, schema_fields: set[str]) -> tuple[set[str], set[str]]:
    """
    - Summary: So khớp field của record với dataset_schema.
    - Args:
        - record:        Dict 1 record đã đọc từ JSONL.
        - schema_fields: Tập tên field kỳ vọng.
    - Output:
        - tuple[set[str], set[str]]: Tập field bị thiếu, tập field thừa.
    """
    actual_fields = set(record.keys())
    return schema_fields - actual_fields, actual_fields - schema_fields


def _build_records_from_file(jsonl_path: Path, schema_fields: set[str]) -> list[dict]:
    """
    - Summary:
        1. Đọc record từ file (_get_records()).
        2. Validate field từng record (_get_field_diff()).
        3. Bỏ record thiếu field, giữ đúng field theo schema.
    - Args:
        - jsonl_path:    Đường dẫn file JSONL (step04 output).
        - schema_fields: Tập tên field kỳ vọng.
    - Output:
        - list[dict]: Danh sách record hợp lệ, đã lọc đúng field.
    """
    valid_records: list[dict] = []
    for record in _get_records(jsonl_path):
        missing_fields, extra_fields = _get_field_diff(record, schema_fields)
        if missing_fields:
            print(f"[WARN] {jsonl_path.name} - sample {record.get('id')}: thiếu field {missing_fields} → bỏ")
            continue
        if extra_fields:
            print(f"[WARN] {jsonl_path.name} - sample {record.get('id')}: thừa field {extra_fields} → đã lọc")
        valid_records.append({field: record[field] for field in schema_fields if field in record})
    return valid_records


def build_training_dataset(jsonl_paths: list[Path], dataset_schema: dict) -> Dataset:
    """
    - Summary:
        1. Đọc field kỳ vọng từ dataset_schema.yaml.
        2. Đọc và validate record từng file (_build_records_from_file()).
        3. Gộp toàn bộ record hợp lệ thành 1 Dataset.
    - Args:
        - jsonl_paths:    List đường dẫn file JSONL (step04 output).
        - dataset_schema: Dict đã load từ dataset_schema.yaml.
    - Output:
        - Dataset: HuggingFace Dataset gồm các record hợp lệ, đã validate theo schema.
    """
    schema_fields = set(dataset_schema["fields"])

    all_records: list[dict] = []
    for jsonl_path in jsonl_paths:
        all_records += _build_records_from_file(jsonl_path, schema_fields)

    return Dataset.from_list(all_records)
