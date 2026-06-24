import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Page

current_file = Path(__file__).resolve()
PROJECT_DIR = current_file.parent.parent.parent


async def init_page(url: str, headless: bool = True):
    """
    Khởi tạo Browser, Context và Page.

    Output:
    - tuple: (playwright_instance, browser, page)

    Input:
    - str: url — địa chỉ trang web cần mở
    - bool: headless — chạy ẩn không hiển thị cửa sổ
    """
    # beginf
    p = await async_playwright().start()

    browser = await p.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )

    page = await context.new_page()

    print(f"Đang điều hướng đến: {url} ...")
    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"Lỗi khi truy cập trang: {e}")
        await page.screenshot(path="debug_error.png")
        raise e

    return p, browser, page
    # endf


async def search_by_date(page: Page, target_date_str: str, debug: bool = False) -> None:
    """
    Nhập ngày vào ô tìm kiếm và tải kết quả.

    Output:
    - None — trang hiển thị bài báo theo ngày target_date_str

    Input:
    - Page: page — trang Playwright đang mở Vietstock
    - str: target_date_str — ngày cần tìm, dạng YYYY-MM-DD
    - bool: debug — in log khi True
    """
    # beginf
    if debug:
        print("Đang chạy hàm search_by_date...")

    start_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    end_date = start_date + timedelta(days=1)

    daterange_string = f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
    if debug:
        print(f"Chuỗi sẽ nhập vào ô search: {daterange_string}")

    # Xóa cookie consent overlay khỏi DOM trước khi thao tác
    await page.evaluate("""
        document.querySelectorAll('.fc-consent-root, .fc-dialog-overlay').forEach(el => el.remove())
    """)

    try:
        input_date = page.locator("input[name='daterange'][aria-label*='search']")
        await input_date.wait_for(timeout=10000)
        print("[LOG] Tìm thấy ô input tìm kiếm theo ngày.")
    except Exception as e:
        print(f"[LOG] Không tìm thấy ô input tìm kiếm. Lỗi: {e}")
        return

    # Dùng JS click để tránh bị overlay chặn
    await page.evaluate("document.querySelector(\"input[name='daterange'][aria-label*='search']\").click()")
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Backspace")
    await input_date.type(daterange_string)
    await input_date.press("Enter")

    await asyncio.sleep(1)
    await page.keyboard.press("Escape")
    await asyncio.sleep(5)

    if debug:
        print("Kết thúc hàm search_by_date.")
    # endf


async def crawl_link_by_date(page: Page, target_date_str: str, debug: bool = False) -> list[str]:
    """
    Cào tất cả link bài báo Vietstock trong một ngày.

    Output:
    - list[str]: all_post_links — danh sách URL bài báo trong ngày

    Input:
    - Page: page — trang Playwright đang mở Vietstock
    - str: target_date_str — ngày cần cào, dạng YYYY-MM-DD
    - bool: debug — in log khi True
    """
    # beginf
    if debug:
        print("Đang chạy hàm crawl_link_by_date...")

    await search_by_date(page, target_date_str, debug=debug)

    page_num = 1
    all_post_links = []
    POST_SELECTOR = "#channel-container .single_post_text h4 a"

    while True:
        # Cào link các bài báo trên page hiện tại
        try:
            await page.wait_for_selector(POST_SELECTOR, timeout=10000)
            post_elements = await page.locator(POST_SELECTOR).all()
        except Exception as e:
            if debug:
                print(f"[LOG] Không tìm thấy bài báo trên trang {page_num}. Lỗi: {e}")
            break

        raw_links = [await el.get_attribute("href") for el in post_elements]
        post_links = [
            ("https://vietstock.vn" + h) if h and h.startswith("/") else h
            for h in raw_links
        ]
        if debug:
            print(f"Các link bài báo trên trang {page_num}:")
            for link in post_links:
                print(link)
            print(f"Đã cào được {len(post_links)} link bài báo trên trang hiện tại (trang {page_num}).")

        page_num += 1
        all_post_links.extend(post_links)

        # Kiểm tra xem có nút "Next" để sang trang tiếp theo không
        try:
            # Dùng raw href (relative) để so sánh với DOM attribute, không dùng full URL
            first_raw_before_click = raw_links[0] if raw_links else None
            next_button = page.locator("li.next:not(.disabled) > a")
            await next_button.wait_for(timeout=5000)

            if debug:
                print("Tìm thấy nút 'Next'. Đang di chuyển chuột tới và click...")

            await next_button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await next_button.click()

            # Chờ dữ liệu thay đổi thực tế
            # arg là 1 giá trị duy nhất truyền vào JS → dùng destructuring array
            await page.wait_for_function(
                """([selector, prevHref]) => {
                    const el = document.querySelector(selector);
                    return el && el.getAttribute('href') !== prevHref;
                }""",
                arg=[POST_SELECTOR, first_raw_before_click],
                timeout=8000
            )

        except Exception as e:
            if debug:
                print("Không còn trang tiếp theo hoặc không thể click chuyển trang. Kết thúc cào link.")
            break

    if debug:
        print("Kết thúc hàm crawl_link_by_date.")
    return all_post_links
    # endf


