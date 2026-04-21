"""경쟁사 자동 탐색 — 네이버 쇼핑 API로 카테고리 경쟁 브랜드 + 성분 분석"""

import os
import re
import requests

def _get_search_creds():
    return os.environ.get("NAVER_SEARCH_ID", ""), os.environ.get("NAVER_SEARCH_SECRET", "")

# 건강기능식품 주요 성분 키워드
INGREDIENT_KEYWORDS = {
    "유산균": ["유산균", "프로바이오틱스", "비피더스", "락토바실러스", "비피도박테리움"],
    "프리바이오틱스": ["프리바이오틱스", "올리고당", "식이섬유"],
    "비타민": ["비타민A", "비타민B", "비타민C", "비타민D", "비타민E", "멀티비타민", "비타민"],
    "미네랄": ["칼슘", "마그네슘", "아연", "철분", "셀레늄"],
    "오메가3": ["오메가3", "EPA", "DHA", "rTG"],
    "콘드로이친": ["콘드로이친", "글루코사민", "관절", "연골"],
    "루테인": ["루테인", "지아잔틴", "황반", "눈"],
    "콜라겐": ["콜라겐", "히알루론산", "저분자"],
    "밀크씨슬": ["밀크씨슬", "실리마린", "간"],
    "홍국": ["홍국", "모나콜린", "콜레스테롤"],
    "가르시니아": ["가르시니아", "HCA", "다이어트", "체지방"],
    "포스파티딜세린": ["포스파티딜세린", "PS", "인지", "기억력", "두뇌"],
    "쏘팔메토": ["쏘팔메토", "전립선"],
    "크랜베리": ["크랜베리", "요로"],
    "코엔자임Q10": ["코엔자임", "CoQ10"],
    "면역": ["면역", "베타글루칸", "프로폴리스"],
}


def _extract_ingredients(title: str) -> list[str]:
    """상품명에서 성분 키워드 추출."""
    found = []
    title_lower = title.lower()
    for category, keywords in INGREDIENT_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title_lower:
                if category not in found:
                    found.append(category)
                break
    return found


def scan_competitors(
    category_keyword: str,
    ckd_brand: str = "",
    display: int = 40,
) -> list[dict]:
    """
    네이버 쇼핑에서 카테고리 키워드로 검색하여 경쟁 브랜드를 자동 추출.

    반환: [{
        "brand": 브랜드명,
        "product_name": 대표 상품명,
        "price": 가격,
        "link": 상품 링크,
        "ingredients": [성분 키워드 리스트],
        "mall": 판매처,
    }, ...]
    """
    SEARCH_CLIENT_ID, SEARCH_CLIENT_SECRET = _get_search_creds()
    if not SEARCH_CLIENT_ID:
        return []

    results = []
    seen_brands = set()
    ckd_lower = ckd_brand.lower()

    # 여러 검색어로 탐색
    queries = [
        f"{category_keyword} 건강기능식품",
        f"{category_keyword} 영양제",
        f"{category_keyword} 보충제",
    ]

    for query in queries:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": SEARCH_CLIENT_ID,
                    "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET,
                },
                params={"query": query, "display": display, "sort": "sim"},
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception:
            continue

        for item in items:
            name = re.sub(r"</?b>", "", item.get("title", ""))
            brand = item.get("brand", "") or item.get("maker", "") or item.get("mallName", "")

            if not brand:
                continue

            brand_lower = brand.lower()
            # 자사 제품 제외
            if "종근당" in brand or ckd_lower in brand_lower:
                continue
            # 중복 제외
            if brand in seen_brands:
                continue

            seen_brands.add(brand)
            ingredients = _extract_ingredients(name)
            price = int(item.get("lprice", 0))

            results.append({
                "brand": brand,
                "product_name": name[:80],
                "price": price,
                "link": item.get("link", ""),
                "ingredients": ingredients,
                "mall": item.get("mallName", ""),
            })

    # 가격 기준 정렬 (가격 있는 것 우선)
    results.sort(key=lambda x: x["price"] if x["price"] > 0 else 999999)
    return results


def compare_ingredients(ckd_ingredients: list[str], competitor_ingredients: list[str]) -> dict:
    """
    자사 vs 경쟁사 성분 비교.
    반환: {
        "ckd_only": 자사만 보유 성분,
        "competitor_only": 경쟁사만 보유 성분,
        "common": 공통 성분,
    }
    """
    ckd_set = set(i.lower() for i in ckd_ingredients)
    comp_set = set(i.lower() for i in competitor_ingredients)

    return {
        "ckd_only": sorted(ckd_set - comp_set),
        "competitor_only": sorted(comp_set - ckd_set),
        "common": sorted(ckd_set & comp_set),
    }


if __name__ == "__main__":
    print("=== 자동 경쟁사 탐색: '유산균' ===\n")
    competitors = scan_competitors("유산균", ckd_brand="락토핏")
    for i, c in enumerate(competitors[:10]):
        print(f"{i+1}. {c['brand']} | {c['price']:,}원 | 성분: {c['ingredients']}")
        print(f"   {c['product_name'][:50]}")
        print()

    # 성분 비교 테스트
    ckd_ings = ["유산균", "프로바이오틱스", "비피더스"]
    comp_ings = ["유산균", "비타민", "아연"]
    diff = compare_ingredients(ckd_ings, comp_ings)
    print(f"\n=== 성분 비교 ===")
    print(f"자사만: {diff['ckd_only']}")
    print(f"경쟁사만: {diff['competitor_only']}")
    print(f"공통: {diff['common']}")
