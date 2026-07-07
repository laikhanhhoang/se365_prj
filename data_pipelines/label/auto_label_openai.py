import json
import sys
import time
from pathlib import Path

import tqdm
from dotenv import dotenv_values
from openai import OpenAI

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from data_pipelines.utils.dir_processor import get_project_abs_dir_str_from_env


def _get_existing_ids(out_path: Path) -> set[str]:
    """
    - Summary: Đọc file output, trả về tập id đã xử lý.
    - Args:
        - out_path: Đường dẫn file output JSONL.
    - Output:
        - set[str]: Tập id đã tồn tại trong output.
    """
    existing_ids: set[str] = set()
    if not out_path.exists():
        return existing_ids
    with out_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    existing_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    return existing_ids


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


def _build_prompt(prompt_template: str, content: str) -> str:
    """
    - Summary: Thay {{content}} trong template bằng nội dung record.
    - Args:
        - prompt_template: Chuỗi template có chứa "{{content}}".
        - content:         Nội dung bài viết cần chèn vào.
    - Output:
        - str: Prompt hoàn chỉnh sẵn sàng gửi API.
    """
    return prompt_template.replace("{{content}}", content)


def _get_response_from_openai_api(
    client:      OpenAI,
    model:       str,
    temperature: float,
    prompt:      str,
    max_retries: int = 3,
) -> tuple[str, int]:
    """
    - Summary: Gọi OpenAI API, retry exponential backoff khi lỗi.
    - Args:
        - client:      OpenAI client đã khởi tạo.
        - model:       Tên model (vd: "gpt-4o-mini").
        - temperature: Độ ngẫu nhiên của model.
        - prompt:      Nội dung prompt gửi lên API.
        - max_retries: Số lần retry tối đa.
    - Output:
        - tuple[str, int]: Phản hồi từ model đã được strip, và tổng số token đã dùng.
    """
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model       = model,
                messages    = [{"role": "user", "content": prompt}],
                temperature = temperature,
            )
            return resp.choices[0].message.content.strip(), resp.usage.total_tokens
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"\n[WARN] API lỗi (lần {attempt + 1}): {e}. Thử lại sau {wait}s...")
                time.sleep(wait)
            else:
                raise


def _process_file(
    in_path:         Path,
    out_path:        Path,
    client:          OpenAI,
    model:           str,
    temperature:     float,
    prompt_template: str,
):
    """
    - Summary:
        1. Tải id đã xử lý (_get_existing_ids()).
        2. Tải records từ input (_get_records()).
        3. Build prompt và gọi API (_build_prompt(), _get_response_from_openai_api()).
        4. Ghi label_raw vào output, in tiến độ và token từng sample.
        5. In tổng thời gian và tổng token đã dùng cho file.
    - Args:
        - in_path:         Đường dẫn file input JSONL.
        - out_path:        Đường dẫn file output JSONL.
        - client:          OpenAI client đã khởi tạo.
        - model:           Tên model.
        - temperature:     Độ ngẫu nhiên của model.
        - prompt_template: Template prompt có "{{content}}".
    - Output:
        - None. Ghi kết quả vào out_path (append).
    """
    existing_ids = _get_existing_ids(out_path)
    records      = _get_records(in_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_count   = 0
    total_token = 0
    start_time  = time.time()
    with out_path.open('a', encoding='utf-8') as fout:
        for record in tqdm.tqdm(records, desc=f'label {in_path.name}', ncols=100):
            sample_id = record.get("id")
            if sample_id in existing_ids:
                continue

            print(f"bắt đầu xử lí sample {sample_id}...")
            prompt                    = _build_prompt(prompt_template, record.get("content", ""))
            label_raw, used_token     = _get_response_from_openai_api(client, model, temperature, prompt)
            record["label_raw"]       = label_raw
            total_token              += used_token
            fout.write(json.dumps(record, ensure_ascii=False) + '\n')
            new_count += 1
            print(f"đã xử lí xong sample {sample_id}, tốn {used_token} token")

    elapsed_seconds = time.time() - start_time
    print(f'  label: {new_count} mới / {len(records)} tổng (đã có: {len(existing_ids)}) → {out_path.name}')
    print(f'  thời gian xử lý: {elapsed_seconds:.2f}s, tổng token đã dùng: {total_token}')


def process_files(
    in_out_pairs:    list,
    project_dir:     str,
    client:          OpenAI,
    model:           str,
    temperature:     float,
    prompt_template: str,
):
    """
    - Summary:
        1. Resolve đường dẫn từng cặp in/out.
        2. Xử lý từng file (_process_file()).
    - Args:
        - in_out_pairs:    List các cặp [input_path_str, output_path_str].
        - project_dir:     Đường dẫn tuyệt đối thư mục gốc dự án.
        - client:          OpenAI client đã khởi tạo.
        - model:           Tên model.
        - temperature:     Độ ngẫu nhiên của model.
        - prompt_template: Template prompt có "{{content}}".
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

        _process_file(
            in_path         = in_path,
            out_path        = out_path,
            client          = client,
            model           = model,
            temperature     = temperature,
            prompt_template = prompt_template,
        )


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")
    ENV_PATH    = Path(__file__).parent.parent / ".env"   # data_pipelines/.env

    _env           = dotenv_values(str(ENV_PATH))
    OPENAI_API_KEY = _env.get("OPENAI_KEY") or _env.get("OPENAI_API_KEY")

    label_config = {
        "model":       "gpt-4o-mini",
        "temperature": 0.2,
        "prompt_file": "data_pipelines/label/prompt.txt",  # chứa "{{content}}" sẽ được thay bằng content
        "in_out": [
            #["data_pipelines/label/vietstock_preprocessed_20260601_20260601_CHUAN.jsonl",
            # "data_pipelines/label/vietstock_labeled_raw_20260601_20260601_CHUAN.jsonl"],
            ["data/processing/preprocess/vietstock_preprocessed_filter_config1_2023_2026_PART_1.jsonl",
             "data/processing/label/prompt1/vietstock_labeled_raw_prompt1_filter_config1_2023_2026_PART_1.jsonl"]
        ]
    }

    model, temperature = label_config.get("model", "gpt-4o-mini"), label_config.get("temperature", 0.2)
    in_out_pairs       = label_config.get("in_out", [])
    prompt_template    = (Path(PROJECT_DIR) / label_config["prompt_file"]).read_text(encoding='utf-8')
    client             = OpenAI(api_key=OPENAI_API_KEY)

    process_files(
        in_out_pairs    = in_out_pairs,
        project_dir     = PROJECT_DIR,
        client          = client,
        model           = model,
        temperature     = temperature,
        prompt_template = prompt_template,
    )