async def main(
    debug: bool = False,
    headless: bool = True,
    start_date: str = "01-06-2026",
    end_date: str = "01-06-2026",
    output_file_dir: str = "data_pipelines/crawl/vietstock_links.txt",
) -> None:
    """
    Cào links bài báo Vietstock theo khoảng ngày và lưu vào file.

    Output:
    - None — ghi kết quả vào file .txt theo output_file_dir

    Input:
    - str: start_date, end_date — khoảng ngày cào, dạng DD-MM-YYYY
    - str: output_file_dir — đường dẫn tương đối từ PROJECT_DIR
    - bool: debug — in log khi True
    - bool: headless — chạy ẩn không hiển thị cửa sổ
    """
    # beginf
    begin_time = time.time()
    base_output = PROJECT_DIR / output_file_dir

    start           = datetime.strptime(start_date, "%d-%m-%Y")
    end             = datetime.strptime(end_date, "%d-%m-%Y")
    current_date    = start

    start_clean     = start.strftime("%Y%m%d")
    end_clean       = end.strftime("%Y%m%d")
    new_filename    = f"{base_output.stem}_{start_clean}_{end_clean}{base_output.suffix}"
    output_path     = base_output.with_name(new_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Đang tiến hành cào link bài báo từ ngày {start_date} đến ngày {end_date}...")
    if debug:
        print(f"[DEBUG] File kết quả thực tế sẽ được lưu tại: {output_path.as_posix()}")

    p, browser, page = await init_page("https://vietstock.vn/doanh-nghiep.htm", headless=headless)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            while current_date <= end:
                date_ymd_str = current_date.strftime("%Y-%m-%d")
                print(f"\n[LOG] Đang tiến hành cào dữ liệu cho ngày: {current_date.strftime('%d-%m-%Y')}")

                date_post_links = await crawl_link_by_date(page, date_ymd_str, debug=debug)

                if debug:
                    print(f"Các link bài báo được đăng vào ngày {current_date.strftime('%d-%m-%Y')}:")
                    for link in date_post_links:
                        print(link)

                print(f"[LOG] Tổng số link bài báo cào được cho ngày {current_date.strftime('%d-%m-%Y')}: {len(date_post_links)}")

                for i, link in enumerate(date_post_links):
                    f.write(f"vietstock_{current_date.strftime('%Y%m%d')}_{i:02d},{link}\n")

                current_date += timedelta(days=1)
    finally:
        if debug:
            await asyncio.sleep(10)
        await browser.close()
        await p.stop()

    print(f"\n[LOG] Đã lưu kết quả tại: {output_path.as_posix()}")
    elapsed_time = time.time() - begin_time
    print("Thời gian thực hiện: {:.2f} giây".format(elapsed_time))
    # endf


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vietstock Crawler (Playwright)")
    parser.add_argument("--debug", action="store_true", help="Bật chế độ debug in ra log")
    parser.add_argument("--head", action="store_true", help="Hiển thị trình duyệt")
    parser.add_argument("--start", type=str, default="01-06-2026", help="Ngày bắt đầu (DD-MM-YYYY)")
    parser.add_argument("--end", type=str, default="", help="Ngày kết thúc (DD-MM-YYYY)")
    parser.add_argument("--output", type=str, default="data_pipelines/crawl/vietstock_links.txt", help="Đường dẫn file kết quả tương đối từ PROJECT_DIR")

    args = parser.parse_args()

    if args.debug:
        print(f"PROJECT_DIR: {PROJECT_DIR.as_posix()}")

    asyncio.run(main(
        start_date=args.start,
        end_date=args.start if not args.end else args.end,
        debug=args.debug,
        headless=not args.head,
        output_file_dir=args.output
    ))
