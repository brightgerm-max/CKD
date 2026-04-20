"""식약처 건강기능식품 API 클라이언트 — 기능성 원료 인정 현황 검색"""

import requests


MFDS_API_BASE = "https://openapi.foodsafetykorea.go.kr/api/sample/C003/json"


def search_health_food(keyword: str, max_results: int = 10) -> list[dict]:
    """
    식약처 건강기능식품 DB에서 원료명/기능성 키워드로 검색.
    전체 데이터에서 키워드 필터링 방식 (API 자체 검색 기능 없음).

    반환: [{"name", "company", "functionality", "ingredients", "report_no", "url"}, ...]
    """
    results = []
    page_size = 100
    keyword_lower = keyword.lower()

    # 여러 페이지 순회하며 키워드 매칭 (최대 1000건 탐색)
    for start in range(1, 1001, page_size):
        end = start + page_size - 1
        try:
            resp = requests.get(
                f"{MFDS_API_BASE}/{start}/{end}",
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("C003", {}).get("row", [])

            if not rows:
                break

            for row in rows:
                raw_nm = (row.get("RAWMTRL_NM") or "").lower()
                fnclty = (row.get("PRIMARY_FNCLTY") or "").lower()
                prd_nm = (row.get("PRDLST_NM") or "").lower()

                if keyword_lower in raw_nm or keyword_lower in fnclty or keyword_lower in prd_nm:
                    report_no = row.get("PRDLST_REPORT_NO", "")
                    results.append({
                        "name": row.get("PRDLST_NM", ""),
                        "company": row.get("BSSH_NM", ""),
                        "functionality": row.get("PRIMARY_FNCLTY", ""),
                        "ingredients": row.get("RAWMTRL_NM", ""),
                        "intake_method": row.get("NTK_MTHD", ""),
                        "caution": row.get("IFTKN_ATNT_MATR_CN", ""),
                        "report_no": report_no,
                        "approval_date": row.get("PRMS_DT", ""),
                        "url": f"https://www.foodsafetykorea.go.kr/portal/healthyfoodlife/searchHomeHF.do?search_code=01&prdlst_report_no={report_no}",
                    })

                    if len(results) >= max_results:
                        return results

        except Exception:
            break

    return results


if __name__ == "__main__":
    print("=== 식약처 건강기능식품 검색: '프로바이오틱스' ===\n")
    items = search_health_food("프로바이오틱스", max_results=5)
    for i, item in enumerate(items):
        print(f"{i+1}. {item['name']}")
        print(f"   업체: {item['company']}")
        print(f"   기능성: {item['functionality'][:80]}...")
        print(f"   원료: {item['ingredients'][:80]}...")
        print(f"   원문: {item['url']}")
        print()
