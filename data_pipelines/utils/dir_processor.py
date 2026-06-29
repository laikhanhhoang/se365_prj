import inspect
from pathlib import Path
from typing import Literal
from dotenv import dotenv_values

import logging
logger = logging.getLogger(__name__)

def find_file_upwards(
    filename: str,
    start_dir: str | Path | None = None,
    return_type: Literal["path", "str"] = "path",
    force_posix: bool = False,
) -> Path | str | None:
    """
    - Summary: Tìm file `filename` từ `start_dir` đi lên các thư mục cha.
        - Nếu `start_dir` là relative path (hoặc None), resolve từ thư mục của file gọi hàm. 
        - Trả về None nếu không tìm thấy.

    - Args:
        - filename:       Tên file cần tìm.
        - start_dir:      Thư mục bắt đầu tìm (mặc định: thư mục của caller).
        - return_type:    "path" trả về Path, "str" trả về string.
        - force_posix:    Chỉ có tác dụng khi return_type="str" — dùng dấu / thay cho dấu phân cách của hệ điều hành.

    - Output:
        - dir: Path hoặc String của đường dẫn tuyệt đối file tìm thấy, hoặc None nếu không tìm thấy.
    """
    caller_dir = Path(inspect.stack()[1].filename).parent.resolve()

    if start_dir is None:
        start_dir = caller_dir
    else:
        start_dir = Path(start_dir)
        if not start_dir.is_absolute():
            start_dir = (caller_dir / start_dir).resolve()
        else:
            start_dir = start_dir.resolve()

    for folder in [start_dir, *start_dir.parents]:
        candidate = folder / filename
        if candidate.exists():
            if return_type == "str":
                return candidate.as_posix() if force_posix else str(candidate)
            return candidate

    return None


def get_project_abs_dir_str_from_env(env_path_str: str | None = None) -> str:
    """
    - Summary: Trả về đường dẫn tuyệt đối của thư mục dự án từ biến môi trường PROJECT_DIR trong file .env.
        1. Tìm file .env từ `env_path_str`. (find_file_upwards())
        Nếu không thấy thì tìm từ thư mục của caller đi lên các thư mục cha. Nếu vẫn không thấy thì raise FileNotFoundError.
        2. Tìm biến môi trường PROJECT_DIR trong file .env được tìm thấy. Nếu không có thì raise KeyError.
    - Args:
        - env_path_str:    Đường dẫn tới file .env (ví dụ: "a/b/.env" | "/a/b/.env" | None)
    - Output:
        - str: Đường dẫn tuyệt đối của thư mục dự án.
    """
    # 1.
    tmp                         = Path(env_path_str)
    envfile_name                = tmp.name if env_path_str is not None else ".env"
    start_dir_to_find_env       = tmp.parent if tmp.is_absolute() \
                                    else (Path(inspect.stack()[1].filename).parent / tmp.parent).resolve()
    abs_envfile_path_founded    = find_file_upwards(
        filename    = envfile_name,
        start_dir   = start_dir_to_find_env,
        return_type = "path"
    )

    if not abs_envfile_path_founded:
        raise FileNotFoundError(f"Không tìm thấy {envfile_name} tại {start_dir_to_find_env.absolute().as_posix() if start_dir_to_find_env else 'current directory and its parents'}")
    else:
        logger.debug(f"Tìm thấy {envfile_name}: {abs_envfile_path_founded.as_posix()}")

    # 2.
    values      = dotenv_values(abs_envfile_path_founded.as_posix())
    project_dir = values.get("PROJECT_DIR") or None # "" cũng coi là không hợp lệ, ít nhất phải có 1 ký tự. Nếu muốn dùng thư mục gốc thì đặt PROJECT_DIR=.
    if not project_dir:
        raise KeyError(f"Không có giá trị PROJECT_DIR trong {abs_envfile_path_founded.as_posix()}")
    else:
        logger.debug(f"Tìm thấy PROJECT_DIR trong {envfile_name}: {project_dir}")

    return (abs_envfile_path_founded.parent / project_dir).resolve().as_posix()



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    try:
        print(get_project_abs_dir_str_from_env("D:\\UIT\\SE365_Prj\\data_pipelines\\.env"))
    except (FileNotFoundError, KeyError) as e:
        print(e)
