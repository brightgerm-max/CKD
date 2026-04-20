"""USP 자동 생성기 — AI(Claude)를 활용한 타겟별 마케팅 메시지 생성"""

import os

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from matching_engine import TARGET_SEGMENTS


def generate_usp_with_ai(
    article: dict,
    matched_product: dict,
    segments: list[dict] = None,
    api_key: str = None,
) -> list[dict]:
    """
    Claude API를 사용하여 논문 + 제품 매칭 결과로부터
    타겟 세그먼트별 USP 마케팅 메시지를 자동 생성.
    """
    if segments is None:
        segments = TARGET_SEGMENTS

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    if not key or not HAS_ANTHROPIC:
        return generate_usp_template(article, matched_product, segments)

    client = anthropic.Anthropic(api_key=key)

    segments_text = "\n".join(
        f"- {s['name']}: {s['gender']}, {s['age']}, 관심사({s['interests']}), 톤앤매너({s['tone']})"
        for s in segments
    )

    prompt = f"""당신은 건강기능식품 마케팅 전문가입니다. 아래 논문 정보와 매칭된 제품을 바탕으로, 각 타겟 세그먼트별 USP(Unique Selling Proposition) 마케팅 메시지를 생성해주세요.

## 논문 정보
- 제목: {article.get('title', '')}
- 초록: {article.get('abstract', '')[:500]}
- 저널: {article.get('journal', '')}
- 발표일: {article.get('pub_date', '')}

## 매칭된 종근당 제품
- 브랜드: {matched_product.get('brand', '')}
- 카테고리: {matched_product.get('category', '')}
- 매칭 근거: {', '.join(matched_product.get('matched_terms', [])[:5])}

## 타겟 세그먼트
{segments_text}

## 요청사항
각 타겟 세그먼트별로 아래 형식으로 출력해주세요:

[세그먼트명]
- 핵심 USP 메시지 (1줄, 광고 헤드라인용)
- 보조 메시지 (1줄, 상세 설명용)
- 추천 채널: (검색광고 / Meta DA / 네이버 블로그 / 인스타그램 / 카페 바이럴 중 택 1~2)
- 키워드 제안: (검색광고용 키워드 3개)

주의: 식약처 광고 심의 기준에 맞게, 과장하지 않고 논문 근거를 기반으로 작성해주세요. "치료", "완치" 등의 표현은 사용하지 마세요.
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text

    # AI 응답을 세그먼트별로 파싱
    results = []
    for segment in segments:
        results.append({
            "segment": segment["name"],
            "age": segment["age"],
            "gender": segment["gender"],
            "tone": segment["tone"],
            "ai_response": response_text,
            "source": "ai",
        })

    return results


def generate_usp_template(
    article: dict,
    matched_product: dict,
    segments: list[dict] = None,
) -> list[dict]:
    """
    AI API 없이 템플릿 기반으로 USP를 생성 (데모/폴백용).
    """
    if segments is None:
        segments = TARGET_SEGMENTS

    title = article.get("title", "")
    brand = matched_product.get("brand", "")
    category = matched_product.get("category", "")
    journal = article.get("journal", "해외 학술지")

    templates = {
        "시니어 건강": {
            "headline": f"국제학술지가 입증한 {category} 효과, {brand}",
            "sub": f"{journal} 게재 연구에서 확인된 과학적 근거, 믿을 수 있는 {brand}로 건강을 지키세요.",
            "channels": "검색광고, 네이버 블로그",
            "keywords": [f"{brand}", f"{category} 영양제", f"{category} 효과"],
        },
        "중년 활력": {
            "headline": f"지금부터 준비하는 {category}, 과학이 증명한 {brand}",
            "sub": f"최신 연구 결과로 입증된 {brand}의 효과. 40대부터 시작하는 현명한 건강관리.",
            "channels": "Meta DA, 인스타그램",
            "keywords": [f"40대 {category}", f"{brand} 효과", f"{category} 영양제 추천"],
        },
        "직장인": {
            "headline": f"바쁜 일상 속 {category} 관리, {brand} 하나로",
            "sub": f"글로벌 연구진이 확인한 {brand}의 효능. 하루 한 번으로 간편하게.",
            "channels": "검색광고, 인스타그램",
            "keywords": [f"직장인 {category}", f"{brand}", f"{category} 간편"],
        },
        "수험생/학부모": {
            "headline": f"세계적 연구진이 확인한 {category} 성분, 우리 아이에게도",
            "sub": f"{journal} 발표 연구 기반, 과학적으로 검증된 {brand}.",
            "channels": "네이버 카페, 블로그",
            "keywords": [f"수험생 {category}", f"{brand} 학생", f"집중력 영양제"],
        },
        "MZ 건강": {
            "headline": f"과학이 인정한 {category} 필수템, {brand}",
            "sub": f"최신 논문이 말하는 {category}의 중요성. 지금 시작해도 늦지 않았어요.",
            "channels": "인스타그램, Meta DA",
            "keywords": [f"{category} 추천", f"20대 영양제", f"{brand}"],
        },
    }

    results = []
    for segment in segments:
        seg_name = segment["name"]
        tmpl = templates.get(seg_name, templates["중년 활력"])

        results.append({
            "segment": seg_name,
            "age": segment["age"],
            "gender": segment["gender"],
            "tone": segment["tone"],
            "headline": tmpl["headline"],
            "sub_message": tmpl["sub"],
            "channels": tmpl["channels"],
            "keywords": tmpl["keywords"],
            "source": "template",
        })

    return results


if __name__ == "__main__":
    test_article = {
        "title": "Phosphatidylserine supplementation improves cognitive function in older adults",
        "abstract": "A meta-analysis of RCTs showed significant improvement in memory and attention.",
        "journal": "Journal of Clinical Nutrition",
        "pub_date": "2026-03",
    }
    test_match = {
        "brand": "포스파티딜세린",
        "category": "두뇌 건강",
        "matched_terms": ["[제목] phosphatidylserine", "[효능] 인지기능 개선 → cognitive"],
    }

    results = generate_usp_template(test_article, test_match)
    print("=== 타겟별 USP (템플릿 기반) ===\n")
    for r in results:
        print(f"[{r['segment']}] {r['age']} / {r['gender']}")
        print(f"  헤드라인: {r['headline']}")
        print(f"  보조 메시지: {r['sub_message']}")
        print(f"  추천 채널: {r['channels']}")
        print(f"  키워드: {', '.join(r['keywords'])}")
        print()
