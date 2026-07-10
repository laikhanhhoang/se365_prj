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
from data_pipelines.utils.file_processor import process_write_run_log

_SCHEMA_PATH = Path(__file__).parent / "data_schema.json"


def _get_event_keywords(schema_path: Path) -> dict[str, list[str]]:
    """
    - Summary: Đọc keyword từng loại sự kiện từ data_schema.json.
    - Args:
        - schema_path: Đường dẫn data_schema.json.
    - Output:
        - dict[str, list[str]]: Dict tên sự kiện → list keyword.
    """
    events = json.loads(schema_path.read_text(encoding='utf-8'))["events"]
    return {event["name"]: event["keywords"] for event in events}


def filter_by_keywords(
    input: str | list[str],
    keyword: dict[str, list[str]],
) -> list[str]:
    """
    Trả về list tên sự kiện khớp với văn bản đầu vào.

    Args:
        input:   chuỗi văn bản, hoặc list các chuỗi (sẽ được nối lại bằng dấu cách)
        keyword: dict mapping tên sự kiện → list cụm từ cần khớp

    Returns:
        list tên sự kiện có ít nhất 1 cụm từ xuất hiện trong văn bản
    """
    text = ' '.join(input) if isinstance(input, list) else input

    matched = []
    for event_name, keywords in keyword.items():
        for kw in keywords:
            if kw in text:
                matched.append(event_name)
                break
    return matched


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


