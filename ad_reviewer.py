"""광고 심의 사전 검토 엔진 — 금지 표현 감지 + 기능성 범위 대조"""

import re

# ─── 금지 표현 키워드 DB ───
# 법 제8조 부당 표시·광고 기준

PROHIBITED_PATTERNS = {
    "질병 치료·예방 표현": {
        "level": "critical",
        "law": "법 제8조 제1호",
        "desc": "질병의 예방·치료에 효능이 있는 것으로 인식할 우려가 있는 표현",
        "keywords": [
            "치료", "완치", "치유", "낫다", "낫게", "고치다", "고친다",
            "예방", "방지", "억제", "차단", "막아",
            "투병", "극복", "퇴치", "박멸",
            "암", "당뇨", "고혈압", "치매", "관절염", "위염", "간염",
            "아토피", "비염", "천식", "우울증", "불면증",
            "혈당 조절", "혈압 정상화", "종양", "세포 파괴",
        ],
        "patterns": [
            r"질병.{0,5}(예방|치료|개선)",
            r"(암|당뇨|고혈압|치매).{0,10}(효과|효능|개선|치료|예방)",
            r"병.{0,3}(낫|치료|고치)",
        ],
    },
    "의약품 혼동 표현": {
        "level": "critical",
        "law": "법 제8조 제2호",
        "desc": "식품등을 의약품으로 인식할 우려가 있는 표현",
        "keywords": [
            "처방", "투약", "복용량", "용법", "용량",
            "부작용 없는 약", "천연 약", "식물성 약",
            "임상 치료", "약효", "약리", "의약",
        ],
        "patterns": [
            r"(약|의약품).{0,5}(대체|대신|효과)",
            r"처방.{0,3}(없이|필요)",
        ],
    },
    "거짓·과장 표현": {
        "level": "high",
        "law": "법 제8조 제4호",
        "desc": "거짓이거나 과장된 표시 또는 광고",
        "keywords": [
            "100% 효과", "확실한 효과", "무조건", "반드시",
            "기적", "놀라운", "획기적", "혁명적", "마법",
            "즉시 효과", "즉효", "단번에",
            "세계 최초", "국내 유일", "독보적",
            "모든 사람", "누구나",
            "완벽한", "절대적",
        ],
        "patterns": [
            r"100\s*%\s*(효과|개선|보장)",
            r"(즉시|바로|단번에).{0,5}(효과|개선|변화)",
            r"(세계|국내)\s*(최초|유일|최고)",
        ],
    },
    "소비자 기만 표현": {
        "level": "high",
        "law": "법 제8조 제5호",
        "desc": "소비자를 기만하는 표시 또는 광고",
        "keywords": [
            "의사 추천", "약사 추천", "전문가 추천",
            "병원 납품", "의료기관 사용",
            "특허 성분", "독점 원료",
        ],
        "patterns": [
            r"(의사|약사|전문가|교수).{0,5}(추천|권장|인정)",
            r"(병원|의료기관).{0,5}(사용|납품|채택)",
        ],
    },
    "비교·비방 표현": {
        "level": "medium",
        "law": "법 제8조 제6·7호",
        "desc": "다른 업체를 비방하거나 부당하게 비교하는 표현",
        "keywords": [
            "타사 대비", "경쟁사보다", "OO보다 우수",
            "유일한 효과", "다른 제품은",
        ],
        "patterns": [
            r"(타사|경쟁사|다른\s*제품).{0,10}(대비|보다|비해|열등|부족)",
        ],
    },
    "주의 표현 (기능성 범위)": {
        "level": "medium",
        "law": "자율심의 운영규정 제3조",
        "desc": "식약처 인정 기능성 범위를 초과하는 표현",
        "keywords": [
            "다이어트 효과", "살 빠지는", "체중 감량 보장",
            "피부가 젊어", "주름 제거", "노화 방지",
            "면역력 강화", "면역력 증강",
            "뇌 기능 향상", "지능 향상", "IQ 상승",
            "성기능", "발기", "정력",
        ],
        "patterns": [
            r"(살|체중|지방).{0,5}(빠지|감량|제거|분해)",
            r"(주름|노화).{0,5}(제거|방지|역전|없애)",
        ],
    },
}

