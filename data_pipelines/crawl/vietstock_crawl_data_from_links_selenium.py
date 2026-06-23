import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, InvalidSessionIdException


current_file = Path(__file__).resolve()
PROJECT_DIR = current_file.parent.parent.parent


def init_driver(
    url: str, 
    headless: bool = True) -> webdriver.Chrome:
    """
    Khởi tạo Chrome WebDriver và điều hướng đến URL.

    Output:
    - webdriver.Chrome: driver — đối tượng trình duyệt đã điều hướng

    Input:
    - str: url — địa chỉ trang web cần mở
    - bool: headless — chạy ẩn không hiển thị cửa sổ
    """
    # beginf
    options = webdriver.ChromeOptions()

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # Nếu KHÔNG debug, chạy ngầm (không có màn hình hiển thị)
    if headless:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.get(url)
    time.sleep(2)  # Đợi 2 giây để trang web tải xong

    return driver
    # endf


def parse_article(
    driver: webdriver.Chrome, 
    debug: bool = False) -> tuple[str | None, str | None, str | None]:
    """
    Trích xuất nội dung bài viết từ driver.

    
    Output:
    - str | None: title, head, body — tiêu đề, mở đầu, nội dung

    Input:
    - webdriver.Chrome: driver — trình duyệt đang mở trang bài viết
    - bool: debug — in log khi True
    """
    # beginf

    # Tìm div có id="vst_detail"
    try:
        post_element = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((
                By.XPATH,
                "//div[contains(@id, 'vst_detail')]"
            ))
        )
        if debug:
            print(f"[LOG] Tìm thấy {len(post_element)} div có id chứa 'vst_detail'")
    except Exception as e:
        if debug:
            print(f"[LOG] Không tìm thấy div#vst_detail. Lỗi: {e}")
        return None, None, None

    # Lấy tất cả các thẻ <p> có trong post_element
    try:
        all_p = post_element[0].find_elements(By.TAG_NAME, "p")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy thẻ <p>: {e}")
        return None, None, None

    # Lấy title từ p có class="pTitle" trong all_p, nếu không có thì gán None
    try:
        title_els = [p for p in all_p if "pTitle" in p.get_attribute("class")]
        title = title_els[0].get_attribute("textContent").strip() if title_els else None
        if debug:
            print(f"[LOG] Title: {title}")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy title: {e}")
        title = None

    # Lấy head từ p trong all_p có class "pHead", nếu không có thì gán None
    try:
        head_els = [p for p in all_p if "pHead" in p.get_attribute("class")]
        head = head_els[0].text if head_els else None
        if debug:
            print(f"[LOG] Head: {head}")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy head: {e}")
        head = None

    # Lấy body từ các p theo thứ tự trong all_p có class "pBody", các đoạn cách nhau bằng \n; nếu không có thì gán None
    try:
        body_els = [p for p in all_p if "pBody" in p.get_attribute("class")]
        body = "\n".join(p.text for p in body_els) if body_els else None
        if debug:
            print(f"[LOG] Body: {body}")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy body: {e}")
        body = None

    return title, head, body
    # endf


def crawl_link(
    driver: webdriver.Chrome,
    link: str,
    debug: bool = False) -> tuple[str | None, str | None, str | None]:
    """
    Crawl một link Vietstock và trả về nội dung bài viết.

    Output:
    - str | None: title, head, body — tiêu đề, mở đầu, nội dung

    Input:
    - webdriver.Chrome: driver — driver đã được khởi tạo sẵn
    - str: link — URL bài viết Vietstock
    - bool: debug — in log khi True
    """
    # beginf

    print("[LOG] Đang crawl link:", link)

    try:
        driver.get(link)
    except TimeoutException:
        print(f"[WARN] Page load timed out, thử tiếp tục với nội dung đã tải: {link}")
        driver.execute_script("window.stop();")
    time.sleep(2)
    title, head, body = parse_article(driver, debug=debug)

    if debug:
        print(f"Title: {title}")
        print(f"Head: {head}")
        print(f"Body: {body}")

    if title and head and body:
        print(f"[LOG] Crawl data thành công từ link {link}")

    return title, head, body
    # endf


