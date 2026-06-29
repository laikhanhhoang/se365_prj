import json
import sys
import os
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


def _call_openai(client: OpenAI, model: str, temperature: float, prompt: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"\n[WARN] API lỗi (lần {attempt + 1}): {e}. Thử lại sau {wait}s...")
                time.sleep(wait)
            else:
                raise


def label_files(config: dict, project_dir: str):
    """Gọi OpenAI để label từng record, lưu label_raw vào JSONL output."""
    project_path = Path(project_dir)

    api_key = (
        config.get("openai_api_key")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_KEY")
    )
    if not api_key:
        raise ValueError("Thiếu API key. Đặt trong label_config['openai_api_key'] hoặc biến môi trường OPENAI_KEY.")

    client      = OpenAI(api_key=api_key)
    model       = config.get("model", "gpt-4o-mini")
    temperature = config.get("temperature", 0.2)

    prompt_path     = project_path / config["prompt_file"]
    prompt_template = prompt_path.read_text(encoding='utf-8')

    for in_str, out_str in config.get("in_out", []):
        in_path  = project_path / in_str
        out_path = project_path / out_str

        if not in_path.exists():
            print(f"[SKIP] Không tìm thấy: {in_path}")
            continue

        existing_ids: set[str] = set()
        if out_path.exists():
            with out_path.open(encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            existing_ids.add(json.loads(line)["id"])
                        except Exception:
                            pass

        records: list[dict] = []
        with in_path.open(encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass

        out_path.parent.mkdir(parents=True, exist_ok=True)
        new_count = 0
        with out_path.open('a', encoding='utf-8') as fout:
            for record in tqdm.tqdm(records, desc=f'label {in_path.name}', ncols=100):
                if record.get("id") in existing_ids:
                    continue
                prompt = prompt_template.replace("{{content}}", record.get("content", ""))
                record["label_raw"] = _call_openai(client, model, temperature, prompt)
                fout.write(json.dumps(record, ensure_ascii=False) + '\n')
                new_count += 1

        print(f'  label: {new_count} mới / {len(records)} tổng (đã có: {len(existing_ids)}) → {out_path.name}')


if __name__ == "__main__":
    PROJECT_DIR = get_project_abs_dir_str_from_env(".env")
    ENV_PATH    = Path(__file__).parent.parent / ".env"   # data_pipelines/.env

    _env = dotenv_values(str(ENV_PATH))
    OPENAI_API_KEY = _env.get("OPENAI_KEY") or _env.get("OPENAI_API_KEY")

    label_config = {
        "openai_api_key": OPENAI_API_KEY,
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "prompt_file": "data_pipelines/label/prompt.txt",  # chứa "{{content}}" sẽ được thay bằng content
        "in_out": [
            ["data_pipelines/label/vietstock_formatted_20260601_20260601_CHUAN.jsonl",
             "data_pipelines/label/vietstock_labeled_20260601_20260601_CHUAN.jsonl"],
            # ["data/processing/formatted/vietstock_filter_config1_2023_2026.jsonl",
            #  "data/processing/labeled/vietstock_filter_config1_2023_2026.jsonl"]
        ]
    }

    label_files(label_config, PROJECT_DIR)
