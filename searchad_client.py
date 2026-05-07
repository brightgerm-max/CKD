"""네이버 검색광고 API + 데이터랩 기반 추정 검색량 산출"""

import os
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timedelta


def _get_searchad_creds():
    return {
        "api_key": os.environ.get("NAVER_AD_API_KEY", ""),
        "secret_key": os.environ.get("NAVER_AD_SECRET_KEY", ""),
        "customer_id": os.environ.get("NAVER_AD_CUSTOMER_ID", ""),
    }


def _get_datalab_creds():
    return {
        "client_id": os.environ.get("NAVER_DATALAB_ID", ""),
        "client_secret": os.environ.get("NAVER_DATALAB_SECRET", ""),
    }


def _make_signature(timestamp, method, path, secret_key):
    message = f"{timestamp}.{method}.{path}"
    sig = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


def fetch_keyword_search_volume(keywords: list[str]) -> dict:
    """
    검색광고 API로 키워드별 월간 검색량 조회.
    반환: {"키워드": {"pc": int, "mo": int, "total": int}, ...}
    """
    creds = _get_searchad_creds()
    if not creds["api_key"]:
        return {}

    result = {}
    import urllib.parse

    for kw in keywords:
        path = "/keywordstool"
        timestamp = str(int(time.time() * 1000))
        signature = _make_signature(timestamp, "GET", path, creds["secret_key"])

        headers = {
            "X-Timestamp": timestamp,
            "X-API-KEY": creds["api_key"],
            "X-Customer": creds["customer_id"],
            "X-Signature": signature,
            "Content-Type": "application/json",
        }

        # 공백 제거한 키워드로도 시도
        search_kw = kw.replace(" ", "")
        encoded = urllib.parse.quote(search_kw)
        url = f"https://api.searchad.naver.com{path}?hintKeywords={encoded}&showDetail=1"

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue

            data = resp.json()
            kw_list = data.get("keywordList", [])

            # 원본 키워드 또는 공백 제거 키워드와 매칭
            kw_lower = kw.lower()
            kw_nospace = search_kw.lower()

            for item in kw_list:
                rel = item.get("relKeyword", "")
                rel_lower = rel.lower()
                rel_nospace = rel.replace(" ", "").lower()

                if rel_lower == kw_lower or rel_nospace == kw_nospace or rel_lower == kw_nospace:
                    pc = _parse_count(item.get("monthlyPcQcCnt", 0))
                    mo = _parse_count(item.get("monthlyMobileQcCnt", 0))
                    result[kw] = {"pc": pc, "mo": mo, "total": pc + mo}
                    break
        except Exception:
            pass

        time.sleep(0.3)

    # 검색 결과에 없는 키워드는 0으로 채움
    for kw in keywords:
        if kw not in result:
            result[kw] = {"pc": 0, "mo": 0, "total": 0}

    return result


def _parse_count(value):
    if isinstance(value, str) and "<" in value:
        return 5  # "< 10" → 5로 추정
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def estimate_search_volume(
    keywords: list[str],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
) -> dict:
    """
    추정 검색량 산출.

    산출 공식:
    1. 검색광고 API → 기준월 PC/MO 월간 검색량
    2. 데이터랩 API → 기준월 포함 전체 기간 트렌드
    3. 변환계수 = 기준월 검색량 ÷ 기준월 트렌드값
    4. 대상 기간 추정 검색량 = 트렌드값 × 변환계수

    반환: {"키워드": [{"period": "2025-01", "volume": 12345}, ...], ...}
    """
    dl_creds = _get_datalab_creds()
    if not dl_creds["client_id"]:
        return {}

    # 1) 검색광고 API로 기준월 검색량
    ad_volumes = fetch_keyword_search_volume(keywords)

    # 2) 데이터랩 트렌드 조회 (5개씩 배치)
    trend_by_kw = {}

    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in batch]

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": keyword_groups,
        }

        try:
            resp = requests.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={
                    "X-Naver-Client-Id": dl_creds["client_id"],
                    "X-Naver-Client-Secret": dl_creds["client_secret"],
                    "Content-Type": "application/json",
                },
                json=body, timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    trend_by_kw[item["title"]] = item.get("data", [])
        except Exception:
            pass

        time.sleep(0.3)

    # 3) 변환계수 산출 + 추정 검색량 계산
    result = {}
    # 기준월: 최근 완료월
    now = datetime.now()
    ref_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    for kw in keywords:
        ad = ad_volumes.get(kw, {"total": 0})
        total_qc = ad["total"]
        trend_data = trend_by_kw.get(kw, [])

        if total_qc <= 0 or not trend_data:
            # 트렌드 지수 그대로 반환
            result[kw] = [{"period": d["period"], "volume": round(d["ratio"], 2)} for d in trend_data]
            continue

        # 기준월 트렌드값 찾기
        ref_trend = None
        for d in trend_data:
            if d["period"][:7] == ref_month and d["ratio"] > 0:
                ref_trend = d["ratio"]
                break

        # 기준월 못 찾으면 전전월
        if ref_trend is None:
            prev_month = (now.replace(day=1) - timedelta(days=32)).strftime("%Y-%m")
            for d in trend_data:
                if d["period"][:7] == prev_month and d["ratio"] > 0:
                    ref_trend = d["ratio"]
                    break

        # 그래도 못 찾으면 마지막 유효값
        if ref_trend is None:
            for d in reversed(trend_data):
                if d["ratio"] > 0:
                    ref_trend = d["ratio"]
                    break

        if ref_trend is None or ref_trend <= 0:
            result[kw] = [{"period": d["period"], "volume": round(d["ratio"], 2)} for d in trend_data]
            continue

        # 변환계수
        factor = total_qc / ref_trend

        # 추정 검색량
        volumes = []
        for d in trend_data:
            estimated = round(d["ratio"] * factor) if d["ratio"] > 0 else 0
            volumes.append({"period": d["period"], "volume": estimated})

        result[kw] = volumes

    return result


if __name__ == "__main__":
    import json
    result = estimate_search_volume(
        ["유산균", "프로바이오틱스"],
        "2025-04-01", "2026-04-20", "month"
    )
    for kw, data in result.items():
        print(f"\n{kw}:")
        for d in data:
            print(f"  {d['period'][:7]} → {d['volume']:,}")
