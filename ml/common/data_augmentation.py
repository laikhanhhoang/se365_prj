import json
import random
import sys
import time
from pathlib import Path

import tqdm
import yaml
from dotenv import dotenv_values
from openai import OpenAI

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_COMMON_FIELDS      = ["event_type", "confidence"]  # có ở mọi event, không tính riêng theo fields của schema
_MAX_EXAMPLE_CHARS  = 1200  # cắt bớt ví dụ tham khảo để prompt không quá dài


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


def _write_log(log_path: Path, summary_lines: list[str]):
    """
    - Summary: Ghi log tóm tắt ra file.
    - Args:
        - log_path: Đường dẫn file log cần ghi.
        - summary_lines: List dòng log tóm tắt.
    - Output:
        - None. Ghi file tại log_path.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('\n'.join(summary_lines), encoding='utf-8')


def _get_event_type_counts(records: list[dict]) -> dict[str, int]:
    """
    - Summary: Đếm số sample theo từng loại sự kiện.
    - Args:
        - records: List record đã đọc từ dataset.
    - Output:
        - dict[str, int]: Dict event_type -> số lượng hiện có.
    """
    counts: dict[str, int] = {}
    for record in records:
        for event in record.get("events", []):
            event_type         = event.get("event_type")
            counts[event_type] = counts.get(event_type, 0) + 1
    return counts


def _get_deficit_by_event_type(
    unbalanced_events: list[str],
    event_type_counts: dict[str, int],
    quantity_needed:   int,
) -> dict[str, int]:
    """
    - Summary: Tính số lượng còn thiếu để đạt quantity_needed.
    - Args:
        - unbalanced_events: List event_type cần cân bằng.
        - event_type_counts: Dict event_type -> số lượng hiện có.
        - quantity_needed:   Số lượng mục tiêu cho mỗi event_type.
    - Output:
        - dict[str, int]: Dict event_type -> số lượng còn thiếu (>= 0).
    """
    return {
        event_type: max(quantity_needed - event_type_counts.get(event_type, 0), 0)
        for event_type in unbalanced_events
    }


def _get_output_event_type_counts(out_path: Path) -> dict[str, int]:
    """
    - Summary: Đếm sample đã sinh từ lần chạy trước trong file output.
    - Args:
        - out_path: Đường dẫn file output auto_augment (only_auto_augmented.jsonl).
    - Output:
        - dict[str, int]: Dict event_type -> số lượng đã sinh từ lần chạy trước, {} nếu chưa có file.
    """
    if not out_path.exists():
        return {}
    return _get_event_type_counts(_get_records(out_path))


def _get_remaining_quantity_by_event_type(
    deficit_by_event_type: dict[str, int],
    existing_counts:       dict[str, int],
) -> dict[str, int]:
    """
    - Summary: Trừ số sample đã sinh trước đó, chỉ còn phần thực sự cần sinh thêm.
    - Args:
        - deficit_by_event_type: Dict event_type -> số lượng cần đạt.
        - existing_counts: Dict event_type -> số lượng đã sinh từ lần chạy trước.
    - Output:
        - dict[str, int]: Dict event_type -> số lượng còn phải sinh thêm (>= 0).
    """
    return {
        event_type: max(quantity - existing_counts.get(event_type, 0), 0)
        for event_type, quantity in deficit_by_event_type.items()
    }


def _get_records_by_event_type(records: list[dict]) -> dict[str, list[dict]]:
    """
    - Summary: Gom nhóm record theo từng loại sự kiện chứa bên trong.
    - Args:
        - records: List record đã đọc từ dataset.
    - Output:
        - dict[str, list[dict]]: Dict event_type -> list record có chứa event_type đó.
    """
    grouped: dict[str, list[dict]] = {}
    for record in records:
        for event in record.get("events", []):
            grouped.setdefault(event.get("event_type"), []).append(record)
    return grouped


def _get_event_type_fields(schema_path: Path) -> dict[str, list[str]]:
    """
    - Summary: Đọc field từng loại sự kiện từ dataset_schema.yaml.
    - Args:
        - schema_path: Đường dẫn dataset_schema.yaml.
    - Output:
        - dict[str, list[str]]: Dict event_type -> list field.
    """
    schema = yaml.safe_load(schema_path.read_text(encoding='utf-8'))
    return {entry["event_type"]: entry["fields"] for entry in schema["event_fields"]}


def _get_event_type_field_descriptions(schema_path: Path) -> dict[str, dict[str, str]]:
    """
    - Summary: Đọc mô tả field từng loại sự kiện từ dataset_schema.yaml.
    - Args:
        - schema_path: Đường dẫn dataset_schema.yaml.
    - Output:
        - dict[str, dict[str, str]]: Dict event_type -> dict field -> mô tả.
    """
    schema = yaml.safe_load(schema_path.read_text(encoding='utf-8'))
    return {entry["event_type"]: entry.get("field_descriptions", {}) for entry in schema["event_fields"]}


def _build_fields_description_block(fields: list[str], field_descriptions: dict[str, str]) -> str:
    """
    - Summary: Build block liệt kê field kèm mô tả ý nghĩa.
    - Args:
        - fields: List tên field cần điền của event_type.
        - field_descriptions: Dict field -> mô tả (dataset_schema.yaml).
    - Output:
        - str: Block dạng "- field: mô tả", mỗi field 1 dòng.
    """
    return "\n".join(f"- {field}: {field_descriptions.get(field, '')}" for field in fields)


def _build_other_event_types_text(event_type: str, all_event_types: list[str]) -> str:
    """
    - Summary: Liệt kê các loại sự kiện khác, trừ event_type mục tiêu.
    - Args:
        - event_type: Loại sự kiện mục tiêu, cần loại khỏi danh sách.
        - all_event_types: List toàn bộ event_type trong dataset_schema.yaml.
    - Output:
        - str: Chuỗi các event_type khác, phân cách bởi dấu phẩy.
    """
    return ", ".join(f'"{other_type}"' for other_type in all_event_types if other_type != event_type)


def _select_external_records(records: list[dict], deficit_by_event_type: dict[str, int]) -> list[dict]:
    """
    - Summary:
        1. Duyệt từng record, xác định event_type còn thiếu trong record.
        2. Chọn record nếu chứa ít nhất 1 event_type còn thiếu.
        3. Giảm deficit tương ứng cho từng event_type đã dùng.
    - Args:
        - records: List record của 1 dataset external.
        - deficit_by_event_type: Dict event_type -> số lượng còn thiếu, bị mutate.
    - Output:
        - list[dict]: List record được chọn từ dataset này.
    """
    selected: list[dict] = []
    for record in records:
        event_types_in_record = {event.get("event_type") for event in record.get("events", [])}
        needed_types          = [et for et in event_types_in_record if deficit_by_event_type.get(et, 0) > 0]
        if not needed_types:
            continue

        selected.append(record)
        for event_type in needed_types:
            deficit_by_event_type[event_type] -= 1
    return selected


def build_augmented_from_external(
    external_paths:         list[Path],
    deficit_by_event_type:  dict[str, int],
) -> list[dict]:
    """
    - Summary:
        1. Đọc record từng file external (_get_records()).
        2. Chọn record chứa event_type còn thiếu (_select_external_records()).
    - Args:
        - external_paths: List đường dẫn file dataset external.
        - deficit_by_event_type: Dict event_type -> số lượng còn thiếu, bị mutate.
    - Output:
        - list[dict]: List record được chọn từ toàn bộ external dataset.
    """
    augmented_records: list[dict] = []
    for external_path in external_paths:
        if not external_path.exists():
            print(f"[SKIP] Không tìm thấy: {external_path}")
            continue

        records  = _get_records(external_path)
        selected = _select_external_records(records, deficit_by_event_type)
        augmented_records += selected
        print(f"  external {external_path.name}: chọn {len(selected)}/{len(records)} record")
    return augmented_records


def _build_augment_prompt(
    prompt_template:    str,
    event_type:         str,
    fields_description: str,
    same_event_example: str,
    diff_event_example: str,
    other_event_types:  str,
) -> str:
    """
    - Summary: Thay {{event_type}}, {{fields}}, 2 ví dụ tham khảo và {{other_event_types}}.
    - Args:
        - prompt_template: Chuỗi template instruction_prompt.txt.
        - event_type: Loại sự kiện cần sinh.
        - fields_description: Block mô tả field cần điền (_build_fields_description_block()).
        - same_event_example: Nội dung bài tham khảo cùng event_type.
        - diff_event_example: Nội dung bài tham khảo khác event_type.
        - other_event_types: Chuỗi liệt kê các loại sự kiện khác cần tránh nhắc tới.
    - Output:
        - str: Prompt hoàn chỉnh sẵn sàng gửi API.
    """
    return (
        prompt_template
        .replace("{{event_type}}", event_type)
        .replace("{{fields}}", fields_description)
        .replace("{{same_event_example}}", same_event_example)
        .replace("{{diff_event_example}}", diff_event_example)
        .replace("{{other_event_types}}", other_event_types)
    )


def _get_random_example_content(records: list[dict], fallback: str) -> str:
    """
    - Summary: Lấy ngẫu nhiên nội dung 1 record làm ví dụ tham khảo.
    - Args:
        - records: Pool record để chọn ngẫu nhiên.
        - fallback: Chuỗi trả về nếu pool rỗng.
    - Output:
        - str: Nội dung record (đã cắt bớt), hoặc fallback.
    """
    if not records:
        return fallback
    content = random.choice(records).get("content", "") or fallback
    return content[:_MAX_EXAMPLE_CHARS]


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
        - client: OpenAI client đã khởi tạo.
        - model: Tên model (vd: "gpt-4o-mini").
        - temperature: Độ ngẫu nhiên của model.
        - prompt: Nội dung prompt gửi lên API.
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


def _build_parsed_sample(response_raw: str) -> dict | None:
    """
    - Summary: Parse JSON thô của model thành sample {content, events}.
    - Args:
        - response_raw: Chuỗi phản hồi thô từ model (có thể kèm code fence).
    - Output:
        - dict | None: Sample đã parse, None nếu parse lỗi.
    """
    cleaned = response_raw.strip()

    if cleaned.startswith("```"):
        newline_idx = cleaned.find('\n')  # bỏ dòng mở fence, dù là ```json hay ``` trần
        cleaned     = cleaned[newline_idx + 1:] if newline_idx != -1 else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _get_field_diff(event: dict, expected_fields: set[str]) -> tuple[set[str], set[str]]:
    """
    - Summary: So khớp field của event với schema kỳ vọng.
    - Args:
        - event: Dict 1 event trong sample vừa sinh.
        - expected_fields: Tập field kỳ vọng của event_type.
    - Output:
        - tuple[set[str], set[str]]: Tập field bị thiếu, tập field thừa.
    """
    actual_fields = set(event.keys())
    return expected_fields - actual_fields, actual_fields - expected_fields


def _build_validated_sample(sample: dict | None, event_type: str, fields: list[str]) -> dict | None:
    """
    - Summary:
        1. Kiểm tra sample có content và ít nhất 1 event đúng event_type.
        2. Chuẩn hoá field từng event theo schema (_get_field_diff()).
    - Args:
        - sample: Sample thô vừa parse ({content, events} hoặc None).
        - event_type: Loại sự kiện kỳ vọng.
        - fields: List field kỳ vọng của event_type (dataset_schema.yaml).
    - Output:
        - dict | None: Sample đã chuẩn hoá, None nếu không hợp lệ.
    """
    if not sample or not sample.get("content") or not sample.get("events"):
        return None

    expected_fields    = set(_COMMON_FIELDS) | set(fields)
    normalized_events: list[dict] = []
    for event in sample["events"]:
        if event.get("event_type") != event_type:
            print(f"[WARN] Sample sinh sai event_type '{event.get('event_type')}' (kỳ vọng '{event_type}') → bỏ event")
            continue

        missing_fields, extra_fields = _get_field_diff(event, expected_fields)
        if missing_fields or extra_fields:
            print(f"[WARN] Sample '{event_type}' lệch field: thiếu {missing_fields or '{}'}, thừa {extra_fields or '{}'}")
        normalized_event = {field: value for field, value in event.items() if field in expected_fields}
        for field in missing_fields:
            normalized_event[field] = "medium" if field == "confidence" else None  # điền default cho field thiếu
        normalized_events.append(normalized_event)

    if not normalized_events:
        return None
    return {"content": sample["content"], "events": normalized_events}


def _build_auto_augmented_samples_for_event_type(
    event_type:         str,
    fields:             list[str],
    field_descriptions: dict[str, str],
    other_event_types:  str,
    quantity:           int,
    start_index:        int,
    output_path:        Path,
    prompt_template:    str,
    same_event_records: list[dict],
    diff_event_records: list[dict],
    client:             OpenAI,
    model:              str,
    temperature:        float,
):
    """
    - Summary:
        1. Build block mô tả field cho event_type (_build_fields_description_block()).
        2. Chọn ngẫu nhiên 2 ví dụ tham khảo cùng/khác event_type (_get_random_example_content()).
        3. Build prompt cho event_type (_build_augment_prompt()).
        4. Gọi API sinh sample (_get_response_from_openai_api()).
        5. Parse và chuẩn hoá sample (_build_parsed_sample(), _build_validated_sample()).
        6. Gán id và ghi ngay ra output_path (nối tiếp lần chạy trước), tránh mất dữ liệu nếu bị ngắt giữa chừng.
    - Args:
        - event_type: Loại sự kiện cần sinh thêm.
        - fields: List field cần điền của event_type.
        - field_descriptions: Dict field -> mô tả (dataset_schema.yaml).
        - other_event_types: Chuỗi liệt kê các loại sự kiện khác cần tránh nhắc tới.
        - quantity: Số lượng sample còn cần sinh (đã trừ phần đã sinh từ lần chạy trước).
        - start_index: Chỉ số bắt đầu đánh id, tiếp nối lần chạy trước.
        - output_path: Đường dẫn file output auto_augment, ghi nối tiếp (append).
        - prompt_template: Chuỗi template instruction_prompt.txt.
        - same_event_records: Pool record cùng event_type, dùng làm ví dụ tham khảo.
        - diff_event_records: Pool record khác event_type, dùng làm ví dụ tham khảo.
        - client: OpenAI client đã khởi tạo.
        - model: Tên model.
        - temperature: Độ ngẫu nhiên của model.
    - Output:
        - None. Ghi từng sample hợp lệ nối tiếp vào output_path.
    """
    if quantity <= 0:
        return

    fields_description = _build_fields_description_block(fields, field_descriptions)
    valid_count   = 0
    invalid_count = 0
    total_token   = 0
    with output_path.open('a', encoding='utf-8') as fout:
        for i in tqdm.tqdm(range(quantity), desc=f'auto-augment "{event_type}"', ncols=100):
            same_event_example = _get_random_example_content(same_event_records, "(chưa có ví dụ cùng loại)")
            diff_event_example = _get_random_example_content(diff_event_records, "(chưa có ví dụ khác loại)")
            prompt              = _build_augment_prompt(
                prompt_template    = prompt_template,
                event_type         = event_type,
                fields_description = fields_description,
                same_event_example = same_event_example,
                diff_event_example = diff_event_example,
                other_event_types  = other_event_types,
            )

            response_raw, used_token = _get_response_from_openai_api(client, model, temperature, prompt)
            total_token              += used_token
            sample                   = _build_validated_sample(_build_parsed_sample(response_raw), event_type, fields)
            if sample is None:
                invalid_count += 1
                print(f"[WARN] Sample lỗi/không hợp lệ cho '{event_type}' (lần {i + 1}) → bỏ")
                continue

            sample["id"] = f"auto_aug_{event_type}_{start_index + i:04d}"
            fout.write(json.dumps(sample, ensure_ascii=False) + '\n')
            fout.flush()  # ghi ngay xuống đĩa, tránh mất sample đã sinh nếu process bị ngắt giữa chừng
            valid_count += 1
    print(f'  "{event_type}": sinh {valid_count}/{quantity} sample hợp lệ '
          f'(lỗi: {invalid_count}), tốn {total_token} token')


def build_auto_augmented_samples(
    base_records:                   list[dict],
    deficit_by_event_type:          dict[str, int],
    event_type_fields:              dict[str, list[str]],
    event_type_field_descriptions:  dict[str, dict[str, str]],
    output_path:                    Path,
    prompt_template:                str,
    client:                         OpenAI,
    model:                          str,
    temperature:                    float,
) -> list[dict]:
    """
    - Summary:
        1. Đếm sample đã sinh từ lần chạy trước trong output_path (_get_output_event_type_counts()).
        2. Trừ deficit cho phần đã sinh, chỉ còn phần cần sinh thêm (_get_remaining_quantity_by_event_type()).
        3. Gom record theo event_type để làm pool ví dụ (_get_records_by_event_type()).
        4. Sinh và ghi nối tiếp sample cho từng event_type còn thiếu (_build_auto_augmented_samples_for_event_type()).
        5. Đọc lại toàn bộ output_path (sample cũ + mới) để trả về.
    - Args:
        - base_records: List record dataset gốc, dùng làm nguồn ví dụ tham khảo.
        - deficit_by_event_type: Dict event_type -> số lượng cần đạt.
        - event_type_fields: Dict event_type -> list field (dataset_schema.yaml).
        - event_type_field_descriptions: Dict event_type -> dict field -> mô tả (dataset_schema.yaml).
        - output_path: Đường dẫn file output auto_augment, dùng để resume và ghi nối tiếp.
        - prompt_template: Chuỗi template instruction_prompt.txt.
        - client: OpenAI client đã khởi tạo.
        - model: Tên model.
        - temperature: Độ ngẫu nhiên của model.
    - Output:
        - list[dict]: Toàn bộ sample trong output_path (đã sinh từ trước + mới sinh thêm).
    """
    existing_counts         = _get_output_event_type_counts(output_path)
    remaining_by_event_type = _get_remaining_quantity_by_event_type(deficit_by_event_type, existing_counts)
    records_by_event_type   = _get_records_by_event_type(base_records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for event_type, quantity in remaining_by_event_type.items():
        fields = event_type_fields.get(event_type)
        if fields is None:
            print(f"[SKIP] event_type '{event_type}' không có trong dataset_schema.yaml")
            continue

        same_event_records = records_by_event_type.get(event_type, [])
        diff_event_records  = [
            record for other_type, records in records_by_event_type.items() if other_type != event_type
            for record in records
        ]
        other_event_types = _build_other_event_types_text(event_type, list(event_type_fields.keys()))

        _build_auto_augmented_samples_for_event_type(
            event_type         = event_type,
            fields             = fields,
            field_descriptions = event_type_field_descriptions.get(event_type, {}),
            other_event_types  = other_event_types,
            quantity           = quantity,
            start_index        = existing_counts.get(event_type, 0),
            output_path        = output_path,
            prompt_template    = prompt_template,
            same_event_records = same_event_records,
            diff_event_records = diff_event_records,
            client             = client,
            model              = model,
            temperature        = temperature,
        )
    return _get_records(output_path) if output_path.exists() else []


if __name__ == "__main__":
    PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
    ENV_PATH    = PROJECT_DIR / "data_pipelines/.env"

    _env           = dotenv_values(str(ENV_PATH))
    OPENAI_API_KEY = _env.get("OPENAI_KEY") or _env.get("OPENAI_API_KEY")

    # TEST — kiểm tra hàm sinh/parse/validate của auto_augment_with_openai trên vài sample nhỏ
    test_config = {
        "dataset": PROJECT_DIR / "ml/samples/dataset_vietstock_20260601_20260601_CHUAN.jsonl",
        "dataset_schema": PROJECT_DIR / "ml/common/dataset_schema.yaml",
        "quantity_by_event": {"Chi trả cổ tức": 1, "M&A": 1},  # số sample test cần sinh cho mỗi event_type
        "auto_augment_with_openai": {
            "model": "gpt-4o-mini",
            "temperature": 0.8,
            "instruction_prompt_path": Path(__file__).resolve().parent / "instruction_prompt.txt",
            "output_path": PROJECT_DIR / "ml/samples/only_auto_augmented_test.jsonl",
        },
    }

    test_records                       = _get_records(test_config["dataset"])
    test_event_type_fields             = _get_event_type_fields(test_config["dataset_schema"])
    test_event_type_field_descriptions = _get_event_type_field_descriptions(test_config["dataset_schema"])
    test_auto_augment                  = test_config["auto_augment_with_openai"]
    test_prompt_template               = test_auto_augment["instruction_prompt_path"].read_text(encoding='utf-8')
    test_client                        = OpenAI(api_key=OPENAI_API_KEY)

    test_auto_augmented_samples = build_auto_augmented_samples(
        base_records                  = test_records,
        deficit_by_event_type         = test_config["quantity_by_event"],
        event_type_fields             = test_event_type_fields,
        event_type_field_descriptions = test_event_type_field_descriptions,
        output_path                   = test_auto_augment["output_path"],
        prompt_template               = test_prompt_template,
        client                        = test_client,
        model                         = test_auto_augment["model"],
        temperature                   = test_auto_augment["temperature"],
    )
    print(f'TEST: tổng {len(test_auto_augmented_samples)} sample trong {test_auto_augment["output_path"].name}')

    # PROD — cân bằng dataset thật bằng external dataset + auto_augment_with_openai
    augmentation_config = {
        "dataset": PROJECT_DIR / "data/processed/train_v1.jsonl",
        "dataset_schema": PROJECT_DIR / "ml/common/dataset_schema.yaml",
        "augmented_dataset_output_path": PROJECT_DIR / "data/processed/augmented_train.jsonl",
        "log_output_path": PROJECT_DIR / "data/processed/augmentation_log.jsonl",
        "unbalanced_events": ["Vay vốn", "Cổ đông thay đổi tỷ lệ sở hữu", "M&A", "Niêm yết", "Tổn thất tài sản nghiêm trọng", "Hợp đồng lớn", "Hủy niêm yết", "Phá sản", "Bồi thường lớn cho bên ngoài"],
        "quantity_needed": 800,
        "external_datasets": [
            PROJECT_DIR / "data/processed/external_v1.jsonl",
        ],
        "auto_augment_with_openai": {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "instruction_prompt_path": Path(__file__).resolve().parent / "instruction_prompt.txt",
            "output_path": PROJECT_DIR / "data/processed/only_auto_augmented.jsonl",
        }
    }

    base_dataset_path     = augmentation_config["dataset"]
    schema_path           = augmentation_config["dataset_schema"]
    augmented_output_path = augmentation_config["augmented_dataset_output_path"]
    log_output_path       = augmentation_config["log_output_path"]
    unbalanced_events     = augmentation_config.get("unbalanced_events", [])
    quantity_needed       = augmentation_config.get("quantity_needed", 0)

    base_records          = _get_records(base_dataset_path)
    event_type_counts     = _get_event_type_counts(base_records)
    deficit_by_event_type = _get_deficit_by_event_type(unbalanced_events, event_type_counts, quantity_needed)

    augmented_records: list[dict] = []
    summary_lines = [
        f'dataset gốc: {len(base_records)} record',
        f'event_type cần cân bằng lên {quantity_needed}: {unbalanced_events}',
    ]

    if augmentation_config.get("external_datasets"):
        # Add thêm các sample có sự kiện nằm trong list "unbalanced_events" vào output dataset
        external_paths    = augmentation_config["external_datasets"]
        external_records  = build_augmented_from_external(external_paths, deficit_by_event_type)
        augmented_records += external_records
        summary_lines.append(f'  external: thêm {len(external_records)} record')

    if augmentation_config.get("auto_augment_with_openai"):
        # Gọi OpenAI API tạo thêm sample có sự kiện nằm trong list "unbalanced_events" đến khi đủ "quantity_needed" và lưu vào output dataset
        auto_augment_config          = augmentation_config["auto_augment_with_openai"]
        event_type_fields            = _get_event_type_fields(schema_path)
        event_type_field_descriptions = _get_event_type_field_descriptions(schema_path)
        prompt_template              = auto_augment_config["instruction_prompt_path"].read_text(encoding='utf-8')
        client                       = OpenAI(api_key=OPENAI_API_KEY)

        auto_augmented_samples = build_auto_augmented_samples(
            base_records                  = base_records,
            deficit_by_event_type         = deficit_by_event_type,
            event_type_fields             = event_type_fields,
            event_type_field_descriptions = event_type_field_descriptions,
            output_path                   = auto_augment_config["output_path"],
            prompt_template               = prompt_template,
            client                        = client,
            model                         = auto_augment_config["model"],
            temperature                   = auto_augment_config["temperature"],
        )
        augmented_records += auto_augmented_samples
        summary_lines.append(
            f'  auto_augment_with_openai: tổng {len(auto_augmented_samples)} sample '
            f'trong {auto_augment_config["output_path"].name}'
        )

    # base_records giữ nguyên dataset gốc — không cộng dồn external/auto_augmented vào đây,
    # tránh ghi trùng record khi write (augmented_records đã gồm cả 2 nguồn ở trên)
    _write_jsonl(base_records + augmented_records, augmented_output_path)
    summary_lines.append(
        f'tổng dataset sau augment: {len(base_records) + len(augmented_records)} record → {augmented_output_path.name}'
    )
    _write_log(log_output_path, summary_lines)
    print('\n'.join(summary_lines))