def crawl_links(
    links: list[str],
    debug: bool = False, headless: bool = True) -> list[dict]:
    """
    Crawl danh sách links và trả về kết quả.

    Output:
    - list[dict]: results — mỗi dict gồm link, title, head, body

    Input:
    - list[str]: links — danh sách URL bài viết Vietstock
    - bool: debug — in log khi True
    - bool: headless — chạy ẩn không hiển thị cửa sổ
    """
    # beginf

    results = []
    total = len(links)
    driver = init_driver(links[0], headless=headless)
    try:
        for i, link in enumerate(links):
            if i % 5 == 0:
                print(f"[LOG] Hiện tại đến link thứ {i + 1}/{total}")
            if i > 0 and i % 100 == 0:
                print(f"[LOG] Đã cào {i} links, nghỉ 2 phút...")
                time.sleep(120)
            try:
                title, head, body = crawl_link(driver, link, debug=debug)
            except InvalidSessionIdException:
                print(f"[WARN] Browser bị crash, đang khởi động lại driver...")
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = init_driver(link, headless=headless)
                title, head, body = crawl_link(driver, link, debug=debug)
            results.append({"link": link, "title": title, "head": head, "body": body})
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return results
    # endf


def main(
    debug: bool = False,
    headless: bool = True,
    links_file: str = "data_pipelines/crawl/vietstock_links_test.txt",
) -> None:
    """
    Đọc file links, crawl và lưu kết quả vào .jsonl.

    Output:
    - None — ghi kết quả vào file .jsonl cùng thư mục

    Input:
    - str: links_file — đường dẫn tương đối từ PROJECT_DIR
    - bool: debug — in log khi True
    - bool: headless — chạy ẩn không hiển thị cửa sổ
    """
    # beginf
    begin_time = time.time()

    # Truy cập file links_file từ PROJECT_DIR
    input_file_path = PROJECT_DIR / links_file
    if not input_file_path.exists():
        print(f"[ERROR] File {input_file_path} không tồn tại. Vui lòng kiểm tra lại.")
        return
    else:
        print(f"[LOG] Đang đọc file link từ: {input_file_path.as_posix()}")

    # Tạo file output định dạng .jsonl bằng cách thay thế "links" bằng "crawled_data" trong tên file input
    output_file_path = input_file_path.parent / (input_file_path.stem.replace("links", "crawled_data") + ".jsonl")
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[LOG] File kết quả sẽ được lưu tại: {output_file_path.as_posix()}")

    with open(input_file_path, "r", encoding="utf-8") as f:
        elements = [line.strip().split(",") for line in f.readlines()]
    print(f"[LOG] Tổng số link cần crawl: {len(elements)}")

    record_ids = [el[0] for el in elements]
    links = [el[-1] for el in elements]

    # Gọi hàm crawl_links để lấy kết quả
    results = crawl_links(links, debug=debug, headless=headless)

    with open(output_file_path, "w", encoding="utf-8") as out_f:
        for record_id, result in zip(record_ids, results):
            record = {"id": record_id, **result}
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    end_time = time.time()
    elapsed_time = end_time - begin_time

    print(f"[LOG] Đã lưu kết quả vào: {output_file_path.as_posix()}")
    print(f"[LOG] Thời gian thực hiện: {elapsed_time:.2f} giây")
    return
    # endf


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vietstock Crawler")
    parser.add_argument("--debug", action="store_true", help="Bật chế độ debug in ra log")
    parser.add_argument("--head", action="store_true", help="Hiển thị trình duyệt")
    parser.add_argument("--links_file", type=str, default="data_pipelines/crawl/vietstock_links_20260601_20260601_CHUAN.txt", help="Đường dẫn file chứa các link cần crawl tương đối từ PROJECT_DIR")

    args = parser.parse_args()

    main(
        debug       = args.debug,
        headless    = not args.head,
        links_file  = args.links_file
    )
