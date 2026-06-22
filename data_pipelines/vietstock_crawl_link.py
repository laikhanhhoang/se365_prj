import time
from pathlib import Path
from datetime import datetime, timedelta
from tracemalloc import start
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

crawl_url = "https://vietstock.vn/doanh-nghiep.htm"

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
    return driver

def search_by_date(driver, target_date_str, debug=False):
    """
    input: target_date_str dạng 'YYYY-MM-DD' (Ví dụ: '2026-06-01')
    output: None (Web hiển thị các bài báo được đăng vào ngày target_date_str)
    """
    if debug:
        print("Đang chạy hàm search_by_date...")

    start_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    end_date = start_date + timedelta(days=1)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    daterange_string = f"{start_str} - {end_str}"
    if debug:
        print(f"Chuỗi sẽ nhập vào ô search: {daterange_string}")

    # Tìm ô input <input type="text" name="daterange" aria-label="search" class="form-control" placeholder="Xem theo ngày">
    input_date = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((                     
            By.XPATH, 
            "//input[@name='daterange' and contains(@aria-label, 'search')]"
        ))
    )

    # Click và xóa nội dung cũ trong ô input
    driver.execute_script("arguments[0].click();", input_date)  
    input_date.send_keys(Keys.CONTROL + "a")
    input_date.send_keys(Keys.BACKSPACE)

    # Nhập string đại diện cho ngày cần search và nhấn Enter
    input_date.send_keys(daterange_string)                      
    input_date.send_keys(Keys.ENTER)

    # Click ra ngoài để đóng calendar và chờ trang load xong
    time.sleep(1)
    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    time.sleep(5)

    if debug:
        print("Kết thúc hàm search_by_date.")

def crawl_link_by_date(driver, target_date_str, debug=False):
    if debug:
        print("Đang chạy hàm crawl_link_by_date...")

    search_by_date(driver, target_date_str, debug=debug)

    page = 1
    all_post_links = []
    while True:
        # Cào link các bài báo trên page hiện tại
        post_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((
                By.XPATH, 
                "//div[@id='channel-container']//div[contains(@class, 'single_post_text')]//h4/a"
            ))
        )

        post_links = [post.get_attribute("href") for post in post_elements]
        if debug:
            print(f"Đã cào được {len(post_links)} link bài báo trên trang hiện tại (trang {page}):")
            for link in post_links:
                print(link)

        page += 1
        all_post_links.extend(post_links)

        # Kiểm tra xem có nút "Next" để sang trang tiếp theo không
        try:
            first_link_before_click = post_links[0] if post_links else None
            next_li = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "//li[contains(@class, 'next') and not(contains(@class, 'disabled'))]"
                ))
            )
            
            # Tìm thẻ <a> trực tiếp bên trong next_li để click
            next_button = next_li.find_element(By.XPATH, "./a")
            if debug:
                print("Tìm thấy nút 'Next'. Đang di chuyển chuột tới và click...")
            
            # Cuộn màn hình xuống đúng vị trí nút Next để tránh bị các thanh menu che khuất
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.5) # Nghỉ nửa giây cho màn hình cuộn xong
            
            # Mô phỏng hành động người dùng - Click bằng chuột thật
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.move_to_element(next_button).click().perform()
            
            # Chờ dữ liệu thay đổi thực tế
            WebDriverWait(driver, 8).until(
                lambda d: d.find_element(
                    By.XPATH, "//div[@id='channel-container']//div[contains(@class, 'single_post_text')]//h4/a"
                ).get_attribute("href") != first_link_before_click
            )
            
        except Exception as e:
            if debug:
                print("Không còn trang tiếp theo hoặc không thể click chuyển trang. Kết thúc cào link.")
            break
    
    if debug:
        print("Kết thúc hàm crawl_link_by_date.")
    return all_post_links


current_file = Path(__file__).resolve()
PROJECT_DIR = current_file.parent.parent

def main(debug=False, headless=False, start_date="01-06-2026", end_date="01-06-2026", output_file_dir="data_pipelines/vietstock_links.txt"):
    # Tạo tên file kết quả có chứa khoảng ngày cào được
    base_output = PROJECT_DIR / output_file_dir


    # Đọc ngày vào theo kiểu DD-MM-YYYY từ terminal
    start           = datetime.strptime(start_date, "%d-%m-%Y")
    end             = datetime.strptime(end_date, "%d-%m-%Y")
    current_date    = start

    start_clean     = start.strftime("%Y%m%d")
    end_clean       = end.strftime("%Y%m%d")
    new_filename    = f"{base_output.stem}_{start_clean}_{end_clean}{base_output.suffix}"
    output_dir      = base_output.with_name(new_filename)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    if debug:
        print(f"[DEBUG] File kết quả thực tế sẽ được lưu tại: {output_dir.as_posix()}")

    # Mở trình duyệt và truy cập vào trang web
    driver = access_webpage(crawl_url, debug=debug, headless=headless)

    # Mở file ghi dữ liệu
    with open(output_dir, "w", encoding="utf-8") as f:
        while current_date <= end:
            # 1. Chuyển đổi định dạng sang YYYY-MM-DD trước khi truyền vào hàm cào
            date_ymd_str = current_date.strftime("%Y-%m-%d")
            
            if debug:
                print(f"\n[DEBUG] Đang tiến hành cào dữ liệu cho ngày: {current_date.strftime('%d-%m-%Y')} (Định dạng truyền vào hàm: {date_ymd_str})...")
            
            # 2. Truyền ngày đã được format chuẩn YYYY-MM-DD vào đây
            date_post_links = crawl_link_by_date(driver, date_ymd_str, debug=debug)    

            if debug:
                print(f"Các link bài báo được đăng vào ngày {current_date.strftime('%d-%m-%Y')}:")
                for link in date_post_links:
                    print(link)     
                print(f"Tổng số link bài báo cào được cho ngày {current_date.strftime('%d-%m-%Y')}: {len(date_post_links)}")

            # Ghi toàn bộ link cào được trong ngày vào file
            for link in date_post_links:
                f.write(f"{link}\n")

            # Tăng thêm 1 ngày
            current_date += timedelta(days=1)

    if debug:
        print(f"\n[DEBUG] Đã lưu kết quả tại: {output_dir.as_posix()}")
        time.sleep(10)  
                          
    driver.quit()

if __name__ == "__main__":
    import argparse
    from datetime import datetime, timedelta
    
    parser = argparse.ArgumentParser(description="Vietstock Crawler")
    parser.add_argument("--debug", action="store_true", help="Bật chế độ debug in ra log")
    parser.add_argument("--head", action="store_true", help="Hiển thị trình duyệt")
    
    # Nhận tham số từ terminal theo kiểu người dùng Việt Nam (DD-MM-YYYY)
    parser.add_argument("--start", type=str, default="01-06-2026", help="Ngày bắt đầu (DD-MM-YYYY)")
    parser.add_argument("--end", type=str, default="01-06-2026", help="Ngày kết thúc (DD-MM-YYYY)")
    parser.add_argument("--output", type=str, default="data_pipelines/vietstock_links.txt", help="Đường dẫn file kết quả tương đối từ PROJECT_DIR")
    
    args = parser.parse_args()

    if args.debug:
        print(f"PROJECT_DIR: {PROJECT_DIR.as_posix()}")

    main(
        start_date=args.start, 
        end_date=args.end, 
        debug=args.debug, 
        headless=not args.head,
        output_file_dir=args.output
    )