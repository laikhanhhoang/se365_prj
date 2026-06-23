import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


current_file = Path(__file__).resolve()
PROJECT_DIR = current_file.parent.parent

def access_webpage(url, debug=False, headless=True):
    options = webdriver.ChromeOptions()

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")  
    options.add_argument("--window-size=1920,1080")
    
    # Nếu KHÔNG debug, chạy ngầm (không có màn hình hiển thị)
    if headless:
        options.add_argument("--headless=new") 
    
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(2)  # Đợi 2 giây để trang web tải xong
    return driver

def crawl_from_driver(driver, debug=False):
    """
    return title, head, body
    """
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

def crawl_from_link(
    link,
    debug=False,
    headless=True   
):
    """
    Crawl data from Vietstock website using the provided link.
    Output: title, head, body
    """
    print("[LOG] Đang crawl link:", link)

    driver = access_webpage(link, debug=debug, headless=headless)

    title, head, body = crawl_from_driver(driver, debug=debug)
    if debug:
        print(f"Title: {title}")
        print(f"Head: {head}")
        print(f"Body: {body}")

    if title and head and body:
        print(f"[LOG] Crawl data thành công từ link {link}")

    return title, head, body

def main(
    debug=False,
    headless=True,
    links_file="data_pipelines/vietstock_links_test.txt",
):
    begin_time = time.time()

    input_file_path = PROJECT_DIR / links_file
    if not input_file_path.exists():
        print(f"[ERROR] File {input_file_path} không tồn tại. Vui lòng kiểm tra lại.")
        return
    else:
        print(f"[LOG] Đang đọc file link từ: {input_file_path.as_posix()}")
    
    # Thay chữ links trong input_file_path bằng crawled_data để tạo tên file output định dạng .jsonl
    output_file_path = input_file_path.parent / (input_file_path.stem.replace("links", "crawled_data") + ".jsonl")
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[LOG] File kết quả sẽ được lưu tại: {output_file_path.as_posix()}")

    with open(input_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        print(f"[LOG] Tổng số link cần crawl: {len(lines)}")

    with open(output_file_path, "w", encoding="utf-8") as out_f:
        for i, line in enumerate(lines):
            if i % 10 == 0:
                print(f"[LOG] Hiện tại đến link thứ {i + 1}/{len(lines)}")

            element = line.strip().split(",")
            id = element[0]
            link = element[-1]
            title, head, body = crawl_from_link(link, debug=debug, headless=headless)
            record = {"id": id, "link": link, "title": title, "head": head, "body": body}
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    end_time = time.time()
    elapsed_time = end_time - begin_time

    print(f"[LOG] Đã lưu kết quả vào: {output_file_path.as_posix()}")
    print(f"[LOG] Thời gian thực hiện: {elapsed_time:.2f} giây")
    return

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vietstock Crawler")
    parser.add_argument("--debug", action="store_true", help="Bật chế độ debug in ra log")
    parser.add_argument("--head", action="store_true", help="Hiển thị trình duyệt")
    parser.add_argument("--links_file", type=str, default="data_pipelines/vietstock_links_20260601_20260601_CHUAN.txt", help="Đường dẫn file chứa các link cần crawl tương đối từ PROJECT_DIR")

    args = parser.parse_args()

    main(
        debug       = args.debug,
        headless    = not args.head,
        links_file  = args.links_file
    )