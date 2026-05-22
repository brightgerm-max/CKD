"""상품 페이지 크롤링 → AI 기반 성분/건강기능 표시 자동 추출"""

import re
import json
import subprocess
import sys
import os
import base64


def scrape_product_info(url: str) -> dict:
    """서브프로세스에서 Playwright 크롤링 후 AI로 파싱 (텍스트 + 스크린샷)"""
    try:
        result = subprocess.run(
            [sys.executable, __file__, url],
            capture_output=True, timeout=90,
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        if result.returncode == 0 and stdout:
            try:
                data = json.loads(stdout)
                return data
            except json.JSONDecodeError:
                return {"_error": f"JSON 파싱 실패: {stdout[:300]}"}
        return {"_error": f"rc={result.returncode}, stderr={stderr[:500]}"}
    except subprocess.TimeoutExpired:
        return {"_error": "타임아웃 (90초 초과)"}
    except Exception as e:
        return {"_error": str(e)}


def analyze_image(image_bytes: bytes) -> dict:
    """이미지 바이트를 Claude Vision으로 분석하여 성분/건강기능 표시 추출"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"_error": "ANTHROPIC_API_KEY 미설정"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        b64 = base64.b64encode(image_bytes).decode()

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": """이 이미지는 건강기능식품의 성분표/상세정보입니다.
이미지에서 아래 정보를 추출해주세요.

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{
  "brand_name": "브랜드명",
  "product_name": "제품명",
  "ingredients": ["기능성 성분1", "성분2", ...],
  "health_claims": ["건강기능 표시1", "표시2", ...],
  "headline": "제품 USP 한 줄 요약",
  "selling_points": ["셀링포인트1", "셀링포인트2", ...]
}

규칙:
- ingredients: 기능성 원료만 (부형제/첨가물 제외). 학명이 있으면 한글명도 함께
- health_claims: 식약처 인정 건강기능 표시
- selling_points: 함량, 특허, 제조방식 등 차별화 포인트
- 정보를 찾을 수 없으면 빈 배열/빈 문자열로"""}
            ]}]
        )

        resp_text = response.content[0].text.strip()
        match = re.search(r'\{[\s\S]*\}', resp_text)
        if match:
            return json.loads(match.group())
        return {"_error": f"AI 응답에서 JSON을 찾을 수 없음: {resp_text[:200]}"}
    except Exception as e:
        return {"_error": f"이미지 분석 실패: {e}"}


def _extract_page_text_and_screenshot(url: str) -> tuple:
    """Playwright로 페이지 텍스트 + 스크린샷 추출. 반환: (text, screenshot_bytes_list)"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "[오류: playwright 미설치]", []

    text = ""
    screenshots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            is_naver = any(d in url for d in ["smartstore.naver.com", "shopping.naver.com", "brand.naver.com"])

            if is_naver:
                # 상세정보 탭 클릭
                try:
                    detail_tab = page.query_selector("a[href*='detail'], button:has-text('상세정보'), a:has-text('상세정보')")
                    if detail_tab:
                        detail_tab.click()
                        page.wait_for_timeout(3000)
                except Exception:
                    pass
                # 스크롤 다운
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 1500)")
                    page.wait_for_timeout(500)

                # iframe 내 텍스트도 추출 시도
                iframe_text = ""
                try:
                    frames = page.frames
                    for frame in frames:
                        if frame != page.main_frame:
                            try:
                                ft = frame.inner_text("body")
                                if len(ft) > len(iframe_text):
                                    iframe_text = ft
                            except Exception:
                                pass
                except Exception:
                    pass

                main_text = page.inner_text("body")[:10000]
                if iframe_text:
                    text = main_text + "\n\n--- iframe ---\n\n" + iframe_text[:8000]
                else:
                    text = main_text

                # 스크린샷 캡처 (상세 영역)
                try:
                    # 상단 스크린샷
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(500)
                    screenshots.append(page.screenshot(type="png"))
                    # 스크롤 내려서 상세 영역 스크린샷
                    page.evaluate("window.scrollBy(0, 900)")
                    page.wait_for_timeout(500)
                    screenshots.append(page.screenshot(type="png"))
                    page.evaluate("window.scrollBy(0, 900)")
                    page.wait_for_timeout(500)
                    screenshots.append(page.screenshot(type="png"))
                except Exception:
                    pass
            else:
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    page.wait_for_timeout(500)
                text = page.inner_text("body")[:15000]
                try:
                    screenshots.append(page.screenshot(type="png"))
                except Exception:
                    pass

            browser.close()
    except Exception as e:
        import traceback
        text = f"[크롤링 오류: {e}\n{traceback.format_exc()[:300]}]"

    return text, screenshots


