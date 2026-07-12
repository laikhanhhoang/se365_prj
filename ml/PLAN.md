# ML — Kế hoạch tổ chức

## Cấu trúc thư mục

```
SE365_Prj/                       # repo root
  pyproject.toml                 # package "ml", packages=["ml", "ml.common", "ml.utils", "ml.approaches", ...]
                                  #   optional-dependencies: [train] và [infer] tách riêng
  ml/
    PLAN.md                      # file này
    utils/                       # thuần kỹ thuật, KHÔNG biết domain (không import từ data_pipelines/utils)
      device.py                  # resolve_device()
    common/                      # domain logic dùng chung mọi approach (không phải "tiện ích")
      dataset_schema.yaml        # schema event_type -> fields (tự chứa, không import từ data_pipelines)
      schema.py                  # đọc dataset_schema.json -> field mapping theo event_type
      data_loader.py              # step04 jsonl -> training format
      prompts.py                  # prompt template chung (nếu cần)
    approaches/                  # mỗi cách tiếp cận 1 folder riêng, không gộp chung train.py
      lora_qwen2_5/
        train.py                  # chạy trên Kaggle
        infer.py                  # gọi bởi apps/ khi đóng gói docker
        config.yaml
      <approach_khac>/...
    weights/                      # gitignore — chỉ là cache local, nguồn thật ở HF Hub
  apps/                           # đóng gói Docker + serving, chi tiết nằm ở kế hoạch riêng của apps/
```

## Quy ước đã chốt

- **`pyproject.toml` ở repo root**, không nằm trong `ml/` — để `git clone` → `cd repo` → `pip install -e . -q` chạy ngay không cần `cd` thêm.
  Khai báo tường minh `packages = [...]` trong `[tool.setuptools]`, không để setuptools auto-discover — vì repo có nhiều thư mục top-level (`ml/`, `apps/`, `data_pipelines/`) dễ gây lỗi "Multiple top-level packages discovered".

- **`common/` vs `utils/`**: `utils/` chỉ chứa hàm generic không biết gì về bài toán trích xuất sự kiện (device resolution, path helper — dùng được cho project khác). `common/` chứa logic biết về domain (schema 15 loại sự kiện, convert data, prompt) mà nhiều approach cùng dùng. Không gộp chung để giữ ranh giới "an toàn sửa vs business logic".

- **`approaches/`**: mỗi cách tiếp cận (LoRA, hoặc cách khác sau này) là 1 folder riêng, tự chứa `train.py` + `infer.py` + `config.yaml`, nhưng gọi lại `ml/common/` và `ml/utils/` cho phần dùng chung — không copy-paste toàn bộ pipeline.

- **Kaggle workflow**:
  ```
  !git clone https://{GITHUB_TOKEN}@github.com/<user>/<repo>.git
  %cd repo
  !pip install -e . -q
  ```
  Sau đó `from ml.approaches.lora_qwen2_5.train import train_lora` chạy được không phụ thuộc cwd.

- **Lưu weight**: không commit vào git, không coi `ml/weights/` là nguồn thật. Cuối script train, push adapter lên **Hugging Face Hub** (private repo), đặt tên `{approach}_{base_model}_{version}`. `ml/weights/` chỉ là cache tải về (gitignore).

- **Đóng gói Docker**: `apps/` chịu trách nhiệm toàn bộ — tách model thành 1 container riêng, phần software gọi qua API tới container này. `apps/` chỉ copy `ml/common/` + `ml/approaches/<approach_thắng>/infer.py` (+config), không copy `train.py`, không copy weight vào image (pull từ HF Hub lúc container start). Container dùng chung `DEVICE=auto|cuda|cpu` từ `ml/utils/device.py` để chạy được cả máy có GPU lẫn CPU-only bằng 1 image. Chi tiết cấu trúc/Dockerfile nằm trong kế hoạch riêng của `apps/`.

- **vLLM**: chỉ dùng cho infer/serving (do `apps/` quyết định có dùng hay không), không liên quan đến training (trừ RLHF-style rollout, không phải case này).

## Việc cần làm tiếp

- [ ] Viết `pyproject.toml` ở repo root.
- [ ] Scaffold `ml/utils/device.py`, `ml/common/dataset_schema.json`, `ml/common/schema.py`, `ml/common/data_loader.py`.
- [ ] Chọn base model cụ thể cho approach đầu tiên (đang nghiêng Qwen2.5-7B-Instruct, ~10k sample).
- [ ] Viết `ml/approaches/lora_qwen2_5/train.py` chạy trên Kaggle.
- [ ] Sang phần `apps/` để lên kế hoạch đóng gói Docker + serving.
