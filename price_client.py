"""가격 비교 클라이언트 — 네이버 쇼핑 API 기반"""

import os
import re
import requests

SEARCH_CLIENT_ID = os.environ.get("NAVER_SEARCH_ID", "")
SEARCH_CLIENT_SECRET = os.environ.get("NAVER_SEARCH_SECRET", "")


def search_product_prices(product_name: str, display: int = 20) -> dict:
    """
    네이버 쇼핑 API로 상품 검색 후 채널별 최저가 분류.
    반환: {
        "naver": [{"name","price","link","mall"}, ...],
        "coupang": [{"name","price","link","mall"}, ...],
        "brand": [{"name","price","link","mall"}, ...],
        "lowest": {"channel","price","name","link"},
    }
    """
    result = {"naver": [], "coupang": [], "brand": [], "lowest": None}

    if not SEARCH_CLIENT_ID:
        return result

    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={
                "X-Naver-Client-Id": SEARCH_CLIENT_ID,
                "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET,
            },
            params={"query": product_name, "display": display, "sort": "asc"},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception:
        return result

    for item in items:
        name = re.sub(r"</?b>", "", item.get("title", ""))
        price = int(item.get("lprice", 0))
        link = item.get("link", "")
        mall = item.get("mallName", "")

        if price <= 0:
            continue

        entry = {"name": name, "price": price, "link": link, "mall": mall}

        mall_lower = mall.lower()
        if "쿠팡" in mall or "coupang" in mall_lower:
            result["coupang"].append(entry)
        elif "종근당" in mall or "ckd" in mall_lower or "ckdmall" in mall_lower:
            result["brand"].append(entry)
        else:
            result["naver"].append(entry)

    # 각 채널별 최저가 정렬
    for ch in ["naver", "coupang", "brand"]:
        result[ch].sort(key=lambda x: x["price"])

    # 전체 최저가
    all_items = []
    if result["naver"]:
        all_items.append(("네이버", result["naver"][0]))
    if result["coupang"]:
        all_items.append(("쿠팡", result["coupang"][0]))
    if result["brand"]:
        all_items.append(("자사몰", result["brand"][0]))

    if all_items:
        lowest = min(all_items, key=lambda x: x[1]["price"])
        result["lowest"] = {"channel": lowest[0], **lowest[1]}

    return result


if __name__ == "__main__":
    import json
    prices = search_product_prices("락토핏 골드")
    print(f"네이버: {len(prices['naver'])}건")
    if prices["naver"]:
        print(f"  최저: {prices['naver'][0]['price']:,}원 ({prices['naver'][0]['mall']})")
    print(f"쿠팡: {len(prices['coupang'])}건")
    print(f"자사몰: {len(prices['brand'])}건")
    if prices["lowest"]:
        print(f"\n전체 최저: {prices['lowest']['channel']} {prices['lowest']['price']:,}원")