def _process_file(
    in_path:  Path,
    out_path: Path,
    keyword:  dict[str, list[str]],
) -> dict:
    """
    - Summary:
        1. Tải records từ input (_get_records()).
        2. Lọc theo keyword từng record (filter_by_keywords()).
        3. Ghi record khớp ra output.
    - Args:
        - in_path:  Đường dẫn file input JSONL.
        - out_path: Đường dẫn file output JSONL.
        - keyword:  Dict tên sự kiện → list keyword.
    - Output:
        - dict: Thống kê hit/total/filtered/by_event của file này.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records = _get_records(in_path)

    hit, filtered = [], []
    event_count: dict[str, int] = {}

    for record in tqdm.tqdm(records, desc=f'filtering {in_path.name}', ncols=100):
        title = record.get('title', '') or ''
        head  = record.get('head',  '') or ''
        body  = record.get('body',  '') or ''

        if not title and not body:
            filtered.append(record)
            continue

        matched_events = filter_by_keywords([title, head, body], keyword)

        if matched_events:
            for event_name in matched_events:
                event_count[event_name] = event_count.get(event_name, 0) + 1
            record['rule_category'] = matched_events
            hit.append(record)
        else:
            filtered.append(record)

    with out_path.open('w', encoding='utf-8') as f:
        for record in hit:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f'  {len(hit)} giữ lại / {len(records)} tổng ({len(filtered)} lọc bỏ) → {out_path.name}')

    return {
        'hit':      len(hit),
        'total':    len(records),
        'filtered': len(filtered),
        'by_event': event_count,
    }


def _build_event_table_lines(by_event: dict[str, int], event_names: list[str]) -> list[str]:
    """
    - Summary: Build bảng log số bài theo từng loại sự kiện.
    - Args:
        - by_event:    Dict tên sự kiện → số bài khớp.
        - event_names: List tên sự kiện theo thứ tự trong data_schema.json.
    - Output:
        - list[str]: List dòng log dạng bảng.
    """
    lines = [f'  {"Tên event":<34}  {"Số bài":>7}', f'  {"-"*34}  {"-"*7}']
    for event_name in event_names:
        count = by_event.get(event_name, 0)
        lines.append(f'  {event_name:<34}  {count:>5} bài')
    return lines


def process_files(
    in_out_pairs: list,
    project_dir:  str,
    keyword:      dict[str, list[str]],
    combine_path: str | None = None,
) -> list[str]:
    """
    - Summary:
        1. Resolve đường dẫn từng cặp in/out.
        2. Xử lý từng file (_process_file()).
        3. Gộp toàn bộ output thành 1 file (nếu có combine_path).
        4. Build bảng tổng kết theo loại sự kiện (_build_event_table_lines()).
    - Args:
        - in_out_pairs: List các cặp [input_path_str, output_path_str].
        - project_dir:  Đường dẫn tuyệt đối thư mục gốc dự án.
        - keyword:      Dict tên sự kiện → list keyword.
        - combine_path: Đường dẫn file gộp toàn bộ output (None nếu không gộp).
    - Output:
        - list[str]: List dòng log tóm tắt của toàn bộ lần chạy.
    """
    project_path = Path(project_dir)

    total_hit, total_all = 0, 0
    total_by_event: dict[str, int] = {}
    summary_lines: list[str] = []

    for in_path_str, out_path_str in in_out_pairs:
        in_path  = project_path / in_path_str
        out_path = project_path / out_path_str

        if not in_path.exists():
            print(f"[SKIP] Không tìm thấy: {in_path}")
            summary_lines.append(f'[SKIP] Không tìm thấy: {in_path}')
            continue

        result = _process_file(in_path, out_path, keyword)
        total_hit += result['hit']
        total_all += result['total']
        for event_name, count in result['by_event'].items():
            total_by_event[event_name] = total_by_event.get(event_name, 0) + count
        summary_lines.append(f'  {result["hit"]} giữ lại / {result["total"]} tổng → {out_path.name}')

    summary_lines.append('=' * 55)
    summary_lines.append('TỔNG KẾT')
    summary_lines.append('=' * 55)
    if total_all:
        summary_lines.append(f'Tổng bài đầu vào : {total_all:>6}')
        summary_lines.append(f'Giữ lại          : {total_hit:>6}  ({total_hit/total_all*100:.1f}%)')
        summary_lines.append(f'Lọc bỏ           : {total_all - total_hit:>6}  ({(total_all-total_hit)/total_all*100:.1f}%)')
    summary_lines += _build_event_table_lines(total_by_event, list(keyword.keys()))

    print('\n'.join(summary_lines))

    if combine_path is not None:
        combined = project_path / combine_path
        combined.parent.mkdir(parents=True, exist_ok=True)
        with combined.open('w', encoding='utf-8') as f_out:
            for _, out_path_str in in_out_pairs:
                out_file = project_path / out_path_str
                if out_file.exists():
                    f_out.write(out_file.read_text(encoding='utf-8'))
        print(f'Đã gộp {len(in_out_pairs)} file → {combined}')
        summary_lines.append(f'Đã gộp {len(in_out_pairs)} file → {combined}')

    return summary_lines


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")

    filter_config = {
        "combine": "data/processing/filter/config1/vietstock_filter_2023_2026.jsonl",
        "log":     "data_pipelines/labelling/logs/step02_filter.log.txt",
        "in_out": [
            ["data/raw/vietstock/vietstock_crawled_data_20230101_20230430.jsonl", "data/processing/filter/config1/vietstock_filter_20230101_20230430.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20230501_20230831.jsonl", "data/processing/filter/config1/vietstock_filter_20230501_20230831.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20230901_20231231.jsonl", "data/processing/filter/config1/vietstock_filter_20230901_20231231.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240101_20240131.jsonl", "data/processing/filter/config1/vietstock_filter_20240101_20240131.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240201_20240229.jsonl", "data/processing/filter/config1/vietstock_filter_20240201_20240229.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240301_20240331.jsonl", "data/processing/filter/config1/vietstock_filter_20240301_20240331.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240401_20240430.jsonl", "data/processing/filter/config1/vietstock_filter_20240401_20240430.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240501_20240630.jsonl", "data/processing/filter/config1/vietstock_filter_20240501_20240630.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240701_20240831.jsonl", "data/processing/filter/config1/vietstock_filter_20240701_20240831.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20240901_20241031.jsonl", "data/processing/filter/config1/vietstock_filter_20240901_20241031.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20241101_20241231.jsonl", "data/processing/filter/config1/vietstock_filter_20241101_20241231.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250101_20250131.jsonl", "data/processing/filter/config1/vietstock_filter_20250101_20250131.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250201_20250228.jsonl", "data/processing/filter/config1/vietstock_filter_20250201_20250228.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250301_20250331.jsonl", "data/processing/filter/config1/vietstock_filter_20250301_20250331.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250401_20250430.jsonl", "data/processing/filter/config1/vietstock_filter_20250401_20250430.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250501_20250531.jsonl", "data/processing/filter/config1/vietstock_filter_20250501_20250531.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250601_20250630.jsonl", "data/processing/filter/config1/vietstock_filter_20250601_20250630.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250701_20250731.jsonl", "data/processing/filter/config1/vietstock_filter_20250701_20250731.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20250801_20251231.jsonl", "data/processing/filter/config1/vietstock_filter_20250801_20251231.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20260101_20260131.jsonl", "data/processing/filter/config1/vietstock_filter_20260101_20260131.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20260201_20260228.jsonl", "data/processing/filter/config1/vietstock_filter_20260201_20260228.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20260301_20260331.jsonl", "data/processing/filter/config1/vietstock_filter_20260301_20260331.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20260401_20260430.jsonl", "data/processing/filter/config1/vietstock_filter_20260401_20260430.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20260501_20260531.jsonl", "data/processing/filter/config1/vietstock_filter_20260501_20260531.jsonl"],
            ["data/raw/vietstock/vietstock_crawled_data_20260601_20260620.jsonl", "data/processing/filter/config1/vietstock_filter_20260601_20260620.jsonl"]
        ]
    }

    in_out_pairs = filter_config.get("in_out", [])
    combine_path = filter_config.get("combine")
    log_path_str = filter_config.get("log")
    keyword      = _get_event_keywords(_SCHEMA_PATH)

    summary_lines = process_files(
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
        keyword      = keyword,
        combine_path = combine_path,
    )

    if log_path_str:
        process_write_run_log(Path(PROJECT_DIR) / log_path_str, summary_lines, _SCHEMA_PATH)
