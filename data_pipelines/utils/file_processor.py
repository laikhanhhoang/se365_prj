import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


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


def _build_split_output_paths(input_file: Path, output_dir: Path, parts: int) -> list[Path]:
    """
    - Summary: Tạo list đường dẫn output cho từng phần.
    - Args:
        - input_file: Đường dẫn file JSONL gốc.
        - output_dir: Thư mục chứa các file sau khi chia.
        - parts:      Số phần cần chia.
    - Output:
        - list[Path]: List đường dẫn output, tên dạng "{tên gốc}_PART_{i}.jsonl".
    """
    return [
        output_dir / f"{input_file.stem}_PART_{i}{input_file.suffix}"
        for i in range(1, parts + 1)
    ]


def _build_split_chunks(records: list[dict], parts: int) -> list[list[dict]]:
    """
    - Summary: Chia list record thành `parts` phần gần bằng nhau.
    - Args:
        - records: List record cần chia.
        - parts:   Số phần cần chia.
    - Output:
        - list[list[dict]]: List các phần, phần đầu nhận thêm record dư (nếu có).
    """
    total_records        = len(records)
    base_size, remainder = divmod(total_records, parts)

    chunks = []
    start  = 0
    for i in range(parts):
        chunk_size = base_size + (1 if i < remainder else 0)
        chunks.append(records[start:start + chunk_size])
        start += chunk_size
    return chunks


def process_split_jsonl_file(input_file: str, output_dir: str, parts: int):
    """
    - Summary:
        1. Đọc toàn bộ record từ input (_get_records()).
        2. Chia record thành `parts` phần gần bằng nhau (_build_split_chunks()).
        3. Build đường dẫn output cho từng phần (_build_split_output_paths()).
        4. Ghi từng phần ra file JSONL riêng.
    - Args:
        - input_file: Đường dẫn file JSONL gốc.
        - output_dir: Thư mục chứa các file sau khi chia.
        - parts:      Số phần cần chia.
    - Output:
        - None. Ghi `parts` file JSONL vào output_dir.
    """
    input_path  = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    records   = _get_records(input_path)
    chunks    = _build_split_chunks(records, parts)
    out_paths = _build_split_output_paths(input_path, output_path, parts)

    for out_path, chunk in zip(out_paths, chunks):
        with out_path.open('w', encoding='utf-8') as fout:
            for record in chunk:
                fout.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f'  {len(chunk)} record → {out_path.name}')

    print(f'Đã chia {len(records)} record thành {parts} phần vào {output_path}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Xử lý file (chia JSONL thành nhiều phần, ...)')
    parser.add_argument('--split_jsonl_file', action='store_true',
                        help='Chia 1 file JSONL thành nhiều phần bằng nhau')
    parser.add_argument('--parts',       dest='parts',       type=int, default=None,
                        help='Số phần cần chia (VD: 5)')
    parser.add_argument('--input_file', dest='input_file',  default=None,
                        help='File JSONL gốc cần chia')
    parser.add_argument('--output_dir', dest='output_dir',  default=None,
                        help='Thư mục chứa các file sau khi chia')
    args = parser.parse_args()

    if args.split_jsonl_file:
        if not (args.parts and args.input_file and args.output_dir):
            parser.error('--split_jsonl_file cần --parts, --input_file, --output_dir')
        process_split_jsonl_file(
            input_file = args.input_file,
            output_dir = args.output_dir,
            parts      = args.parts,
        )
    else:
        parser.error('Cần chỉ định 1 action, VD: --split_jsonl_file')
