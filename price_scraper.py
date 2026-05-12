"""상품 URL에서 직접 가격 추출 — Playwright 서브프로세스"""

import re
import json
import subprocess
import sys
import os


def scrape_price_from_url(url: str) -> dict:
    """URL에서 가격 추출. 서브프로세스 실행."""
    if not url:
        return {}
    try:
        result = subprocess.run(
            [sys.executable, __file__, url],
            capture_output=True, timeout=45,
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        if result.returncode == 0 and stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                return {}
        return {}
    except Exception:
        return {}


def scrape_prices_from_urls(urls: dict) -> dict:
    """채널별 URL dict에서 가격 추출. {"naver": url, "coupang": url, "brand": url}"""
    result = {"naver": [], "coupang": [], "brand": []}
    for ch_key in ["naver", "coupang", "brand"]:
        url = urls.get(ch_key, "")
        if not url:
            continue
        data = scrape_price_from_url(url)
        if data and data.get("price", 0) > 0:
            result[ch_key] = [data]
    return result


def _extract_price(url: str) -> dict:
    """Playwright로 페이지에서 가격 추출"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            price = 0
            name = ""
            quantity_raw = ""
            days = 0

            # ── 네이버 스토어 ──
            if any(d in url for d in ["smartstore.naver.com", "brand.naver.com", "shopping.naver.com"]):
                # 가격 추출 (여러 셀렉터 시도)
                price_selectors = [
                    "span._1LY7DqCnwR",           # 스마트스토어 가격
                    "span.lowestPrice_num__A5gM9",  # 브랜드스토어
                    "span._2pgHN-ntx6",
                    "div.product_info_area span._3_7Uh",
                    "span[class*='price'] strong",
                    "em.sale_price",
                ]
                for sel in price_selectors:
                    el = page.query_selector(sel)
                    if el:
                        txt = el.inner_text().strip().replace(",", "").replace("원", "")
                        m = re.search(r"(\d+)", txt)
                        if m and int(m.group(1)) > 100:
                            price = int(m.group(1))
                            break

                # 가격을 JS로도 시도
                if price == 0:
                    price = page.evaluate('''() => {
                        const els = document.querySelectorAll('[class*="price"], [class*="Price"]');
                        for (const el of els) {
                            const text = el.innerText.replace(/,/g, '').replace(/원/g, '');
                            const m = text.match(/(\d{4,})/);
                            if (m) return parseInt(m[1]);
                        }
                        return 0;
                    }''') or 0

                # 상품명
                name_el = page.query_selector("h3._22kNQuEXmb, span._3oDjSvLfl3, h2[class*='name'], div.product_title")
                if name_el:
                    name = name_el.inner_text().strip()

            # ── 쿠팡 ──
            elif "coupang.com" in url:
                price_selectors = [
                    "span.total-price strong",
                    "span.total-price",
                    "div.prod-sale-price span.total-price",
                ]
                for sel in price_selectors:
                    el = page.query_selector(sel)
                    if el:
                        txt = el.inner_text().strip().replace(",", "").replace("원", "")
                        m = re.search(r"(\d+)", txt)
                        if m and int(m.group(1)) > 100:
                            price = int(m.group(1))
                            break

                if price == 0:
                    price = page.evaluate('''() => {
                        const el = document.querySelector('.total-price strong, .total-price');
                        if (el) {
                            const m = el.innerText.replace(/,/g, '').match(/(\d{4,})/);
                            if (m) return parseInt(m[1]);
                        }
                        return 0;
                    }''') or 0

                name_el = page.query_selector("h2.prod-buy-header__title, h1.prod-buy-header__title")
                if name_el:
                    name = name_el.inner_text().strip()

            # ── 일반 사이트 (자사몰 등) ──
            else:
                # 범용 가격 추출
                price = page.evaluate('''() => {
                    // 가격 관련 클래스/속성 탐색
                    const selectors = [
                        '[class*="sale_price"]', '[class*="salePrice"]',
                        '[class*="total-price"]', '[class*="totalPrice"]',
                        '[class*="price"] strong', '.price',
                        '[class*="cost"]', 'ins',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = el.innerText.replace(/,/g, '').replace(/원/g, '');
                            const m = text.match(/(\d{4,})/);
                            if (m) return parseInt(m[1]);
                        }
                    }
                    // body 텍스트에서 가격 패턴 찾기
                    const body = document.body.innerText;
                    const priceMatch = body.match(/(\d{1,3}(?:,\d{3})+)\s*원/);
                    if (priceMatch) return parseInt(priceMatch[1].replace(/,/g, ''));
                    return 0;
                }''') or 0

                name_el = page.query_selector("h1, h2, [class*='product_name'], [class*='productName']")
                if name_el:
                    name = name_el.inner_text().strip()[:100]

            # 상품명에서 수량 파싱
            if not name:
                name = page.title()
            quantity_raw, days = _parse_quantity_from_name(name)

            browser.close()

            if price > 0:
                daily_price = round(price / days) if days > 0 else 0
                return {
                    "name": name[:100],
                    "price": price,
                    "link": url,
                    "mall": "",
                    "quantity": quantity_raw,
                    "days": days,
                    "daily_price": daily_price,
                }
    except Exception:
        pass

    return {}


def _parse_quantity_from_name(name: str) -> tuple:
    """상품명에서 수량 추출 → (raw, days)"""
    name = name.lower().replace(",", "")

    m = re.search(r"(\d+)\s*일\s*분", name)
    if m:
        return (m.group(0), int(m.group(1)))

    m = re.search(r"(\d+)\s*개월\s*분", name)
    if m:
        return (m.group(0), int(m.group(1)) * 30)

    m = re.search(r"(\d+)\s*(?:포|정|캡슐|입|매)\s*[x×\*]?\s*(\d+)\s*(?:통|개|박스|병|봉|세트|팩)?", name)
    if m:
        total = int(m.group(1)) * int(m.group(2))
        return (f"{m.group(1)}x{m.group(2)}={total}", total)

    m = re.search(r"(\d+)\s*(?:포|정|캡슐|입|매)", name)
    if m:
        return (m.group(0), int(m.group(1)))

    return ("", 0)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        target_url = sys.argv[1]
        result = _extract_price(target_url)
        print(json.dumps(result, ensure_ascii=False))
