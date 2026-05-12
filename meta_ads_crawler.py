"""Meta Ad Library 크롤러 — Playwright 기반 (서브프로세스 실행)"""

import re
import json
import subprocess
import sys


def crawl_meta_ads(keyword: str, country: str = "KR", max_ads: int = 28) -> list[dict]:
    """서브프로세스에서 Playwright 크롤링 실행 (Streamlit asyncio 충돌 방지)"""
    try:
        result = subprocess.run(
            [sys.executable, __file__, keyword, country, str(max_ads)],
            capture_output=True, timeout=90,
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        if result.returncode == 0 and stdout:
            return json.loads(stdout)
        # 에러 정보를 반환
        return [{"_error": f"rc={result.returncode}, stderr={stderr[:300]}"}]
    except Exception as e:
        return [{"_error": str(e)}]


def _crawl_internal(keyword: str, country: str = "KR", max_ads: int = 28) -> list[dict]:
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
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(8000)

            # 1) 라이브러리 ID + 게재일 + 광고주 추출 (텍스트 기반)
            all_text = page.inner_text("body")
            lines = [l.strip() for l in all_text.split("\n") if l.strip()]

            ad_meta_list = []
            current_meta = None

            for i, line in enumerate(lines):
                if "라이브러리 ID:" in line:
                    if current_meta:
                        ad_meta_list.append(current_meta)
                    lib_id = line.replace("라이브러리 ID:", "").strip()
                    current_meta = {"library_id": lib_id, "advertiser": "", "start_date": ""}
                elif current_meta:
                    if "게재 시작" in line:
                        dm = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", line)
                        if dm:
                            current_meta["start_date"] = f"{dm.group(1)}-{dm.group(2).zfill(2)}-{dm.group(3).zfill(2)}"
                    elif line == "광고" and i > 0:
                        prev = lines[i-1].strip()
                        if prev and prev not in ["광고 상세 정보 보기", "드롭다운 열기", "플랫폼", "\u200b"]:
                            current_meta["advertiser"] = prev
            if current_meta:
                ad_meta_list.append(current_meta)

            # 2) _4ik4 _4ik5 div 그룹으로 본문/CTA 분리
            ad_content_list = page.evaluate('''() => {
                const results = [];
                const allDivs = document.querySelectorAll("div._4ik4._4ik5");
                let group = [];

                for (const div of allDivs) {
                    const text = div.innerText.trim();
                    if (text === "광고") {
                        if (group.length > 0) results.push(group);
                        group = [];
                    } else if (text !== "") {
                        group.push(text);
                    }
                }
                if (group.length > 0) results.push(group);
                return results;
            }''')

            # 3) 이미지 URL 추출
            ad_images = page.evaluate('''() => {
                const results = [];
                const seen = new Set();
                const media = document.querySelectorAll("img, video");
                for (const el of media) {
                    let src = el.tagName === "VIDEO" ? (el.poster || "") : (el.src || "");
                    if (!src || seen.has(src)) continue;
                    if ((src.includes("scontent") || src.includes("fbcdn") || src.includes("cdninstagram"))) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 || rect.height > 100) {
                            seen.add(src);
                            results.push(src);
                        }
                    }
                }
                return results;
            }''')

            # 4) CTA 버튼 텍스트 추출
            cta_buttons = page.evaluate('''() => {
                const results = [];
                const btns = document.querySelectorAll("div[class*='x8t9es0'][class*='x1fvot60'][class*='xxio538']");
                for (const btn of btns) {
                    const text = btn.innerText.trim();
                    if (text && text.length < 20 && text.length > 1) {
                        results.push(text);
                    }
                }
                return results;
            }''')

            browser.close()

            # 5) 조합
            for idx in range(min(len(ad_meta_list), max_ads)):
                meta = ad_meta_list[idx]
                content = ad_content_list[idx] if idx < len(ad_content_list) else []

                # content 파싱: [0]=본문, 나머지=랜딩URL/CTA설명
                body_text = content[0] if len(content) > 0 else ""
                landing_url = ""
                cta_desc_parts = []

                for c in content[1:]:
                    if re.match(r"^[A-Z0-9\-\.]+\.(COM|CO\.KR|KR|NET|IO)$", c, re.IGNORECASE):
                        landing_url = c
                    elif c and c != "\u200b" and len(c) > 1:
                        cta_desc_parts.append(c)
                cta_desc = "\n".join(cta_desc_parts)

                # CTA 버튼 필터링
                valid_ctas = ["더 알아보기","지금 구매하기","Shop Now","자세히 알아보기",
                              "지금 쇼핑하기","가입하기","예약하기","다운로드","문의하기",
                              "지금 신청하기","지금 주문하기","더 보기","구매하기"]
                cta_btn = ""
                for c in content[1:]:
                    if c in valid_ctas:
                        cta_btn = c
                        break
                img = ad_images[idx] if idx < len(ad_images) else ""

                ads.append({
                    "library_id": meta["library_id"],
                    "advertiser": meta["advertiser"],
                    "start_date": meta["start_date"],
                    "text": body_text,
                    "cta": cta_btn,
                    "cta_desc": cta_desc,
                    "landing_url": landing_url,
                    "image_url": img,
                    "url": f"https://www.facebook.com/ads/library/?id={meta['library_id']}",
                })

    except Exception as e:
        import sys as _sys
        _sys.stderr.write(f"[meta_crawler] Error: {e}\n")

    return ads


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        kw = sys.argv[1]
        country = sys.argv[2]
        max_n = int(sys.argv[3])
        results = _crawl_internal(kw, country, max_n)
        print(json.dumps(results, ensure_ascii=False))
    else:
        results = crawl_meta_ads("유산균", max_ads=3)
        for ad in results:
            sys.stderr.write(f"광고주: {ad['advertiser']}\n")
            sys.stderr.write(f"본문: {ad['text'][:50]}...\n")
            sys.stderr.write(f"CTA: {ad['cta']} | {ad['cta_desc']}\n\n")
