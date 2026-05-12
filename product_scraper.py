"""상품 페이지 크롤링 → AI 기반 성분/건강기능 표시 자동 추출"""

import re
import json
import subprocess
import sys
import os


def scrape_product_info(url: str) -> dict:
    """서브프로세스에서 Playwright 크롤링 후 AI로 파싱"""
    try:
        result = subprocess.run(
            [sys.executable, __file__, url],
            capture_output=True, timeout=60,
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        if result.returncode == 0 and stdout:
            data = json.loads(stdout)
            if "_error" not in data:
                return data
            return data
        return {"_error": f"rc={result.returncode}, stderr={stderr[:300]}"}
    except Exception as e:
        return {"_error": str(e)}


def _extract_page_text(url: str) -> str:
    """Playwright로 페이지 텍스트 추출"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""

    text = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            # 네이버 스마트스토어: 상세 영역 iframe 처리
            if "smartstore.naver.com" in url or "shopping.naver.com" in url:
                try:
                    # 상세정보 탭 클릭 시도
                    detail_tab = page.query_selector("a[href*='detail'], button:has-text('상세정보')")
                    if detail_tab:
                        detail_tab.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

            # 전체 텍스트 추출 (최대 15000자)
            text = page.inner_text("body")[:15000]
            browser.close()
    except Exception as e:
        text = f"[크롤링 오류: {e}]"

    return text


def _parse_with_ai(page_text: str, url: str) -> dict:
    """Claude AI로 상품 정보 파싱"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _parse_with_regex(page_text)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""다음은 건강기능식품 상품 페이지에서 추출한 텍스트입니다.
이 텍스트에서 아래 정보를 추출해주세요.

URL: {url}

텍스트:
{page_text[:8000]}

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
- ingredients: 기능성 원료만 추출 (부형제/첨가물 제외). 예: 프로바이오틱스, 콘드로이친, 포스파티딜세린
- health_claims: 식약처 인정 건강기능 표시만. 예: 장 건강에 도움, 관절 건강에 도움
- selling_points: 제품 차별화 포인트 (함량, 특허, 제조방식 등)
- 정보를 찾을 수 없으면 빈 배열/빈 문자열로"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        # JSON 부분만 추출
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
    except Exception as e:
        pass

    return _parse_with_regex(page_text)


def _parse_with_regex(page_text: str) -> dict:
    """AI 없이 정규식 기반 간이 파싱 (폴백)"""
    ingredients = []
    claims = []

    # 흔한 기능성 원료 키워드
    ingredient_keywords = [
        "프로바이오틱스", "비피더스", "락토바실러스", "유산균",
        "콘드로이친", "글루코사민", "MSM", "보스웰리아",
        "포스파티딜세린", "오메가3", "루테인", "밀크씨슬",
        "비타민", "아연", "마그네슘", "셀레늄", "칼슘",
        "프리바이오틱스", "식이섬유", "코엔자임Q10",
        "EPA", "DHA", "크릴오일", "감마리놀렌산",
    ]
    for kw in ingredient_keywords:
        if kw.lower() in page_text.lower():
            ingredients.append(kw)

    # 건강기능 표시 패턴
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

        page_text = _extract_page_text(target_url)
        if page_text and not page_text.startswith("[크롤링 오류"):
            result = _parse_with_ai(page_text, target_url)
        else:
            result = {"_error": page_text or "페이지 텍스트 추출 실패"}

        print(json.dumps(result, ensure_ascii=False))
