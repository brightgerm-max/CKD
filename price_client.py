"""가격 비교 클라이언트 — 네이버 쇼핑 API 기반 + 단위 정규화"""

import os
import re
import urllib.parse
import requests

def _get_search_creds():
    return os.environ.get("NAVER_SEARCH_ID", ""), os.environ.get("NAVER_SEARCH_SECRET", "")


def _parse_quantity(title: str) -> dict:
    """
    상품명에서 수량/용량 정보 추출.
    반환: {"days": 일수, "units": 포/정/캡슐 수, "raw": 원본 표현}
    """
    title = title.lower().replace(",", "")

    # 일분 (예: 360일분, 4개월분, 5개월분)
    m = re.search(r"(\d+)\s*일\s*분", title)
    if m:
        return {"days": int(m.group(1)), "raw": m.group(0)}

    m = re.search(r"(\d+)\s*개월\s*분", title)
    if m:
        return {"days": int(m.group(1)) * 30, "raw": m.group(0)}

    # 포/정/캡슐 수 (곱셈 포함: 50포 x 3통, 50포 6개)
    # 패턴: 50포 x 3, 50포 3통, 50포 6개, 50정 x 2박스
    m = re.search(r"(\d+)\s*(?:포|정|캡슐|입|매)\s*[x×\*]?\s*(\d+)\s*(?:통|개|박스|병|봉|세트|팩)?", title)
    if m:
        per_unit = int(m.group(1))
        count = int(m.group(2))
        total = per_unit * count
        return {"days": total, "raw": f"{per_unit}x{count}={total}"}

    # 단순 포/정/캡슐 (예: 120포, 60정)
    m = re.search(r"(\d+)\s*(?:포|정|캡슐|입|매)", title)
    if m:
        return {"days": int(m.group(1)), "raw": m.group(0)}

    return {"days": 0, "raw": ""}


def search_product_prices(product_name: str, display: int = 20, brand_keywords: list = None) -> dict:
    """
    네이버 쇼핑 API로 상품 검색 후 채널별 분류 + 1일당 가격 계산.
    """
    result = {"naver": [], "coupang": [], "brand": [], "lowest": None,
              "coupang_search_url": "", "brand_search_url": ""}

    SEARCH_CLIENT_ID, SEARCH_CLIENT_SECRET = _get_search_creds()
    if not SEARCH_CLIENT_ID:
        return result

    try:
        all_items = []
        for sort_type in ["asc", "sim"]:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": SEARCH_CLIENT_ID,
                    "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET,
                },
                params={"query": product_name, "display": display, "sort": sort_type},
                timeout=10,
            )
            resp.raise_for_status()
            all_items.extend(resp.json().get("items", []))
        seen = set()
        items = []
        for item in all_items:
            key = (item.get("productId", ""), item.get("mallName", ""), item.get("lprice", ""))
            if key not in seen:
                seen.add(key)
                items.append(item)
    except Exception:
        return result

    for item in items:
        name = re.sub(r"</?b>", "", item.get("title", ""))
        price = int(item.get("lprice", 0))
        link = item.get("link", "")
        mall = item.get("mallName", "")

        if price <= 0:
            continue

        qty = _parse_quantity(name)
        daily_price = round(price / qty["days"]) if qty["days"] > 0 else 0

        entry = {
            "name": name, "price": price, "link": link, "mall": mall,
            "quantity": qty["raw"], "days": qty["days"], "daily_price": daily_price,
        }

        mall_lower = mall.lower()
        brand_kws = brand_keywords or ["종근당", "ckd", "ckdmall", "종근당건강"]
        is_brand = any(bk.lower() in mall_lower or bk in mall for bk in brand_kws)

        if "쿠팡" in mall or "coupang" in mall_lower:
            result["coupang"].append(entry)
        elif is_brand:
            result["brand"].append(entry)
        else:
            result["naver"].append(entry)

    # 1일당 가격 기준으로 정렬 (0이면 뒤로)
    for ch in ["naver", "coupang", "brand"]:
        result[ch].sort(key=lambda x: x["daily_price"] if x["daily_price"] > 0 else 999999)

    encoded = urllib.parse.quote(product_name)
    result["coupang_search_url"] = f"https://www.coupang.com/np/search?q={encoded}"
    result["brand_search_url"] = f"https://www.ckdmall.co.kr/search?q={encoded}"

    # 전체 최저가 (1일당 기준)
    candidates = []
    for ch_name, ch_key in [("네이버", "naver"), ("쿠팡", "coupang"), ("자사몰", "brand")]:
        for item in result[ch_key]:
            if item["daily_price"] > 0:
                candidates.append({"channel": ch_name, **item})
                break

    if candidates:
        result["lowest"] = min(candidates, key=lambda x: x["daily_price"])

    return result


if __name__ == "__main__":
    prices = search_product_prices("락토핏 골드")
    print(f"네이버: {len(prices['naver'])}건")
    for p in prices["naver"][:3]:
        print(f"  {p['price']:,}원 / {p['quantity']} / 1일 {p['daily_price']}원 ({p['mall']})")
    print(f"쿠팡: {len(prices['coupang'])}건")
    print(f"자사몰: {len(prices['brand'])}건")
    for p in prices["brand"][:2]:
        print(f"  {p['price']:,}원 / {p['quantity']} / 1일 {p['daily_price']}원 ({p['mall']})")
