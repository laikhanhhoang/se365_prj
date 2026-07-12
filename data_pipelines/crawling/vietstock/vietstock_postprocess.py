import json, sys, tqdm
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from data_pipelines.utils.dir_processor import get_project_abs_dir_str_from_env
from data_pipelines.utils.file_processor import process_merge_output_files


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


def _format_vietstock_record(record: dict) -> dict:
    """
    - Summary: Format record crawled ["id", "link", "title", "head", "body"] thành ["id", "content"] với "content" = "Tiêu đề: {title}\n Nội dung: {head} \n {body}".
    - Args:
        - record: Dict dữ liệu gốc của 1 sample (chưa chuẩn hóa theo schema).
    - Output:
        - dict: Dict dữ liệu chuẩn, chỉ gồm "id" và "content".
    """
    title = record.get("title") or ""
    head  = record.get("head")  or ""
    body  = record.get("body")  or ""
    return {
        "id":      record.get("id"),
        "content": f"Tiêu đề: {title}\n Nội dung: {head} \n {body}",
    }


def _postprocess_crawled_data_file(in_path: Path, out_path: Path) -> None:
    """
    - Summary:
        1. Tải records từ input (_get_records()).
        2. Format từng record (_format_vietstock_record()).
        3. Ghi kết quả ra output.
    - Args:
        - in_path:  Đường dẫn file input JSONL (crawled thô).
        - out_path: Đường dẫn file output JSONL (đã format).
    - Output:
        - None. Ghi kết quả vào out_path.
    """
    records = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'postprocess {in_path.name}', ncols=100):
            formatted_record = _format_vietstock_record(record)
            fout.write(json.dumps(formatted_record, ensure_ascii=False) + '\n')

    print(f'  {len(records)} record → {out_path.name}')


def postprocess_crawled_data_files(
    in_out_pairs: list,
    project_dir:  str,
) -> None:
    """
    - Summary:
        1. Resolve đường dẫn từng cặp in/out.
        2. Xử lý từng file (_postprocess_crawled_data_file()).
    - Args:
        - in_out_pairs: List các cặp [input_path_str, output_path_str].
        - project_dir:  Đường dẫn tuyệt đối thư mục gốc dự án.
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

        _postprocess_crawled_data_file(in_path, out_path)

if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")


    # TEST
#    vietstock_postprocess_config_test = {
#        "in_out": [
#            ["data_pipelines/samples/vietstock_crawled_data_20260601_20260601_CHUAN.jsonl",
#             "data_pipelines/samples/vietstock_data_20260601_20260601_CHUAN.jsonl"],
#        ],
#        "merge_output_files_into": "",
#    }
#    
#    in_out_pairs             = vietstock_postprocess_config_test.get("in_out", [])
#    merge_output_files_into  = vietstock_postprocess_config_test.get("merge_output_files_into", )
#
#    postprocess_crawled_data_files(
#        in_out_pairs = in_out_pairs,
#        project_dir  = PROJECT_DIR,
#    )
#
#    if merge_output_files_into:
#        out_paths = [Path(PROJECT_DIR) / out_path_str for _, out_path_str in in_out_pairs]
#        process_merge_output_files(out_paths, Path(PROJECT_DIR) / merge_output_files_into)

    
    # PROD
    vietstock_postprocess_config_23_26 = {
        "in_out": [
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20230101_20230430.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20230101_20230430.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20230501_20230831.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20230501_20230831.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20230901_20231231.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20230901_20231231.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240101_20240131.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240101_20240131.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240201_20240229.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240201_20240229.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240301_20240331.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240301_20240331.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240401_20240430.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240401_20240430.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240501_20240630.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240501_20240630.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240701_20240831.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240701_20240831.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20240901_20241031.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20240901_20241031.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20241101_20241231.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20241101_20241231.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250101_20250131.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250101_20250131.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250201_20250228.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250201_20250228.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250301_20250331.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250301_20250331.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250401_20250430.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250401_20250430.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250501_20250531.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250501_20250531.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250601_20250630.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250601_20250630.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250701_20250731.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250701_20250731.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20250801_20251231.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20250801_20251231.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20260101_20260131.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20260101_20260131.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20260201_20260228.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20260201_20260228.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20260301_20260331.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20260301_20260331.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20260401_20260430.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20260401_20260430.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20260501_20260531.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20260501_20260531.jsonl"],
            ["data/raw/vietstock/crawled/vietstock_crawled_data_20260601_20260620.jsonl", 
             "data/raw/vietstock/post_crawled/vietstock_post_crawled_data_20260601_20260620.jsonl"]
        ],
        "merge_output_files_into": "data/raw/vietstock/vietstock_data_2023_2026.jsonl"
    }
    
    in_out_pairs             = vietstock_postprocess_config_23_26.get("in_out", [])
    merge_output_files_into  = vietstock_postprocess_config_23_26.get("merge_output_files_into", )

    postprocess_crawled_data_files(
        in_out_pairs = in_out_pairs,
        project_dir  = PROJECT_DIR,
    )

    if merge_output_files_into:
        out_paths = [Path(PROJECT_DIR) / out_path_str for _, out_path_str in in_out_pairs]
        process_merge_output_files(out_paths, Path(PROJECT_DIR) / merge_output_files_into)
