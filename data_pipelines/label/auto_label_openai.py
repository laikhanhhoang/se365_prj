import sys, os, json, time
from pathlib import Path
from openai import OpenAI, RateLimitError
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))
from utils.prj_dir import prj_dir_str


PRJ_ABS_DIR = prj_dir_str()


# ─── IO ───────────────────────────────────────────────────────────────────────

def load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(records: list[dict], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ─── Core logic ───────────────────────────────────────────────────────────────

def build_prompt(sample: dict, prompt_template: str) -> str:
    return prompt_template.format(**sample)


def label_one(
    client: OpenAI,
    sample: dict,
    system_prompt: str,
    prompt_template: str,
    model: str,
    max_retries: int = 5,
) -> dict:
    prompt = build_prompt(sample, prompt_template)
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt},
                ],
            )
            raw = response.choices[0].message.content.strip()
            return {**sample, "label_raw": raw}
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s, 16s


def label_file(
    input_file: str,
    output_file: str,
    api_key: str,
    model: str,
    system_prompt: str,
    prompt_template: str,
    max_consecutive_errors: int = 5,
) -> None:
    samples = load_jsonl(input_file)
    print(f"  Loaded {len(samples)} samples from {input_file}")

    client = OpenAI(api_key=api_key)
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    consecutive_errors = 0

    with open(output_file, "w", encoding="utf-8") as f_out:
        for i, sample in enumerate(samples):
            try:
                result = label_one(client, sample, system_prompt, prompt_template, model)
                f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
                f_out.flush()
                consecutive_errors = 0
                print(f"  [{i+1}/{len(samples)}] OK  id={sample.get('id')}")
            except Exception as e:
                consecutive_errors += 1
                print(f"  [{i+1}/{len(samples)}] ERROR id={sample.get('id')}: {e}")
                f_out.write(json.dumps({**sample, "label_raw": None, "error": str(e)}, ensure_ascii=False) + "\n")
                f_out.flush()
                if consecutive_errors >= max_consecutive_errors:
                    raise RuntimeError(f"Dừng: {max_consecutive_errors} lỗi liên tiếp.")

    print(f"  Done. Output: {output_file}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(
    env_path: str,
    config_path: str,
):
    if env_path is None:
        env_path = (Path(__file__).parent / ".env").as_posix()
    elif Path(env_path).is_absolute():
        env_path = Path(env_path).as_posix()
    else:
        env_path = (Path(PRJ_ABS_DIR) / env_path).resolve().as_posix()

    print(f"Tìm thấy .env tại: {env_path}")

    if config_path is None:
        config_path = (Path(__file__).parent / "config.json").as_posix()
    elif Path(config_path).is_absolute():
        config_path = Path(config_path).as_posix()
    else:
        config_path = (Path(PRJ_ABS_DIR) / config_path).resolve().as_posix()
    
    print(f"Tìm thấy config.json tại: {config_path}")

    load_dotenv(env_path)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    api_key         = os.getenv("OPENAI_KEY")
    model           = config.get("model", "gpt-4o-mini")
    system_prompt   = config.get("system_prompt", "")
    prompt_template = config.get("prompt_template", "")
    input_output_files = config.get("in_out", [])

    print(f"{api_key[0:6]} - model {model} - system_prompt {system_prompt[0:20]} - prompt_template {prompt_template}")

    for in_out_file in input_output_files:
        input_file  = (Path(PRJ_ABS_DIR) / in_out_file[0]).resolve().as_posix()
        output_file = (Path(PRJ_ABS_DIR) / in_out_file[1]).resolve().as_posix()

        print(f"\n[Processing] {Path(input_file).name}")
        label_file(
            input_file      = input_file,
            output_file     = output_file,
            api_key         = api_key,
            model           = model,
            system_prompt   = system_prompt,
            prompt_template = prompt_template,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--env",    help="Path to the .env file")
    parser.add_argument("--config", help="Path to the config file")
    args = parser.parse_args()

    main(env_path=args.env, config_path=args.config)
