import json
import random
from pathlib import Path


def _get_records(jsonl_path: Path) -> list[dict]:
    """
    - Summary: Đọc toàn bộ record hợp lệ từ file JSONL.
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


def _write_jsonl(records: list[dict], out_path: Path):
    """
    - Summary: Ghi list record ra file JSONL, ghi đè.
    - Args:
        - records: List record cần ghi.
        - out_path: Đường dẫn file output JSONL.
    - Output:
        - None. Ghi file tại out_path.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def _build_random_subset(records: list[dict], quantity: int) -> list[dict]:
    """
    - Summary: Lấy ngẫu nhiên quantity record, không lặp lại.
    - Args:
        - records: List record nguồn.
        - quantity: Số lượng mẫu cần lấy.
    - Output:
        - list[dict]: Subset ngẫu nhiên, tối đa quantity record.
    """
    if quantity >= len(records):
        return records
    return random.sample(records, quantity)


def _process_file(in_path: Path, out_path: Path, quantity: int):
    """
    - Summary:
        1. Đọc record từ input (_get_records()).
        2. Lấy ngẫu nhiên quantity record (_build_random_subset()).
        3. Ghi subset ra output (_write_jsonl()).
    - Args:
        - in_path: Đường dẫn file input JSONL.
        - out_path: Đường dẫn file output JSONL.
        - quantity: Số lượng mẫu random cần lấy.
    - Output:
        - None. Ghi file subset tại out_path.
    """
    if not in_path.exists():
        print(f"[SKIP] Không tìm thấy: {in_path}")
        return

    records = _get_records(in_path)
    subset  = _build_random_subset(records, quantity)
    _write_jsonl(subset, out_path)
    print(f"  {in_path.name}: lấy {len(subset)}/{len(records)} record → {out_path.name}")


def process_files(quantity: int, in_out_pairs: list[list[str]], project_dir: Path):
    """
    - Summary:
        1. Duyệt từng cặp in_out (_process_file()).
        2. Ghép đường dẫn tương đối với project_dir.
    - Args:
        - quantity: Số lượng mẫu random cần lấy.
        - in_out_pairs: List cặp [đường dẫn input, đường dẫn output], tương đối project_dir.
        - project_dir: Thư mục gốc project.
    - Output:
        - None. Ghi file subset cho từng cặp in_out.
    """
    for in_rel_path, out_rel_path in in_out_pairs:
        _process_file(
            in_path  = project_dir / in_rel_path,
            out_path = project_dir / out_rel_path,
            quantity = quantity,
        )


if __name__ == "__main__":
    PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
    config = [
        {
            "quantity": 10, # Số lượng mẫu random cần lấy
            "in_out": [
                ["data/processed/augmented_train.jsonl", "ml/samples/augmented_train_subset.jsonl"],
                ["data/processed/train_v1.jsonl", "ml/samples/train_v1_subset.jsonl"]
            ]
        }
    ]

    for entry in config:
        process_files(
            quantity     = entry["quantity"],
            in_out_pairs = entry["in_out"],
            project_dir  = PROJECT_DIR,
        )
