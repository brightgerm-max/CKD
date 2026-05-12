"""Meta Ad Library 크롤러 — Playwright 기반 (서브프로세스 실행)"""

import re
import json
import subprocess
import sys


def crawl_meta_ads(keyword: str, country: str = "KR", max_ads: int = 10) -> list[dict]:
    """서브프로세스에서 Playwright 크롤링 실행 (Streamlit asyncio 충돌 방지)"""
    try:
        result = subprocess.run(
            [sys.executable, __file__, keyword, country, str(max_ads)],
            capture_output=True, timeout=60,
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        if result.returncode == 0 and stdout:
            return json.loads(stdout)
    except Exception as e:
        print(f"[meta_crawler] subprocess error: {e}")
    return []


def _crawl_internal(keyword: str, country: str = "KR", max_ads: int = 10) -> list[dict]:
    """
    Meta Ad Library에서 키워드로 광고를 검색하여 크롤링.
    반환: [{"advertiser", "text", "start_date", "library_id", "platforms", "url"}, ...]
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    import urllib.parse
    encoded = urllib.parse.quote(keyword)
    url = (
        f"https://www.facebook.com/ads/library/"
        f"?active_status=active&ad_type=all&country={country}"
        f"&media_type=all&q={encoded}&search_type=keyword_unordered"
        f"&sort_data[direction]=desc&sort_data[mode]=total_impressions"
    )

    ads = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(8000)

            # 광고 이미지 URL 추출
            ad_images = page.evaluate('''() => {
                const results = [];
                const seen = new Set();
                const media = document.querySelectorAll("img, video");
                for (const el of media) {
                    let src = "";
                    if (el.tagName === "VIDEO") {
                        src = el.poster || "";
                    } else {
                        src = el.src || el.dataset.src || "";
                    }
                    if (!src || seen.has(src)) continue;
                    if ((src.includes("scontent") || src.includes("fbcdn") || src.includes("cdninstagram"))) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 || rect.height > 100 || src.includes("s600x600") || src.includes("s1080x1080")) {
                            seen.add(src);
                            results.push(src);
                        }
                    }
                }
                return results;
            }''')

            # 페이지 텍스트 추출
            all_text = page.inner_text("body")
            lines = [l.strip() for l in all_text.split("\n") if l.strip()]

            # 광고 파싱
            current_ad = None
            text_buffer = []

            for i, line in enumerate(lines):
                # 라이브러리 ID 감지 → 새 광고 시작
                if "라이브러리 ID:" in line:
                    # 이전 광고 저장
                    if current_ad and current_ad.get("advertiser"):
                        current_ad["text"] = "\n".join(text_buffer).strip()
                        if current_ad["text"]:
                            ads.append(current_ad)
                        if len(ads) >= max_ads:
                            break

                    lib_id = line.replace("라이브러리 ID:", "").strip()
                    current_ad = {
                        "library_id": lib_id,
                        "advertiser": "",
                        "start_date": "",
                        "text": "",
                        "cta": "",
                        "landing_url": "",
                        "platforms": [],
                        "url": f"https://www.facebook.com/ads/library/?id={lib_id}",
                    }
                    text_buffer = []

                elif current_ad is not None:
                    # 게재 시작일
                    if "게재 시작" in line:
                        date_match = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", line)
                        if date_match:
                            current_ad["start_date"] = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"

                    # 광고주명 (보통 "광고" 바로 앞 줄)
                    elif line == "광고" and i > 0:
                        # 바로 이전 줄이 광고주명
                        prev = lines[i-1].strip() if i > 0 else ""
                        if prev and prev not in ["광고 상세 정보 보기", "드롭다운 열기", "플랫폼", "​"]:
                            current_ad["advertiser"] = prev

                    # CTA 버튼 감지
                    elif line in ["더 알아보기", "지금 구매하기", "Shop Now", "자세히 알아보기",
                                  "지금 쇼핑하기", "가입하기", "예약하기", "다운로드", "문의하기",
                                  "지금 신청하기", "지금 주문하기", "더 보기", "구매하기"]:
                        current_ad["cta"] = line
                        # CTA 앞 2줄을 CTA 설명으로 분리
                        cta_desc_lines = []
                        while text_buffer and len(cta_desc_lines) < 2:
                            cta_desc_lines.insert(0, text_buffer.pop())
                        current_ad["cta_desc"] = "\n".join(cta_desc_lines)

                    # 랜딩 URL 감지 (대문자 도메인)
                    elif line.endswith(".COM") or line.endswith(".CO.KR") or line.endswith(".KR") or ".com" in line.lower():
                        if len(line) < 50 and "facebook" not in line.lower():
                            current_ad["landing_url"] = line

                    # 플랫폼/UI 텍스트 스킵
                    elif line in ["플랫폼", "드롭다운 열기", "광고 상세 정보 보기", "​", "활성",
                                  "정렬", "필터", "삭제", "정렬 기준", "활동 상태: 게재 중인 광고",
                                  "0:00 / 0:25", "0:00 / 0:28", "0:00 / 0:30", "0:00 / 0:15"]:
                        continue

                    # 동영상 길이 스킵
                    elif re.match(r"^\d+:\d+\s*/\s*\d+:\d+$", line):
                        continue

                    # 광고 텍스트
                    elif current_ad.get("advertiser") and len(line) > 3:
                        text_buffer.append(line)

            # 마지막 광고 저장
            if current_ad and current_ad.get("advertiser"):
                current_ad["text"] = "\n".join(text_buffer).strip()
                if current_ad["text"] and len(ads) < max_ads:
                    ads.append(current_ad)

            # 이미지 매칭 (순서대로 할당)
            for i, ad in enumerate(ads):
                if i < len(ad_images):
                    ad["image_url"] = ad_images[i]
                else:
                    ad["image_url"] = ""

            browser.close()

    except Exception as e:
        print(f"[meta_crawler] Error: {e}")

    return ads


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        # 서브프로세스 모드: 결과를 JSON으로 stdout 출력
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        kw = sys.argv[1]
        country = sys.argv[2]
        max_n = int(sys.argv[3])
        results = _crawl_internal(kw, country, max_n)
        print(json.dumps(results, ensure_ascii=False))
    else:
        # 직접 실행 테스트
        results = crawl_meta_ads("유산균", max_ads=3)
        for ad in results:
            sys.stderr.write(f"광고주: {ad['advertiser']}\n")
            sys.stderr.write(f"텍스트: {ad['text'][:80]}...\n\n")
