import asyncio
import json
import time
from pathlib import Path
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


async def parse_article(page: Page, debug: bool = False) -> tuple[str | None, str | None, str | None]:
    """
    Trích xuất nội dung bài viết từ page.

    Output:
    - str | None: title, head, body — tiêu đề, mở đầu, nội dung

    Input:
    - Page: page — trang Playwright đang mở bài viết
    - bool: debug — in log khi True
    """
    # beginf
    try:
        await page.wait_for_selector("[id*='vst_detail']", timeout=10000)
        post_el = page.locator("[id*='vst_detail']").first
        if debug:
            print("[LOG] Tìm thấy div có id chứa 'vst_detail'")
    except Exception as e:
        if debug:
            print(f"[LOG] Không tìm thấy div#vst_detail. Lỗi: {e}")
        return None, None, None

    def normalize(text: str) -> str:
        return text.replace("\xa0", " ").strip()

    # Title
    try:
        title_loc = post_el.locator("p.pTitle")
        title = normalize(await title_loc.first.text_content()) if await title_loc.count() > 0 else None
        if debug:
            print(f"[LOG] Title: {title}")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy title: {e}")
        title = None

    # Head
    try:
        head_loc = post_el.locator("p.pHead")
        head = normalize(await head_loc.first.inner_text()) if await head_loc.count() > 0 else None
        if debug:
            print(f"[LOG] Head: {head}")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy head: {e}")
        head = None

    # Body — nối tất cả các đoạn p.pBody theo thứ tự
    try:
        body_loc = post_el.locator("p.pBody")
        body_count = await body_loc.count()
        if body_count > 0:
            parts = [
                normalize(await body_loc.nth(i).inner_text())
                for i in range(body_count)
            ]
            body = "\n".join(parts)
        else:
            body = None
        if debug:
            print(f"[LOG] Body: {body}")
    except Exception as e:
        if debug:
            print(f"[LOG] Lỗi khi lấy body: {e}")
        body = None

    return title, head, body
    # endf


async def crawl_link(
    page: Page,
    link: str,
    debug: bool = False,
) -> tuple[str | None, str | None, str | None]:
    """
    Crawl một link Vietstock và trả về nội dung bài viết.

    Output:
    - str | None: title, head, body — tiêu đề, mở đầu, nội dung

    Input:
    - Page: page — trang Playwright đã được khởi tạo sẵn
    - str: link — URL bài viết Vietstock
    - bool: debug — in log khi True
    """
    # beginf
    print("[LOG] Đang crawl link:", link)

    await page.goto(link, timeout=60000, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    title, head, body = await parse_article(page, debug=debug)

    if debug:
        print(f"Title: {title}")
        print(f"Head: {head}")
        print(f"Body: {body}")

    if title and head and body:
        print(f"[LOG] Crawl data thành công từ link {link}")

    return title, head, body
    # endf


async def crawl_links(
    links: list[str],
    debug: bool = False,
    headless: bool = True,
) -> list[dict]:
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
    p, browser, page = await init_page(links[0], headless=headless)

    try:
        for i, link in enumerate(links):
            if i % 5 == 0:
                print(f"[LOG] Hiện tại đến link thứ {i + 1}/{total}")
            if i > 0 and i % 100 == 0:
                print(f"[LOG] Đã cào {i} links, nghỉ 2 phút...")
                await asyncio.sleep(120)
            title, head, body = await crawl_link(page, link, debug=debug)
            results.append({"link": link, "title": title, "head": head, "body": body})
    finally:
        await browser.close()
        await p.stop()

    return results
    # endf


async def main(
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

    input_file_path = PROJECT_DIR / links_file
    if not input_file_path.exists():
        print(f"[ERROR] File {input_file_path} không tồn tại. Vui lòng kiểm tra lại.")
        return
    print(f"[LOG] Đang đọc file link từ: {input_file_path.as_posix()}")

    output_file_path = input_file_path.parent / (
        input_file_path.stem.replace("links", "crawled_data") + ".jsonl"
    )
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[LOG] File kết quả sẽ được lưu tại: {output_file_path.as_posix()}")

    with open(input_file_path, "r", encoding="utf-8") as f:
        elements = [line.strip().split(",") for line in f.readlines()]
    print(f"[LOG] Tổng số link cần crawl: {len(elements)}")

    record_ids = [el[0] for el in elements]
    links = [el[-1] for el in elements]

    results = await crawl_links(links, debug=debug, headless=headless)

    with open(output_file_path, "w", encoding="utf-8") as out_f:
        for record_id, result in zip(record_ids, results):
            record = {"id": record_id, **result}
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    elapsed_time = time.time() - begin_time
    print(f"[LOG] Đã lưu kết quả vào: {output_file_path.as_posix()}")
    print(f"[LOG] Thời gian thực hiện: {elapsed_time:.2f} giây")
    # endf


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vietstock Data Crawler (Playwright)")
    parser.add_argument("--debug", action="store_true", help="Bật chế độ debug in ra log")
    parser.add_argument("--head", action="store_true", help="Hiển thị trình duyệt")
    parser.add_argument(
        "--links_file",
        type=str,
        default="data_pipelines/crawl/vietstock_links_20260601_20260601_CHUAN.txt",
        help="Đường dẫn file chứa các link cần crawl tương đối từ PROJECT_DIR",
    )

    args = parser.parse_args()

    asyncio.run(main(
        debug=args.debug,
        headless=not args.head,
        links_file=args.links_file,
    ))