# ─── 허용 표현 (식약처 인정 기능성 문구) ───
ALLOWED_CLAIMS = {
    "장 건강": [
        "장 건강에 도움을 줄 수 있음",
        "유익균 증식에 도움을 줄 수 있음",
        "유해균 억제에 도움을 줄 수 있음",
        "배변활동 원활에 도움을 줄 수 있음",
    ],
    "관절 건강": [
        "관절 건강에 도움을 줄 수 있음",
        "연골 구성성분",
        "관절 기능 개선에 도움을 줄 수 있음",
    ],
    "두뇌 건강": [
        "인지기능 개선에 도움을 줄 수 있음",
        "기억력 개선에 도움을 줄 수 있음",
    ],
    "눈 건강": [
        "눈 건강에 도움을 줄 수 있음",
        "황반색소밀도 유지에 도움을 줄 수 있음",
        "눈의 피로 개선에 도움을 줄 수 있음",
    ],
    "혈행 건강": [
        "혈중 중성지방 개선에 도움을 줄 수 있음",
        "혈행 개선에 도움을 줄 수 있음",
    ],
    "간 건강": [
        "간 건강에 도움을 줄 수 있음",
        "간세포 보호에 도움을 줄 수 있음",
    ],
    "면역 건강": [
        "항산화에 도움을 줄 수 있음",
        "면역 기능에 도움을 줄 수 있음",
    ],
    "피부 건강": [
        "피부 보습에 도움을 줄 수 있음",
        "피부 탄력에 도움을 줄 수 있음",
        "자외선에 의한 피부손상 보호에 도움을 줄 수 있음",
    ],
    "뼈 건강": [
        "뼈 건강에 도움을 줄 수 있음",
        "칼슘 흡수 촉진에 도움을 줄 수 있음",
    ],
    "콜레스테롤": [
        "콜레스테롤 개선에 도움을 줄 수 있음",
    ],
    "남성 건강": [
        "전립선 건강에 도움을 줄 수 있음",
        "배뇨 기능 개선에 도움을 줄 수 있음",
    ],
    "여성 건강": [
        "요로 건강에 도움을 줄 수 있음",
    ],
    "다이어트": [
        "체지방 감소에 도움을 줄 수 있음",
    ],
}


def review_ad_text(ad_text: str, product_category: str = "") -> dict:
    """
    광고 문구 사전 검토.

    반환: {
        "violations": [{"type", "level", "law", "desc", "matched", "position"}, ...],
        "warnings": [{"type", "level", "law", "desc", "matched", "position"}, ...],
        "allowed_claims": [허용 표현 리스트],
        "score": 0~100 (높을수록 안전),
        "summary": 요약 메시지,
    }
    """
    violations = []
    warnings = []

    ad_lower = ad_text.lower()

    for cat_name, cat_data in PROHIBITED_PATTERNS.items():
        level = cat_data["level"]
        law = cat_data["law"]
        desc = cat_data["desc"]

        # 키워드 매칭
        for kw in cat_data["keywords"]:
            if kw.lower() in ad_lower:
                # 위치 찾기
                idx = ad_lower.find(kw.lower())
                context_start = max(0, idx - 10)
                context_end = min(len(ad_text), idx + len(kw) + 10)
                context = ad_text[context_start:context_end]

                item = {
                    "type": cat_name,
                    "level": level,
                    "law": law,
                    "desc": desc,
                    "matched": kw,
                    "context": f"...{context}...",
                }

                if level in ("critical", "high"):
                    violations.append(item)
                else:
                    warnings.append(item)

        # 정규식 패턴 매칭
        for pattern in cat_data.get("patterns", []):
            matches = re.finditer(pattern, ad_text)
            for match in matches:
                # 이미 키워드로 감지된 것과 중복 체크
                matched_text = match.group()
                if not any(v["matched"] == matched_text for v in violations + warnings):
                    item = {
                        "type": cat_name,
                        "level": level,
                        "law": law,
                        "desc": desc,
                        "matched": matched_text,
                        "context": ad_text[max(0, match.start()-10):match.end()+10],
                    }
                    if level in ("critical", "high"):
                        violations.append(item)
                    else:
                        warnings.append(item)

    # 허용 표현 목록
    allowed = ALLOWED_CLAIMS.get(product_category, [])

    # 점수 산출 (100점 만점)
    critical_count = sum(1 for v in violations if v["level"] == "critical")
    high_count = sum(1 for v in violations if v["level"] == "high")
    medium_count = len(warnings)

    score = 100 - (critical_count * 30) - (high_count * 15) - (medium_count * 5)
    score = max(0, min(100, score))

    # 요약
    if critical_count > 0:
        summary = f"심의 부적합 가능성 높음 — 치명적 위반 {critical_count}건 감지"
    elif high_count > 0:
        summary = f"수정적합 가능성 — 주요 위반 {high_count}건 감지"
    elif medium_count > 0:
        summary = f"주의 필요 — 경미한 주의 사항 {medium_count}건"
    else:
        summary = "적합 가능성 높음 — 금지 표현 미감지"

    return {
        "violations": violations,
        "warnings": warnings,
        "allowed_claims": allowed,
        "score": score,
        "summary": summary,
    }


if __name__ == "__main__":
    test = "락토핏 골드는 장 건강 치료에 획기적인 효과가 있으며, 의사가 추천하는 유산균입니다. 100% 효과를 보장합니다."
    result = review_ad_text(test, "장 건강")
    print(f"점수: {result['score']}/100")
    print(f"요약: {result['summary']}")
    print(f"\n위반 {len(result['violations'])}건:")
    for v in result["violations"]:
        print(f"  [{v['level']}] {v['type']} — '{v['matched']}' ({v['law']})")
    print(f"\n주의 {len(result['warnings'])}건:")
    for w in result["warnings"]:
        print(f"  [{w['level']}] {w['type']} — '{w['matched']}' ({w['law']})")
    print(f"\n허용 표현:")
    for a in result["allowed_claims"]:
        print(f"  ✅ {a}")
