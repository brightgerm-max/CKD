"""가격 비교 클라이언트 — 네이버 쇼핑 API 기반"""

import os
import re
import requests

SEARCH_CLIENT_ID = os.environ.get("NAVER_SEARCH_ID", "")
SEARCH_CLIENT_SECRET = os.environ.get("NAVER_SEARCH_SECRET", "")


def search_product_prices(product_name: str, display: int = 20, brand_keywords: list = None) -> dict:
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
        # 가격순 + 정확도순 모두 검색해서 합침 (자사몰이 가격순에서 누락되는 경우 대비)
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
        # 중복 제거
        seen = set()
        items = []
        for item in all_items:
            key = (item.get("productId",""), item.get("mallName",""), item.get("lprice",""))
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

        entry = {"name": name, "price": price, "link": link, "mall": mall}

        mall_lower = mall.lower()
        brand_kws = brand_keywords or ["종근당", "ckd", "ckdmall", "종근당건강"]
        is_brand = any(bk.lower() in mall_lower or bk in mall for bk in brand_kws)

        if "쿠팡" in mall or "coupang" in mall_lower:
            result["coupang"].append(entry)
        elif is_brand:
            result["brand"].append(entry)
        else:
            result["naver"].append(entry)

    # 각 채널별 최저가 정렬
    for ch in ["naver", "coupang", "brand"]:
        result[ch].sort(key=lambda x: x["price"])

    # 쿠팡/자사몰 검색 링크 (네이버 쇼핑에 없을 경우 대비)
    import urllib.parse
    encoded = urllib.parse.quote(product_name)
    result["coupang_search_url"] = f"https://www.coupang.com/np/search?q={encoded}"
    result["brand_search_url"] = f"https://www.ckdmall.co.kr/search?q={encoded}"

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
