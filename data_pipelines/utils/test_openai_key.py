import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv


def test_openai_key(api_key: str, model: str = "gpt-4o-mini", prompt: str = "Say hello in one word."):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=20,
    )
    reply = response.choices[0].message.content.strip()
    print(f"[OK] Key works. Model: {model}")
    print(f"Response: {reply}")
    return reply


if __name__ == "__main__":
    # Load key from .env at data_pipelines/
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    api_key = os.getenv("OPENAI_KEY")

    # --- Tham số ---
    model = "gpt-4o-mini"
    prompt = "Trả lời tôi bạn là ai? Không quá 15 từ bằng tiếng Việt."
    # ----------------

    if not api_key:
        print("[ERROR] OPENAI_KEY not found in .env")
    else:
        test_openai_key(api_key=api_key, model=model, prompt=prompt)
