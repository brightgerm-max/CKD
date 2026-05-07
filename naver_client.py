"""네이버 API 클라이언트 — 데이터랩(검색 트렌드) + 뉴스 검색(TV 방송)"""

import os
import requests
from datetime import datetime, timedelta

# 환경변수에서 API 키 로드
DATALAB_CLIENT_ID = os.environ.get("NAVER_DATALAB_ID", "")
DATALAB_CLIENT_SECRET = os.environ.get("NAVER_DATALAB_SECRET", "")
SEARCH_CLIENT_ID = os.environ.get("NAVER_SEARCH_ID", "")
SEARCH_CLIENT_SECRET = os.environ.get("NAVER_SEARCH_SECRET", "")

DATALAB_HEADERS = {
    "X-Naver-Client-Id": DATALAB_CLIENT_ID,
    "X-Naver-Client-Secret": DATALAB_CLIENT_SECRET,
}

SEARCH_HEADERS = {
    "X-Naver-Client-Id": SEARCH_CLIENT_ID,
    "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET,
}


# ─── 데이터랩: 검색 트렌드 ───
def fetch_search_trend(keywords_kr: list[str], months_back: int = 12) -> list[dict]:
    """
    네이버 데이터랩 검색어 트렌드 API.
    반환: [{"period": "2024-05-01", "ratio": 85.2}, ...]
    """
    end = datetime.now()
    start = end - timedelta(days=months_back * 30)

    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": "month",
        "keywordGroups": [
            {"groupName": keywords_kr[0], "keywords": keywords_kr}
        ],
    }

    try:
        resp = requests.post(
            "https://openapi.naver.com/v1/datalab/search",
            headers={**DATALAB_HEADERS, "Content-Type": "application/json"},
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results and results[0].get("data"):
            return results[0]["data"]
    except Exception:
        pass
    return []


def fetch_multi_keyword_trend(
    keywords: list[str],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
) -> dict[str, list[dict]]:
    """
    여러 키워드의 검색 트렌드를 배치로 조회 (5개씩 분할).
    반환: {"키워드1": [{"period","ratio"}, ...], "키워드2": [...], ...}
    """
    results = {}
    batch_size = 5

    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]
        keyword_groups = [
            {"groupName": kw, "keywords": [kw]}
            for kw in batch
        ]

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": keyword_groups,
        }

        try:
            resp = requests.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={**_get_datalab_headers(), "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                kw_name = item.get("title", "")
                results[kw_name] = item.get("data", [])
        except Exception:
            for kw in batch:
                results[kw] = []

        import time as _time
        _time.sleep(0.3)

    return results


# ─── 뉴스 검색: TV 건강 프로그램 관련 기사 ───
TV_PROGRAMS = ["나는몸신이다", "생로병사의비밀", "명의", "건강톡톡", "좋은아침", "생방송오늘아침"]


def search_tv_health_news(ingredient_kr: str, display: int = 5) -> list[dict]:
    """
    네이버 뉴스 검색 API로 건강 프로그램 + 성분 관련 기사 검색.
    반환: [{"title", "link", "description", "pubDate"}, ...]
    """
    queries = [
        f"{ingredient_kr} 건강 방송",
        f"{ingredient_kr} TV 효능",
    ]

    seen_links = set()
    results = []

    for query in queries:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers=SEARCH_HEADERS,
                params={"query": query, "display": display, "sort": "date"},
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            for item in items:
                link = item.get("link", "")
                if link not in seen_links:
                    seen_links.add(link)
                    # HTML 태그 제거
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                    results.append({
                        "title": title,
                        "link": link,
                        "description": desc,
                        "pubDate": item.get("pubDate", ""),
                    })
        except Exception:
            continue

    return results[:display]


if __name__ == "__main__":
    print("=== 검색 트렌드 테스트 ===")
    trend = fetch_search_trend(["유산균", "프로바이오틱스"])
    for t in trend:
        print(f"  {t['period']} → {t['ratio']}")

    print("\n=== TV 건강 뉴스 테스트 ===")
    news = search_tv_health_news("유산균")
    for n in news:
        print(f"  {n['title']}")
        print(f"    {n['link']}")
