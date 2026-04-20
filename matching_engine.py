"""성분 매칭 엔진 — 논문 트렌드와 종근당 제품을 자동 매칭"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def load_product_db() -> list[dict]:
    """종근당 제품-성분 DB 로드."""
    db_path = DATA_DIR / "product_ingredient_db.json"
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def match_article_to_products(article: dict, products: list[dict] = None) -> list[dict]:
    """
    논문 1건을 종근당 제품들과 매칭.

    반환: [{"product": {...}, "match_type": "direct"|"indirect"|"keyword", "score": int, "matched_terms": [...]}]
    """
    if products is None:
        products = load_product_db()

    title = (article.get("title") or "").lower()
    abstract = (article.get("abstract") or "").lower()
    mesh_terms = [m.lower() for m in article.get("mesh_terms", [])]
    keywords = [k.lower() for k in article.get("keywords", [])]

    all_text = f"{title} {abstract} {' '.join(mesh_terms)} {' '.join(keywords)}"

    matches = []

    for product in products:
        score = 0
        match_type = None
        matched_terms = []

        # 직접 매칭: 영문 성분 키워드가 논문에 있는지
        for kw in product.get("ingredient_keywords_en", []):
            kw_lower = kw.lower()
            if kw_lower in title:
                score += 10
                matched_terms.append(f"[제목] {kw}")
                match_type = "direct"
            elif kw_lower in abstract:
                score += 5
                matched_terms.append(f"[초록] {kw}")
                if match_type is None:
                    match_type = "direct"

        # MeSH 매칭
        for kw in product.get("ingredient_keywords_en", []):
            kw_lower = kw.lower()
            for mesh in mesh_terms:
                if kw_lower in mesh:
                    score += 7
                    matched_terms.append(f"[MeSH] {mesh}")
                    if match_type is None:
                        match_type = "direct"

        # 간접 매칭: 효능 키워드
        for claim in product.get("health_claims", []):
            claim_en_map = {
                "관절 건강": ["joint", "arthritis", "cartilage", "knee"],
                "연골 구성성분": ["cartilage", "chondrocyte"],
                "관절 기능 개선": ["joint function", "mobility", "osteoarthritis"],
                "장 건강": ["gut", "intestinal", "bowel", "digestive"],
                "유익균 증식": ["beneficial bacteria", "colonization"],
                "유해균 억제": ["pathogen", "antimicrobial"],
                "배변활동 원활": ["bowel movement", "constipation", "transit"],
                "인지기능 개선": ["cognitive", "cognition", "mental"],
                "기억력 개선": ["memory", "recall", "learning"],
                "두뇌 건강": ["brain", "neural", "neuroprotect"],
                "집중력": ["attention", "focus", "concentration"],
                "눈 건강": ["eye", "ocular", "visual"],
                "황반색소밀도 유지": ["macular", "retinal", "MPOD"],
                "혈중 중성지방 개선": ["triglyceride", "lipid", "cholesterol"],
                "혈행 개선": ["circulation", "vascular", "blood flow"],
                "간 건강": ["liver", "hepatic", "hepatoprotect"],
                "간세포 보호": ["hepatocyte", "liver protection"],
                "항산화": ["antioxidant", "oxidative stress", "free radical"],
                "면역 기능": ["immune", "immunity", "immunomodulat"],
                "피부 보습": ["skin hydration", "moistur"],
                "피부 탄력": ["skin elasticity", "wrinkle", "collagen"],
                "전립선 건강": ["prostate", "BPH", "urinary"],
                "체지방 감소": ["body fat", "weight loss", "obesity", "adipose"],
                "콜레스테롤 개선": ["cholesterol", "LDL", "lipid"],
                "뼈 건강": ["bone", "osteoporosis", "bone density"],
            }
            en_keywords = claim_en_map.get(claim, [])
            for ek in en_keywords:
                if ek.lower() in all_text:
                    score += 3
                    matched_terms.append(f"[효능] {claim} → {ek}")
                    if match_type is None:
                        match_type = "indirect"

        if score > 0:
            # 매칭 등급 판단
            if score >= 15:
                relevance = "★★★ 즉시 활용"
            elif score >= 8:
                relevance = "★★ 콘텐츠 기획"
            else:
                relevance = "★ 모니터링"

            matches.append({
                "brand": product["brand"],
                "category": product["category"],
                "match_type": match_type or "keyword",
                "score": score,
                "relevance": relevance,
                "matched_terms": matched_terms,
                "target": product.get("target_demographic", {}),
            })

    # 점수 높은 순 정렬
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


# 타겟 세그먼트 정의
TARGET_SEGMENTS = [
    {
        "name": "시니어 건강",
        "gender": "남녀",
        "age": "50-70대",
        "interests": "관절, 뼈, 인지기능",
        "tone": "신뢰, 안심, 전문성",
    },
    {
        "name": "중년 활력",
        "gender": "남녀",
        "age": "40-50대",
        "interests": "피로회복, 기억력, 면역",
        "tone": "활력, 관리, 예방",
    },
    {
        "name": "직장인",
        "gender": "남녀",
        "age": "30-40대",
        "interests": "장 건강, 면역, 스트레스",
        "tone": "실용, 간편, 효율",
    },
    {
        "name": "수험생/학부모",
        "gender": "여성",
        "age": "40-50대",
        "interests": "집중력, 기억력",
        "tone": "응원, 과학적 근거",
    },
    {
        "name": "MZ 건강",
        "gender": "남녀",
        "age": "20-30대",
        "interests": "다이어트, 장 건강, 피부",
        "tone": "트렌디, 가벼움",
    },
]


if __name__ == "__main__":
    # 테스트: 가상의 논문으로 매칭 테스트
    test_article = {
        "title": "Phosphatidylserine supplementation improves cognitive function in older adults: a meta-analysis",
        "abstract": "This meta-analysis of 10 randomized controlled trials found that phosphatidylserine supplementation significantly improved memory and cognitive function in adults aged 50-70. The brain health benefits were most pronounced in subjects with mild cognitive decline.",
        "mesh_terms": ["Phosphatidylserines", "Cognition", "Dietary Supplements", "Aged"],
        "keywords": ["phosphatidylserine", "cognitive function", "memory", "supplement"],
    }

    products = load_product_db()
    matches = match_article_to_products(test_article, products)

    print("=== 매칭 결과 ===\n")
    for m in matches:
        print(f"  {m['relevance']} | {m['brand']} ({m['category']})")
        print(f"    매칭 유형: {m['match_type']} | 점수: {m['score']}")
        print(f"    매칭 근거: {', '.join(m['matched_terms'][:5])}")
        print()