def _parse_with_ai(page_text: str, url: str, screenshots: list = None) -> dict:
    """Claude AI로 상품 정보 파싱 (텍스트 + 스크린샷 Vision)"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        result = _parse_with_regex(page_text)
        result["_debug"] = "AI키 없음, 정규식 폴백"
        return result

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # 메시지 구성: 텍스트 + 스크린샷 이미지
        content = []

        # 스크린샷 추가 (최대 3장)
        if screenshots:
            for i, ss in enumerate(screenshots[:3]):
                b64 = base64.b64encode(ss).decode()
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64}
                })

        content.append({
            "type": "text",
            "text": f"""다음은 건강기능식품 상품 페이지에서 추출한 텍스트와 스크린샷입니다.
텍스트와 이미지 모두 분석하여 아래 정보를 추출해주세요.
이미지에 성분표, 건강기능 표시, 제품 상세가 있으면 반드시 반영하세요.

URL: {url}

텍스트:
{page_text[:6000]}

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "brand_name": "브랜드명 (제조/판매 회사)",
  "product_name": "제품명",
  "ingredients": ["핵심 기능성 성분1", "성분2", ...],
  "health_claims": ["건강기능 표시1", "표시2", ...],
  "headline": "제품의 핵심 USP 한 줄 요약",
  "selling_points": ["셀링포인트1", "셀링포인트2", ...]
}}

규칙:
- ingredients: 기능성 원료만 추출 (부형제/첨가물 제외). 학명과 한글명 모두 포함
- health_claims: 식약처 인정 건강기능 표시만. 예: 장 건강에 도움, 관절 건강에 도움
- selling_points: 제품 차별화 포인트 (함량, 균수, 특허, 제조방식 등)
- 이미지에서 읽은 정보도 반드시 포함
- 정보를 찾을 수 없으면 빈 배열/빈 문자열로"""
        })

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": content}]
        )

        resp_text = response.content[0].text.strip()
        match = re.search(r'\{[\s\S]*\}', resp_text)
        if match:
            return json.loads(match.group())
        else:
            return {"_error": f"AI 응답에서 JSON을 찾을 수 없음: {resp_text[:200]}"}
    except Exception as e:
        import traceback
        result = _parse_with_regex(page_text)
        result["_debug"] = f"AI 에러({e}), 정규식 폴백"
        return result


def _parse_with_regex(page_text: str) -> dict:
    """AI 없이 정규식 기반 간이 파싱 (폴백)"""
    ingredients = []
    claims = []

    ingredient_keywords = [
        "프로바이오틱스", "비피더스", "락토바실러스", "유산균",
        "콘드로이친", "글루코사민", "MSM", "보스웰리아",
        "포스파티딜세린", "오메가3", "루테인", "밀크씨슬",
        "비타민", "아연", "마그네슘", "셀레늄", "칼슘",
        "프리바이오틱스", "식이섬유", "코엔자임Q10",
        "EPA", "DHA", "크릴오일", "감마리놀렌산",
        "뮤코다당단백", "상어연골",
    ]
    for kw in ingredient_keywords:
        if kw.lower() in page_text.lower():
            ingredients.append(kw)

    claim_patterns = [
        r"[가-힣]+\s*건강에\s*도움",
        r"[가-힣]+\s*개선에\s*도움",
        r"[가-힣]+\s*기능에\s*도움",
        r"항산화에?\s*도움",
        r"면역[력기능\s]*에?\s*도움",
        r"혈행\s*개선에?\s*도움",
        r"체지방\s*감소에?\s*도움",
        r"기억력\s*개선에?\s*도움",
        r"인지[력기능\s]*개선에?\s*도움",
    ]
    for pat in claim_patterns:
        found = re.findall(pat, page_text)
        claims.extend(found)

    return {
        "brand_name": "",
        "product_name": "",
        "ingredients": list(set(ingredients))[:10],
        "health_claims": list(set(claims))[:10],
        "headline": "",
        "selling_points": [],
    }


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        target_url = sys.argv[1]

        # .env 로드 (ANTHROPIC_API_KEY 필요)
        from pathlib import Path
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().strip().split("\n"):
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

        page_text, screenshots = _extract_page_text_and_screenshot(target_url)
        text_len = len(page_text) if page_text else 0
        text_preview = page_text[:200] if page_text else ""

        if page_text and not page_text.startswith("[크롤링 오류") and not page_text.startswith("[오류"):
            result = _parse_with_ai(page_text, target_url, screenshots)
        else:
            result = {"_error": page_text or "페이지 텍스트 추출 실패"}

        result["_text_length"] = text_len
        result["_text_preview"] = text_preview
        result["_screenshots_count"] = len(screenshots)

        print(json.dumps(result, ensure_ascii=False))
