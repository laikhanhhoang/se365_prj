if __name__ == "__main__":
    PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
    ENV_PATH    = PROJECT_DIR / "data_pipelines/.env"

    _env           = dotenv_values(str(ENV_PATH))
    OPENAI_API_KEY = _env.get("OPENAI_KEY") or _env.get("OPENAI_API_KEY")

    augmentation_config = {
        "dataset": PROJECT_DIR / "data/processed/train.jsonl",
        "dataset_schema": PROJECT_DIR / "ml/common/dataset_schema.yaml",
        "augmented_dataset_output_path": PROJECT_DIR / "data/processed/augmented_train.jsonl",
        "log_output_path": PROJECT_DIR / "data/processed/augmentation_log.jsonl",
        "unbalanced_events": ["Niêm yết", "Tổn thất tài sản nghi"],
        "quantity_needed": 800,
        "external_datasets": [
            # PROJECT_DIR / "data/processed/external1.jsonl",
            # PROJECT_DIR / "data/processed/external2.jsonl",
        ],
        "auto_augment_with_openai": {
            "model": "gpt-4",
            "temperature": 0.7,
            "instruction_prompt_path": Path(__file__).resolve().parent / "instruction_prompt.txt",
            "output_path": PROJECT_DIR / "data/processed/only_auto_augmented.jsonl",
        }
    }

    if augmentation_config.get("external_datasets"):
        # Add thêm các sample có sự kiện nằm trong list "unbalanced_events" vào output dataset
        pass

    if augmentation_config.get("auto_augment_with_openai"):
        # Gọi OpenAI API tạo thêm sample có sự kiện nằm trong list "unbalanced_events" đến khi đủ "quantity_needed" và lưu vào output dataset
        pass
        

