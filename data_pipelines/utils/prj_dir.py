import inspect
from pathlib import Path
from dotenv import dotenv_values


def prj_dir_str(env_path: str | None = None) -> str:
    """
    Mục đích: Trả về đường dẫn thư mục gốc project dưới dạng POSIX string, đọc từ biến PRJ_DIR trong file .env.

    Input:
        env_path (str | None): abs/rel path đến file .env (rel tính từ file gọi hàm). None = tự tìm .env từ folder caller đi lên từng cấp cha.

    Output:
        str: POSIX path của thư mục gốc project. Nếu PRJ_DIR là rel path thì resolve từ thư mục chứa .env.
    """
    if env_path is not None:
        p = Path(env_path)
        if not p.is_absolute():
            caller_dir = Path(inspect.stack()[1].filename).parent
            p = (caller_dir / p).resolve()
        else:
            p = p.resolve()
    else:
        caller_dir = Path(inspect.stack()[1].filename).parent.resolve()
        for folder in [caller_dir, *caller_dir.parents]:
            candidate = folder / ".env"
            if candidate.exists():
                p = candidate
                break
        else:
            raise FileNotFoundError(
                f".env not found in {caller_dir} or any of its parent directories."
            )

    if not p.exists():
        raise FileNotFoundError(f".env not found at: {p}")

    values = dotenv_values(p)
    prj_dir = values.get("PROJECT_DIR")
    if prj_dir is None:
        raise KeyError(f"PRJ_DIR not defined in {p}")

    prj_dir_path = Path(prj_dir)
    if not prj_dir_path.is_absolute():
        prj_dir_path = (p.parent / prj_dir_path).resolve()

    print(f"Project Directory: prj_dir = {prj_dir_path.as_posix()}. Hãy dùng biến này để tạo các đường dẫn trong dự án.")
    
    return prj_dir_path.as_posix()


if __name__ == "__main__":
    # Không truyền gì -> tự tìm .env
    print(prj_dir_str())

    # Truyền rel path
    # print(prj_dir_str("../.env"))

    # Truyền abs path
    # print(prj_dir_str(r"D:\UIT\SE365_Prj\data_pipelines\.env"))
