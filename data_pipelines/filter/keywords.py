import json
import sys
from pathlib import Path

import tqdm

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_DIR         = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_FILE = Path(__file__).parent / 'config.json'


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


# ─────────────────────────────────────────────
# LOGIC THUẦN (không đụng file)
# ─────────────────────────────────────────────

def filter_by_keywords(
    input: str | list[str],
    keyword: dict[str, list[str]],
) -> list[str]:
    """
    Trả về list event_id khớp với văn bản đầu vào.

    Args:
        input:   chuỗi văn bản, hoặc list các chuỗi (sẽ được nối lại bằng dấu cách)
        keyword: dict mapping event_id → list cụm từ cần khớp
                 VD: {"01": ["cổ tức", "trả cổ tức"], "02": [...]}

    Returns:
        list event_id có ít nhất 1 cụm từ xuất hiện trong văn bản
    """
    text = ' '.join(input) if isinstance(input, list) else input

    matched = []
    for event_id, keywords in keyword.items():
        for kw in keywords:
            if kw in text:
                matched.append(event_id)
                break
    return matched


# ─────────────────────────────────────────────
# I/O FILE
# ─────────────────────────────────────────────

def _process_file(
    input_path: Path,
    output_path: Path,
    keyword: dict[str, list[str]],
) -> dict:
    """Đọc 1 file JSONL, lọc theo keyword, ghi ra file output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_data = []
    with input_path.open(encoding='utf-8') as f:
        for line in tqdm.tqdm(f, desc=f'reading {input_path.name}', ncols=100):
            line = line.strip()
            if line:
                all_data.append(json.loads(line))

    hit, filtered = [], []
    event_count: dict[str, int] = {}

    for dict_data in tqdm.tqdm(all_data, desc='filtering', ncols=100):
        title = dict_data.get('title', '') or ''
        head  = dict_data.get('head',  '') or ''
        body  = dict_data.get('body',  '') or ''

        if not title and not body:
            filtered.append(dict_data)
            continue

        categories = filter_by_keywords([title, head, body], keyword)

        if categories:
            for cat in categories:
                event_count[cat] = event_count.get(cat, 0) + 1
            dict_data['rule_category'] = categories
            hit.append(dict_data)
        else:
            filtered.append(dict_data)

    with output_path.open('w', encoding='utf-8') as f:
        for d in hit:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')

    print(f'  {len(hit)} giữ lại / {len(all_data)} tổng ({len(filtered)} lọc bỏ)')

    return {
        'hit':      len(hit),
        'total':    len(all_data),
        'filtered': len(filtered),
        'by_event': event_count,
    }


def _print_event_table(by_event: dict[str, int], event_name: dict[str, str], log):
    for event_id in sorted(event_name.keys()):
        name  = event_name.get(event_id, '')
        count = by_event.get(event_id, 0)
        log(f'  {event_id}  {name:<34}  {count:>5} bài')


def main(
    config_path: str | Path = DEFAULT_CONFIG_FILE,
    log_path: str | Path | None = None,
):
    """Đọc config.json và chạy filter cho tất cả cặp in_out."""
    config_path = _resolve(config_path)
    config      = json.loads(config_path.read_text(encoding='utf-8'))

    keyword      = config['keyword']
    in_out_pairs = config['in_out']
    event_name   = config.get('event_name', {})
    combine_path = config.get('combine') or None

    total_hit, total_all = 0, 0
    total_by_event: dict[str, int] = {}

    log_lines: list[str] = []
    def log(msg: str = ''):
        print(msg)
        log_lines.append(msg)

    log(f'Config: {config_path}')
    log(f'Số cặp file: {len(in_out_pairs)}')
    log()

    for input_dir, output_dir in in_out_pairs:
        log(f'[{Path(input_dir).name}]')
        result = _process_file(_resolve(input_dir), _resolve(output_dir), keyword)
        total_hit += result['hit']
        total_all += result['total']
        for k, v in result['by_event'].items():
            total_by_event[k] = total_by_event.get(k, 0) + v
        log()

    log('=' * 55)
    log('TỔNG KẾT')
    log('=' * 55)
    log(f'Tổng bài đầu vào : {total_all:>6}')
    log(f'Giữ lại          : {total_hit:>6}  ({total_hit/total_all*100:.1f}%)')
    log(f'Lọc bỏ           : {total_all - total_hit:>6}  ({(total_all-total_hit)/total_all*100:.1f}%)')
    log()
    log(f'  {"ID":<4}  {"Tên event":<34}  {"Số bài":>7}')
    log(f'  {"-"*4}  {"-"*34}  {"-"*7}')
    _print_event_table(total_by_event, event_name, log)
    log('=' * 55)

    if log_path is not None:
        log_file = Path(__file__).parent / log_path
        log_file.write_text('\n'.join(log_lines), encoding='utf-8')
        print(f'\nLog đã ghi: {log_file}')

    if combine_path is not None:
        combined = _resolve(combine_path)
        combined.parent.mkdir(parents=True, exist_ok=True)
        with combined.open('w', encoding='utf-8') as f_out:
            for _, output_dir in in_out_pairs:
                out_file = _resolve(output_dir)
                if out_file.exists():
                    f_out.write(out_file.read_text(encoding='utf-8'))
        print(f'Đã gộp {len(in_out_pairs)} file → {combined}')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Lọc bài báo theo từ khóa sự kiện')
    parser.add_argument('--in',     dest='input_dir',  default=None,
                        help='File JSONL đầu vào  (VD: data/raw/vietstock/data.jsonl)')
    parser.add_argument('--out',    dest='output_dir', default=None,
                        help='File JSONL đầu ra   (VD: data/processing/filter/data.jsonl)')
    parser.add_argument('--kwfile', dest='kwfile',     default=DEFAULT_CONFIG_FILE,
                        help='File config.json cho mode đơn lẻ (mặc định: config.json)')
    parser.add_argument('--config', dest='config',     default=None,
                        help='File config.json cho mode toàn bộ')
    parser.add_argument('--log',    dest='log_path',   default=None,
                        help='Tên file log trong thư mục filter/ (VD: log.txt)')
    args = parser.parse_args()

    if args.config:
        main(config_path=args.config, log_path=args.log_path)
    elif args.input_dir and args.output_dir:
        config = json.loads(_resolve(args.kwfile).read_text(encoding='utf-8'))
        _process_file(_resolve(args.input_dir), _resolve(args.output_dir), config['keyword'])
    else:
        main(log_path=args.log_path)
