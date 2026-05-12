"""
CKD Insight Radar — 사이드바 내비게이션 대시보드
실행: streamlit run app.py
"""

import os
from pathlib import Path as _P
# .env 파일이 있으면 로드 (로컬 개발용)
_env_path = _P(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import time
import random
import base64
from pathlib import Path

from pubmed_client import search_pubmed, fetch_article_details, INGREDIENT_QUERIES
from matching_engine import load_product_db, match_article_to_products, TARGET_SEGMENTS
from usp_generator import generate_usp_with_ai, generate_usp_template
from naver_client import fetch_search_trend, search_tv_health_news, fetch_multi_keyword_trend
from searchad_client import estimate_search_volume
from mfds_client import search_health_food
from clinicaltrials_client import search_clinical_trials
from price_client import search_product_prices
from competitor_scanner import scan_competitors, compare_ingredients
from ad_reviewer import review_ad_text, ALLOWED_CLAIMS

# ─── 경로 & 데이터 ───
DATA_DIR = Path(__file__).parent / "data"

def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_product_db(data):
    with open(DATA_DIR / "product_ingredient_db.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_competitor_db(data):
    with open(DATA_DIR / "competitor_db.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_products():
    return load_json("product_ingredient_db.json")

def load_competitor_db():
    return load_json("competitor_db.json")

def load_trend_keywords():
    return load_json("trend_keywords.json")

def save_trend_keywords(data):
    with open(DATA_DIR / "trend_keywords.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_tv_data():
    return load_json("sample_tv_data.json")

def load_regulatory_data():
    return load_json("sample_regulatory_data.json")

# ─── 페이지 설정 ───
st.set_page_config(page_title="CKD Insight Radar", page_icon="🔬", layout="wide", initial_sidebar_state="expanded")

# ─── 글로벌 CSS ───
st.markdown("""
<style>
/* ── CSS 변수 ── */
:root {
    --c-primary: #2563eb;
    --c-primary-light: #eff6ff;
    --c-primary-hover: #1d4ed8;
    --c-success: #059669;
    --c-success-light: #ecfdf5;
    --c-warning: #d97706;
    --c-warning-light: #fffbeb;
    --c-danger: #dc2626;
    --c-danger-light: #fef2f2;
    --c-text: #1e293b;
    --c-text-sub: #64748b;
    --c-text-muted: #94a3b8;
    --c-bg: #f1f5f9;
    --c-card: #ffffff;
    --c-border: #e2e8f0;
    --c-border-light: #f1f5f9;
    --radius: 12px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
    --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
    --font-xs: 0.72rem;
    --font-sm: 0.82rem;
    --font-base: 0.92rem;
    --font-lg: 1.1rem;
    --font-xl: 1.5rem;
}

/* ── 전체 ── */
.stApp { background: var(--c-bg); }
.main .block-container { padding-top: 1.5rem; max-width: 1260px; }

/* ── 사이드바 ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0c1929 0%, #142338 50%, #1a2d45 100%);
    min-width: 250px; max-width: 250px;
}
section[data-testid="stSidebar"] * { color: #8ba3bd !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #9ca3af !important;
    text-align: left !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    margin: 1px 0 !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.08) !important;
    color: #ffffff !important;
}
/* 선택된 메뉴: 파란 배경 + 흰 텍스트 */
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
    background: #2563eb !important;
    background-image: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    text-shadow: none !important;
}
.sidebar-brand {
    padding: 20px 16px 6px; display: flex; align-items: center; gap: 10px;
}
.sidebar-brand-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg, #2563eb, #60a5fa);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem;
}
.sidebar-brand-text { font-size: 1.1rem !important; font-weight: 800 !important; color: #ffffff !important; letter-spacing: -0.3px; }
.sidebar-brand-sub  { font-size: 0.65rem !important; color: #4a6580 !important; text-transform: uppercase; letter-spacing: 2px; padding: 0 16px; margin-bottom: 4px; }
.sidebar-hr { border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 3px 16px; }
.sidebar-label { font-size: 0.92rem !important; font-weight: 600 !important; color: #8ba3bd !important; letter-spacing: 0; padding: 4px 16px 2px; cursor: pointer; }
/* 사이드바 expander 스타일 */
section[data-testid="stSidebar"] div[data-testid="stExpander"],
section[data-testid="stSidebar"] div[data-testid="stExpander"] details,
section[data-testid="stSidebar"] div[data-testid="stExpander"] > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    margin-bottom: 0 !important;
    outline: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary {
    color: #c8d6e5 !important;
    font-size: 0.92rem !important;
    font-weight: 700 !important;
    padding: 8px 4px !important;
    background: transparent !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary:hover {
    color: #ffffff !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] svg {
    fill: #5a7a9a !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
    padding: 0 4px 4px !important;
    border-top: none !important;
    background: transparent !important;
}
/* 사이드바 버튼 간격 */
section[data-testid="stSidebar"] .stButton { margin-bottom: -6px !important; }
/* (primary 스타일은 위에서 통합 정의) */
.sidebar-src { display: flex; align-items: center; gap: 8px; padding: 3px 16px; font-size: 0.78rem !important; }
.sidebar-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.sidebar-dot-on  { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.5); }
.sidebar-dot-off { background: #374151; }
.sidebar-ver { padding: 12px 16px; font-size: 0.7rem !important; color: #2d4a63 !important; }

/* ── 페이지 헤더 ── */
.pg-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.pg-icon {
    width: 50px; height: 50px; border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; flex-shrink: 0; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.pg-icon-blue   { background: linear-gradient(135deg,#2563eb,#60a5fa); }
.pg-icon-green  { background: linear-gradient(135deg,#059669,#34d399); }
.pg-icon-purple { background: linear-gradient(135deg,#7c3aed,#a78bfa); }
.pg-icon-orange { background: linear-gradient(135deg,#ea580c,#fb923c); }
.pg-title { font-size: var(--font-xl); font-weight: 800; color: var(--c-text); }
.pg-desc  { font-size: var(--font-sm); color: var(--c-text-sub); margin-top: 2px; }

/* ── 카드 시스템 ── */
.g-card {
    background: var(--c-card); border: 1px solid var(--c-border);
    border-radius: var(--radius); padding: 20px;
    box-shadow: var(--shadow-sm); transition: box-shadow 0.2s;
}
.g-card:hover { box-shadow: var(--shadow-md); }
.g-card-header {
    display: flex; align-items: center; gap: 10px;
    font-size: var(--font-base); font-weight: 700; color: var(--c-text);
    margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--c-border-light);
}
.g-card-badge {
    margin-left: auto; font-size: 0.72rem; font-weight: 700;
    padding: 3px 10px; border-radius: 20px;
}
.g-badge-blue   { background: var(--c-primary-light); color: var(--c-primary); }
.g-badge-green  { background: var(--c-success-light); color: var(--c-success); }
.g-badge-yellow { background: var(--c-warning-light); color: var(--c-warning); }
.g-badge-gray   { background: var(--c-border-light); color: var(--c-text-sub); }

/* ── 상품 카드 ── */
.p-card {
    background: linear-gradient(160deg, #ffffff 0%, #f0f4fa 100%);
    border: 1.5px solid #e2e8f0; border-radius: 16px;
    padding: 22px 14px 18px; text-align: center; cursor: pointer;
    transition: all 0.25s ease; min-height: 110px;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    position: relative; overflow: hidden;
}
.p-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, #cbd5e1, #94a3b8);
    border-radius: 16px 16px 0 0;
}
.p-card:hover { border-color: #93c5fd; box-shadow: var(--shadow-md); transform: translateY(-1px); }
.p-card:hover::before { background: linear-gradient(90deg, #60a5fa, #2563eb); }
.p-card-sel {
    background: linear-gradient(160deg, #eff6ff 0%, #dbeafe 100%);
    border: 2px solid #2563eb; border-radius: 16px;
    padding: 22px 14px 18px; text-align: center; min-height: 110px;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    box-shadow: 0 8px 24px rgba(37,99,235,0.18);
    position: relative; overflow: hidden;
}
.p-card-sel::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, #2563eb, #60a5fa);
    border-radius: 16px 16px 0 0;
}
.p-brand { font-size: 1rem; font-weight: 700; color: #1e293b; margin-bottom: 6px; }
.p-cat {
    font-size: 0.75rem; color: #64748b; background: #e8edf3;
    padding: 3px 12px; border-radius: 20px; display: inline-block; font-weight: 500;
}
.p-card-sel .p-cat { background: rgba(37,99,235,0.12); color: #1d4ed8; }

/* ── 미니 메트릭 ── */
.m-card {
    background: var(--c-card); border: 1px solid var(--c-border);
    border-radius: var(--radius); padding: 18px 14px; text-align: center;
    box-shadow: var(--shadow-sm);
}
.m-val { font-size: var(--font-xl); font-weight: 800; color: var(--c-text); line-height: 1; }
.m-lbl { font-size: var(--font-xs); color: var(--c-text-muted); margin-top: 6px; font-weight: 500; }
.m-val-blue   { color: var(--c-primary); }
.m-val-green  { color: var(--c-success); }
.m-val-orange { color: #ea580c; }

/* ── 데이터 아이템 ── */
.d-item {
    padding: 12px 14px; border-radius: 10px;
    background: var(--c-border-light); margin-bottom: 6px;
    border: 1px solid transparent; border-left: 3px solid var(--c-border);
    transition: all 0.15s;
}
.d-item:hover { background: #e8edf3; border-left-color: var(--c-primary); }
.d-title { font-size: var(--font-sm); font-weight: 600; color: var(--c-text); line-height: 1.4; margin-bottom: 2px; }
.d-meta  { font-size: var(--font-xs); color: var(--c-text-muted); }
.d-link  { font-size: var(--font-xs); color: var(--c-primary); text-decoration: none; font-weight: 500; }
.d-link:hover { text-decoration: underline; }

/* ── 섹션 헤더 ── */
.s-header {
    font-size: var(--font-lg); font-weight: 700; color: var(--c-text);
    padding: 12px 16px; margin: 20px 0 14px;
    border-left: 3px solid var(--c-primary); border-radius: 0 8px 8px 0;
    background: var(--c-primary-light);
}

/* ── USP 카드 ── */
.usp-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px;
    overflow: hidden; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    transition: all 0.2s;
}
.usp-card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.08); }
.usp-head {
    background: linear-gradient(135deg, #1e293b, #334155);
    padding: 14px 20px; display: flex; align-items: center; gap: 10px;
}
.usp-seg  { color: #ffffff; font-size: 0.95rem; font-weight: 700; }
.usp-age  { color: #94a3b8; font-size: 0.78rem; margin-left: auto; }
.usp-body { padding: 18px 20px; background: linear-gradient(160deg, #ffffff 0%, #fafbfd 100%); }
.usp-hl {
    font-size: 1.05rem; font-weight: 700; color: #0f172a; line-height: 1.5;
    padding: 12px 16px; margin-bottom: 10px;
    background: linear-gradient(90deg, #fefce8, #ffffff);
    border-left: 3px solid #eab308; border-radius: 0 10px 10px 0;
}
.usp-sub { font-size: 0.85rem; color: #64748b; margin-bottom: 14px; line-height: 1.5; }
.usp-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.usp-tag {
    font-size: 0.75rem; padding: 4px 12px; border-radius: 20px; font-weight: 600;
}
.usp-t-ch  { background: #eff6ff; color: #2563eb; }
.usp-t-kw  { background: #f0fdf4; color: #15803d; }
.usp-t-tn  { background: #fdf4ff; color: #a21caf; }

/* ── 성분 필 ── */
.ing-pill {
    background: linear-gradient(160deg, #ffffff 0%, #f0f4fa 100%);
    border: 1.5px solid #e2e8f0; border-radius: 14px;
    padding: 14px 10px; text-align: center; cursor: pointer;
    transition: all 0.25s; min-height: 70px;
    position: relative; overflow: hidden;
}
.ing-pill::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #cbd5e1, #94a3b8);
}
.ing-pill:hover { border-color: #93c5fd; box-shadow: var(--shadow-md); transform: translateY(-1px); }
.ing-pill:hover::before { background: linear-gradient(90deg, #60a5fa, #2563eb); }
.ing-pill-sel {
    background: linear-gradient(160deg, #eff6ff 0%, #dbeafe 100%);
    border: 2px solid #2563eb; border-radius: 14px;
    padding: 14px 10px; text-align: center; min-height: 70px;
    color: #1e293b; box-shadow: 0 8px 20px rgba(37,99,235,0.18);
    position: relative; overflow: hidden;
}
.ing-pill-sel::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #2563eb, #60a5fa);
}
.ing-nm { font-size: 0.92rem; font-weight: 700; }
.ing-en { font-size: 0.68rem; opacity: 0.55; margin-top: 2px; }
.ing-ct { font-size: 0.68rem; opacity: 0.45; margin-top: 1px; }

/* ── 경쟁사 테이블 ── */
.ct-wrap { background: linear-gradient(160deg, #ffffff 0%, #f8fafd 100%); border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.ct-row { display: grid; grid-template-columns: 2fr 1.5fr 1fr; padding: 14px 20px; border-bottom: 1px solid #f1f5f9; align-items: center; transition: background 0.15s; }
.ct-row:hover { background: #f8fafc; }
.ct-row:last-child { border-bottom: none; }
.ct-hdr { background: #f8fafc; font-weight: 700; font-size: 0.78rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.ct-hdr:hover { background: #f8fafc; }
.ct-ckd { background: linear-gradient(90deg, #eff6ff, #ffffff); }

/* ── 차별화 ── */
.diff-c {
    background: linear-gradient(90deg, #f0fdf4, #ffffff);
    border: 1px solid #bbf7d0; border-left: 4px solid #22c55e;
    border-radius: 0 14px 14px 0; padding: 14px 20px; margin: 8px 0;
    transition: all 0.15s;
}
.diff-c:hover { box-shadow: 0 4px 12px rgba(34,197,94,0.1); }
.diff-c b { color: #15803d; }

/* ── 요약 패널 ── */
.summary-panel {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #1a2744 100%);
    border-radius: 18px; padding: 28px; color: #ffffff;
    margin-bottom: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.15);
    position: relative; overflow: hidden;
}
.summary-panel::before {
    content: ""; position: absolute; top: -50px; right: -50px;
    width: 200px; height: 200px; border-radius: 50%;
    background: radial-gradient(circle, rgba(37,99,235,0.15) 0%, transparent 70%);
    pointer-events: none;
}
.summary-panel::after {
    content: ""; position: absolute; bottom: -30px; left: -30px;
    width: 140px; height: 140px; border-radius: 50%;
    background: radial-gradient(circle, rgba(96,165,250,0.1) 0%, transparent 70%);
    pointer-events: none;
}
.summary-title { font-size: 1.15rem; font-weight: 700; margin-bottom: 18px; color: #ffffff; }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.summary-item { text-align: center; }
.summary-val { font-size: 1.8rem; font-weight: 800; color: #60a5fa; }
.summary-lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }

/* ── 푸터 ── */
.footer { text-align: center; color: var(--c-text-muted); font-size: var(--font-xs); padding: 30px 0 12px; }

/* ── Streamlit 기본 위젯 보정 ── */
div[data-testid="stExpander"] {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 14px !important; margin-bottom: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
/* ── 메인 영역 버튼만 리스타일 (사이드바 제외) ── */
section[data-testid="stMain"] button[data-testid="stBaseButton-secondary"],
section[data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-secondary"],
.stMainBlockContainer button[kind="secondary"] {
    background: #e8edf3 !important;
    background-image: linear-gradient(180deg, #eef1f6 0%, #dde3ec 100%) !important;
    border: 1.5px solid #c1c9d6 !important;
    border-radius: 8px !important;
    color: #334155 !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    padding: 6px 14px !important;
    min-height: 34px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.6) !important;
    transition: all 0.15s ease !important;
    cursor: pointer !important;
}
section[data-testid="stMain"] button[data-testid="stBaseButton-secondary"]:hover,
section[data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-secondary"]:hover {
    background-image: linear-gradient(180deg, #e2e7ef 0%, #cdd4df 100%) !important;
    border-color: #94a3b8 !important;
    color: #0f172a !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.5) !important;
    transform: translateY(-1px) !important;
}
section[data-testid="stMain"] button[data-testid="stBaseButton-secondary"]:active,
section[data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-secondary"]:active {
    transform: translateY(0px) !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.1) !important;
    background-image: linear-gradient(180deg, #d0d7e2 0%, #c1c9d6 100%) !important;
}
section[data-testid="stMain"] button[data-testid="stBaseButton-primary"],
section[data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"],
.stMainBlockContainer button[kind="primary"] {
    background: #2563eb !important;
    background-image: linear-gradient(180deg, #3b82f6 0%, #1d4ed8 100%) !important;
    border: 1.5px solid #1e40af !important;
    border-radius: 8px !important;
    color: #ffffff !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    padding: 6px 14px !important;
    min-height: 34px !important;
    box-shadow: 0 3px 10px rgba(37,99,235,0.35), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    transition: all 0.15s ease !important;
    cursor: pointer !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
}
section[data-testid="stMain"] button[data-testid="stBaseButton-primary"]:hover,
section[data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"]:hover {
    background-image: linear-gradient(180deg, #60a5fa 0%, #2563eb 100%) !important;
    box-shadow: 0 6px 18px rgba(37,99,235,0.45), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    transform: translateY(-1px) !important;
}
section[data-testid="stMain"] button[data-testid="stBaseButton-primary"]:active,
section[data-testid="stMainBlockContainer"] button[data-testid="stBaseButton-primary"]:active {
    transform: translateY(0px) !important;
    background-image: linear-gradient(180deg, #1d4ed8 0%, #1e3a8a 100%) !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.2) !important;
}
/* link_button (메인 영역만) */
section[data-testid="stMain"] [data-testid="stLinkButton"] a,
section[data-testid="stMainBlockContainer"] [data-testid="stLinkButton"] a {
    background: #e8edf3 !important;
    background-image: linear-gradient(180deg, #eef1f6 0%, #dde3ec 100%) !important;
    border: 1.5px solid #c1c9d6 !important;
    border-radius: 8px !important;
    color: #2563eb !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    padding: 6px 14px !important;
    min-height: 34px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.6) !important;
    transition: all 0.15s ease !important;
    text-decoration: none !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
}
section[data-testid="stMain"] [data-testid="stLinkButton"] a:hover,
section[data-testid="stMainBlockContainer"] [data-testid="stLinkButton"] a:hover {
    background-image: linear-gradient(180deg, #dbeafe 0%, #bfdbfe 100%) !important;
    border-color: #60a5fa !important;
    color: #1d4ed8 !important;
    box-shadow: 0 4px 10px rgba(37,99,235,0.15) !important;
    transform: translateY(-1px) !important;
}
/* text_area 스타일 */
textarea[type="textarea"] {
    background: #ffffff !important;
    border: 1.5px solid var(--c-border) !important;
    border-radius: 10px !important;
}
textarea[type="textarea"]:focus,
textarea[type="textarea"]:active,
textarea[type="textarea"]:focus-visible {
    border: 1.5px solid var(--c-border) !important;
}
/* container 내 AI 응답 텍스트 크기 제한 */
div[data-testid="stVerticalBlockBorderWrapper"] h1 { font-size: var(--font-lg) !important; }
div[data-testid="stVerticalBlockBorderWrapper"] h2 { font-size: var(--font-base) !important; }
div[data-testid="stVerticalBlockBorderWrapper"] h3 { font-size: var(--font-sm) !important; }
div[data-testid="stVerticalBlockBorderWrapper"] p,
div[data-testid="stVerticalBlockBorderWrapper"] li { font-size: var(--font-sm) !important; line-height: 1.7 !important; }
/* date_input 스타일 */
.stDateInput > div > div {
    border-radius: 10px !important;
    background: linear-gradient(160deg, #ffffff 0%, #f0f4fa 100%) !important;
    border: 1.5px solid #e2e8f0 !important;
}
.stDateInput > div > div:hover {
    border-color: #93c5fd !important;
}
/* 차트 컨테이너 카드 스타일 */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
}
.chart-card {
    background: linear-gradient(160deg, #ffffff 0%, #f8fafd 100%);
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.stSelectbox > div > div {
    border-radius: 10px !important;
    background: linear-gradient(160deg, #ffffff 0%, #f0f4fa 100%) !important;
    border: 1.5px solid #e2e8f0 !important;
}
.stSelectbox > div > div:hover {
    border-color: #93c5fd !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.1) !important;
}
</style>
""", unsafe_allow_html=True)

# ─── 사이드바 ───
MENU_SECTIONS = [
    {"section": "🛡️ 광고심의", "items": [
        {"key": "ai_review",        "label": "AI 사전검토"},
        {"key": "review_dashboard", "label": "심의현황 대시보드"},
    ]},
    {"section": "📈 EASY 리포팅", "items": [
        {"key": "creative_report",  "label": "소재 실적관리"},
        {"key": "label_report",     "label": "라벨링 리포트"},
    ]},
    {"section": "🔍 시장조사", "items": [
        {"key": "search_query",     "label": "검색쿼리 분석"},
        {"key": "ad_research",      "label": "광고배너 조사"},
        {"key": "competitor",       "label": "경쟁사 모니터링"},
    ]},
    {"section": "⚙️ 설정", "items": [
        {"key": "products",         "label": "자사 상품관리"},
        {"key": "api_keys",         "label": "API 키 관리"},
        {"key": "competitor_db",    "label": "경쟁사 DB 관리"},
        {"key": "keyword_mgmt",     "label": "검색 키워드 관리"},
        {"key": "account",          "label": "계정 설정"},
    ]},
]

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "search_query"

LOGO_PATH = Path(__file__).parent / "LOGO.webp"
with open(LOGO_PATH, "rb") as _f:
    _logo_b64 = base64.b64encode(_f.read()).decode()

with st.sidebar:
    st.markdown(
        f'<div style="text-align:center; padding:20px 16px 8px">'
        f'<img src="data:image/webp;base64,{_logo_b64}" '
        f'style="width:100px; height:100px; border-radius:50%; '
        f'border:2px solid rgba(255,255,255,0.15); '
        f'box-shadow:0 4px 16px rgba(0,0,0,0.3)">'
        f'</div>'
        f'<div style="text-align:center; padding:6px 16px 0">'
        f'<div class="sidebar-brand-text" style="text-align:center">CKD Insight Radar</div>'
        f'</div>'
        f'<div class="sidebar-brand-sub" style="text-align:center">종근당건강 · Trend Marketing Platform</div>'
        f'<div style="height:24px"></div>',
        unsafe_allow_html=True,
    )

    for section in MENU_SECTIONS:
        # 현재 선택된 메뉴가 이 섹션에 있으면 자동 펼침
        section_keys = [item["key"] for item in section["items"]]
        is_section_active = st.session_state.get("current_page", "") in section_keys

        with st.expander(section["section"], expanded=is_section_active):
            for item in section["items"]:
                is_active = st.session_state["current_page"] == item["key"]
                if st.button(item["label"], key=f"nav_{item['key']}", use_container_width=True,
                             type="primary" if is_active else "secondary"):
                    if not is_active:
                        st.session_state["current_page"] = item["key"]
                        st.rerun()

    st.markdown(
        '<hr class="sidebar-hr"><div class="sidebar-label">모니터링 소스</div>',
        unsafe_allow_html=True,
    )
    for name, on in [("PubMed",True),("ClinicalTrials.gov",True),("식약처 공지",True),("TV 건강 프로그램",True),("네이버 데이터랩",True)]:
        dot = "sidebar-dot sidebar-dot-on" if on else "sidebar-dot sidebar-dot-off"
        st.markdown(f'<div class="sidebar-src"><span class="{dot}"></span> {name}</div>', unsafe_allow_html=True)

    st.markdown('<hr class="sidebar-hr"><div class="sidebar-ver">v2.0 — 종근당건강 제안용</div>', unsafe_allow_html=True)

# ─── 유틸리티 ───
def render_page_header(icon, title, desc, color="blue"):
    st.markdown(
        f'<div class="pg-header">'
        f'<div class="pg-icon pg-icon-{color}">{icon}</div>'
        f'<div><div class="pg-title">{title}</div><div class="pg-desc">{desc}</div></div>'
        f'</div>', unsafe_allow_html=True)

def extract_all_ingredients(products_data):
    ingredients, seen = [], set()
    for p in products_data["products"]:
        kr = p.get("ingredient_keywords_kr",[])
        en = p.get("ingredient_keywords_en",[])
        main_kr = kr[0] if kr else p["brand"]
        if main_kr not in seen:
            seen.add(main_kr)
            ingredients.append({"name_kr": main_kr, "name_en": en[0] if en else "", "category": p.get("category",""),
                                "brand": p["brand"], "keywords_en": en, "keywords_kr": kr})
    return ingredients

def find_query_for_ingredient(info):
    for qk, qv in INGREDIENT_QUERIES.items():
        for kw in info["keywords_kr"]:
            if kw in qk: return qv
        for kw in info["keywords_en"]:
            if kw.lower() in qk.lower(): return qv
    terms = " OR ".join(f'"{kw}"[tiab]' for kw in info["keywords_en"][:3])
    return f'({terms}) AND "supplement"[tiab]'

def get_tv_data_for_ingredient(tv, info):
    results, kws = [], [k.lower() for k in info["keywords_kr"]]
    for prog in tv.get("tv_programs",[]):
        for ep in prog.get("episodes",[]):
            ep_ings = [i.lower() for i in ep.get("ingredients",[])]
            if any(kw in ing for kw in kws for ing in ep_ings):
                results.append({"program":prog["program"],"channel":prog["channel"],"date":ep["date"],"title":ep["title"],"summary":ep["summary"]})
    return results

def get_regulatory_data_for_ingredient(reg, info):
    results, kws = [], [k.lower() for k in info["keywords_kr"]]
    for n in reg.get("regulatory_notices",[]):
        n_ings = [i.lower() for i in n.get("ingredients",[])]
        if "전체" in n.get("ingredients",[]) or any(kw in ing for kw in kws for ing in n_ings):
            results.append(n)
    return results

def generate_trend_data(name):
    months = [f"2025-{m:02d}" for m in range(5,13)] + [f"2026-{m:02d}" for m in range(1,5)]
    random.seed(hash(name)%1000)
    base = random.randint(40,70)
    naver = [base+random.randint(-10,20)+i*2 for i in range(12)]
    google = [int(v*0.7)+random.randint(-5,10) for v in naver]
    return pd.DataFrame({"월":months,"네이버":naver,"구글":google})

def build_product_query(product):
    en, kr = product.get("ingredient_keywords_en",[]), product.get("ingredient_keywords_kr",[])
    for qk in INGREDIENT_QUERIES:
        for kw in kr:
            if kw in qk: return INGREDIENT_QUERIES[qk]
    terms = " OR ".join(f'"{kw}"[tiab]' for kw in en[:3])
    return f'({terms}) AND "supplement"[tiab]'

# ═══════════════════════════════════════════
# 페이지 1: 자사 상품관리
# ═══════════════════════════════════════════
def page_product_management():
    products_data = load_products()
    products = products_data["products"]

    col_h, col_btn = st.columns([5, 1])
    with col_h:
        render_page_header("📦","자사 상품관리","종근당건강 제품 라인업을 등록·관리합니다","blue")
    with col_btn:
        st.markdown("")
        if st.button("＋ 상품 추가", type="primary", use_container_width=True):
            st.session_state["mgmt_add_mode"] = True

    # 상품 추가 폼
    if st.session_state.get("mgmt_add_mode"):
        with st.expander("새 상품 등록", expanded=True):
            with st.form("add_product_form"):
                c1, c2 = st.columns(2)
                with c1:
                    new_brand = st.text_input("브랜드명 *")
                    new_category = st.text_input("카테고리 *")
                    new_target = st.text_input("타겟 (예: 30-50대)")
                with c2:
                    new_ingredients = st.text_area("핵심 성분 (쉼표 구분)")
                    new_kr_keywords = st.text_area("한글 키워드 (쉼표 구분)")
                    new_en_keywords = st.text_area("영문 키워드 (쉼표 구분)")
                new_claims = st.text_input("건강기능 표시 (쉼표 구분)")
                new_url = st.text_input("상품몰 URL")
                if st.form_submit_button("등록", type="primary"):
                    if new_brand and new_category:
                        products_data["products"].append({
                            "brand": new_brand, "category": new_category,
                            "ingredients": [x.strip() for x in new_ingredients.split(",") if x.strip()],
                            "ingredient_keywords_kr": [x.strip() for x in new_kr_keywords.split(",") if x.strip()],
                            "ingredient_keywords_en": [x.strip() for x in new_en_keywords.split(",") if x.strip()],
                            "health_claims": [x.strip() for x in new_claims.split(",") if x.strip()],
                            "target_demographic": {"gender":"all","primary_age":new_target},
                            "sub_products": [new_brand], "product_url": new_url,
                        })
                        save_product_db(products_data)
                        st.session_state.pop("mgmt_add_mode", None)
                        st.rerun()

    # ── 상단: 선택된 상품 상세 or 전체 요약 ──
    selected_idx = st.session_state.get("mgmt_selected")

    if selected_idx is not None and selected_idx < len(products):
        p = products[selected_idx]
        target = p.get("target_demographic",{})
        ingredients_html = "".join(f'<span style="display:inline-block;background:#eff6ff;color:#2563eb;padding:4px 12px;border-radius:20px;font-size:0.82rem;font-weight:500;margin:3px 4px">{ing}</span>' for ing in p.get("ingredients",[]))
        claims_html = "".join(f'<span style="display:inline-block;background:#f0fdf4;color:#059669;padding:4px 12px;border-radius:20px;font-size:0.82rem;font-weight:500;margin:3px 4px">{c}</span>' for c in p.get("health_claims",[]))
        subs_html = "".join(f'<span style="display:inline-block;background:#f5f3ff;color:#7c3aed;padding:4px 12px;border-radius:20px;font-size:0.82rem;font-weight:500;margin:3px 4px">{s}</span>' for s in p.get("sub_products",[]))
        url = p.get("product_url","")
        url_html = f'<a href="{url}" target="_blank" style="color:#2563eb;text-decoration:none;font-weight:500;font-size:0.85rem">🔗 상품몰 바로가기 →</a>' if url else ""

        st.markdown(f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:18px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); margin-bottom:20px">
            <div style="background:linear-gradient(135deg,#1e293b,#334155); padding:18px 24px; display:flex; align-items:center; justify-content:space-between">
                <div>
                    <span style="color:#ffffff; font-size:1.2rem; font-weight:800">{p["brand"]}</span>
                    <span style="background:rgba(255,255,255,0.15); color:#94a3b8; padding:3px 12px; border-radius:20px; font-size:0.78rem; margin-left:10px">{p["category"]}</span>
                </div>
                <div style="color:#94a3b8; font-size:0.85rem">타겟: <b style="color:#60a5fa">{target.get("primary_age","N/A")}</b></div>
            </div>
            <div style="padding:22px 24px">
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px">
                    <div>
                        <div style="font-size:0.75rem; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px">핵심 성분</div>
                        <div>{ingredients_html}</div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px">건강기능 표시</div>
                        <div>{claims_html}</div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px">서브 제품</div>
                        <div>{subs_html}</div>
                    </div>
                </div>
                <div style="margin-top:16px; padding-top:14px; border-top:1px solid #f1f5f9; display:flex; align-items:center; justify-content:space-between">
                    {url_html}
                    <div></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        e1, e2, _ = st.columns([1,1,8])
        with e1:
            if st.button("✏️ 수정", key=f"edit_{selected_idx}"):
                st.session_state["mgmt_edit_mode"] = selected_idx
        with e2:
            if st.button("🗑️ 삭제", key=f"delete_{selected_idx}"):
                st.session_state["mgmt_delete_confirm"] = selected_idx

        if st.session_state.get("mgmt_delete_confirm") == selected_idx:
            st.warning(f"'{p['brand']}' 상품을 정말 삭제하시겠습니까?")
            dc1, dc2, _ = st.columns([1,1,8])
            with dc1:
                if st.button("삭제 확인", type="primary"):
                    products_data["products"].pop(selected_idx)
                    save_product_db(products_data)
                    st.session_state.pop("mgmt_selected",None)
                    st.session_state.pop("mgmt_delete_confirm",None)
                    st.rerun()
            with dc2:
                if st.button("취소"):
                    st.session_state.pop("mgmt_delete_confirm",None)
                    st.rerun()

        if st.session_state.get("mgmt_edit_mode") == selected_idx:
            with st.form(f"edit_form_{selected_idx}"):
                c1, c2 = st.columns(2)
                with c1:
                    edit_brand = st.text_input("브랜드명", value=p["brand"])
                    edit_category = st.text_input("카테고리", value=p["category"])
                    edit_target = st.text_input("타겟", value=p.get("target_demographic",{}).get("primary_age",""))
                with c2:
                    edit_ingredients = st.text_area("핵심 성분", value=", ".join(p.get("ingredients",[])))
                    edit_claims = st.text_area("건강기능 표시", value=", ".join(p.get("health_claims",[])))
                edit_url = st.text_input("상품몰 URL", value=p.get("product_url",""))
                if st.form_submit_button("저장", type="primary"):
                    p["brand"]=edit_brand; p["category"]=edit_category
                    p["target_demographic"]["primary_age"]=edit_target
                    p["ingredients"]=[x.strip() for x in edit_ingredients.split(",") if x.strip()]
                    p["health_claims"]=[x.strip() for x in edit_claims.split(",") if x.strip()]
                    p["product_url"]=edit_url
                    save_product_db(products_data)
                    st.session_state.pop("mgmt_edit_mode",None)
                    st.rerun()
    else:
        # 전체 요약 패널
        cats = {}
        for p in products:
            cats[p["category"]] = cats.get(p["category"],0)+1
        total_ingredients = sum(len(p.get("ingredients",[])) for p in products)

        st.markdown(
            f'<div class="summary-panel">'
            f'<div class="summary-title">종근당건강 제품 라인업 요약</div>'
            f'<div class="summary-grid">'
            f'<div class="summary-item"><div class="summary-val">{len(products)}</div><div class="summary-lbl">등록 상품</div></div>'
            f'<div class="summary-item"><div class="summary-val">{len(cats)}</div><div class="summary-lbl">건강 카테고리</div></div>'
            f'<div class="summary-item"><div class="summary-val">{total_ingredients}</div><div class="summary-lbl">관리 성분</div></div>'
            f'<div class="summary-item"><div class="summary-val">{sum(len(p.get("sub_products",[])) for p in products)}</div><div class="summary-lbl">서브 제품</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(f'<div class="s-header">전체 상품 ({len(products)})</div>', unsafe_allow_html=True)

    # ── 상품 카드 그리드 ──
    cols_per_row = 4
    for row_start in range(0, len(products), cols_per_row):
        cols = st.columns(cols_per_row)
        for i, col in enumerate(cols):
            idx = row_start + i
            if idx >= len(products): break
            p = products[idx]
            with col:
                is_sel = st.session_state.get("mgmt_selected") == idx
                css = "p-card-sel" if is_sel else "p-card"
                st.markdown(
                    f'<div class="{css}">'
                    f'<div class="p-brand">{p["brand"]}</div>'
                    f'<div class="p-cat">{p["category"]}</div>'
                    f'</div>', unsafe_allow_html=True,
                )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("상세 보기" if not is_sel else "✓ 선택됨", key=f"detail_{idx}", use_container_width=True,
                                 type="primary" if is_sel else "secondary"):
                        st.session_state["mgmt_selected"] = idx
                        st.rerun()
                with b2:
                    url = p.get("product_url","")
                    if url:
                        st.link_button("몰이동 >", url, use_container_width=True)
                    else:
                        st.button("—", key=f"mall_{idx}", disabled=True, use_container_width=True)


# ═══════════════════════════════════════════
# 페이지 2: 데이터 수집
# ═══════════════════════════════════════════
def page_data_collection():
    hdr_col, period_col = st.columns([4, 1.5])
    with hdr_col:
        render_page_header("📡","데이터 수집","성분별 PubMed 논문 · TV 방송 · 식약처 · 검색 트렌드를 한눈에 조회합니다","green")
    with period_col:
        st.markdown("")
        period_map = {"최근 1개월":30,"최근 3개월":90,"최근 6개월":180,"최근 1년":365,"최근 2년":730,"최근 5년":1825}
        period_label = st.selectbox("📅 검색 기간", list(period_map.keys()), index=3)
        days_back = period_map[period_label]

    products_data = load_products()
    all_ingredients = extract_all_ingredients(products_data)
    tv_data = load_tv_data()
    reg_data = load_regulatory_data()

    # 성분 선택
    st.markdown('<div class="s-header">성분 선택</div>', unsafe_allow_html=True)
    n_cols = min(len(all_ingredients), 7)
    ing_cols = st.columns(n_cols)
    for i, ing in enumerate(all_ingredients):
        with ing_cols[i % n_cols]:
            is_sel = st.session_state.get("dc_ingredient") == i
            pill = "ing-pill-sel" if is_sel else "ing-pill"
            st.markdown(
                f'<div class="{pill}">'
                f'<div class="ing-nm">{ing["name_kr"]}</div>'
                f'<div class="ing-en">{ing["name_en"]}</div>'
                f'<div class="ing-ct">{ing["category"]}</div>'
                f'</div>', unsafe_allow_html=True,
            )
            if st.button("✓" if is_sel else "선택", key=f"ing_btn_{i}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state["dc_ingredient"] = i
                st.rerun()

    if st.session_state.get("dc_ingredient") is None:
        st.info("분석할 성분을 선택하세요.")
        return

    sel_ing = all_ingredients[st.session_state["dc_ingredient"]]

    # 통합 캐시키 (성분 + 기간)
    dc_key = f"dc_{sel_ing['name_kr']}_{days_back}"
    query = find_query_for_ingredient(sel_ing)

    if dc_key not in st.session_state:
        _, btn_col, _ = st.columns([2, 2, 2])
        with btn_col:
            if st.button(f"🔍 \"{sel_ing['name_kr']}\" 데이터 수집 실행", key="search_all_btn", type="primary", use_container_width=True):
                with st.spinner("PubMed + 임상시험 + TV 뉴스 + 식약처 + 트렌드 데이터를 수집하고 있습니다..."):
                    collected = {}
                    # 1) PubMed
                    try:
                        pmids = search_pubmed(query, max_results=15, days_back=days_back)
                        time.sleep(0.4)
                        collected["pubmed"] = fetch_article_details(pmids)
                    except Exception:
                        collected["pubmed"] = []
                    # 2) ClinicalTrials.gov
                    try:
                        en_kws = sel_ing["keywords_en"][:2]
                        ct_query = " ".join(en_kws) + " supplement"
                        collected["clinical"] = search_clinical_trials(ct_query, max_results=8)
                    except Exception:
                        collected["clinical"] = []
                    # 3) TV·건강 뉴스
                    try:
                        news = search_tv_health_news(sel_ing["name_kr"], display=5)
                        if news:
                            collected["tv"] = {"source": "api", "data": news}
                        else:
                            collected["tv"] = {"source": "sample", "data": get_tv_data_for_ingredient(tv_data, sel_ing)}
                    except Exception:
                        collected["tv"] = {"source": "sample", "data": get_tv_data_for_ingredient(tv_data, sel_ing)}
                    # 4) 식약처
                    try:
                        mfds_results = []
                        for kw in sel_ing["keywords_en"][:2] + sel_ing["keywords_kr"][:1]:
                            found = search_health_food(kw, max_results=5)
                            for item in found:
                                if not any(r["report_no"] == item["report_no"] for r in mfds_results):
                                    mfds_results.append(item)
                                if len(mfds_results) >= 5:
                                    break
                            if len(mfds_results) >= 5:
                                break
                        collected["mfds"] = mfds_results
                    except Exception:
                        collected["mfds"] = []
                    # 5) 검색 트렌드
                    try:
                        trend_data = fetch_search_trend(sel_ing["keywords_kr"][:3], months_back=max(days_back//30, 6))
                        collected["trend"] = {"source": "api", "data": trend_data} if trend_data else {"source": "sample", "data": None}
                    except Exception:
                        collected["trend"] = {"source": "sample", "data": None}

                    st.session_state[dc_key] = collected
                    st.rerun()
        return

    dc = st.session_state[dc_key]
    st.markdown(f'<div class="s-header">🔎 "{sel_ing["name_kr"]}" 수집 데이터</div>', unsafe_allow_html=True)

    # ── Row 1: PubMed + ClinicalTrials ──
    col_l, col_r = st.columns(2)

    with col_l:
        articles = dc.get("pubmed", [])
        badge = f'<span class="g-card-badge g-badge-blue">{len(articles)}건</span>'
        st.markdown(f'<div class="g-card"><div class="g-card-header">📰 PubMed 논문 {badge}</div>', unsafe_allow_html=True)
        for a in articles[:8]:
            st.markdown(
                f'<div class="d-item">'
                f'<div class="d-title">{a["title"][:90]}</div>'
                f'<div class="d-meta">{a.get("journal","N/A")} · {a.get("pub_date","")}'
                f' · <a href="{a.get("url","#")}" target="_blank" class="d-link">원문 →</a></div>'
                f'</div>', unsafe_allow_html=True)
        if not articles:
            st.caption("관련 논문 없음")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r:
        trials = dc.get("clinical", [])
        badge = f'<span class="g-card-badge g-badge-blue">{len(trials)}건</span>' if trials else ""
        st.markdown(f'<div class="g-card"><div class="g-card-header">🏥 ClinicalTrials.gov {badge}</div>', unsafe_allow_html=True)
        if trials:
            for t in trials[:6]:
                status_color = {"RECRUITING":"#059669","COMPLETED":"#2563eb","ACTIVE_NOT_RECRUITING":"#d97706"}.get(t["status"],"#64748b")
                st.markdown(
                    f'<div class="d-item">'
                    f'<div class="d-title">{t["title"][:90]}</div>'
                    f'<div class="d-meta"><span style="color:{status_color};font-weight:600">{t["status"]}</span>'
                    f' · Phase {t["phase"]} · {t.get("start_date","")}'
                    f' · <a href="{t["url"]}" target="_blank" class="d-link">원문 →</a></div>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.caption("관련 임상시험 없음")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Row 2: TV 뉴스 + 식약처 ──
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        tv_cached = dc.get("tv", {})
        tv_source = tv_cached.get("source", "sample")
        tv_items = tv_cached.get("data", [])
        source_label = "" if tv_source == "api" else ' <span class="g-card-badge g-badge-gray">샘플</span>'
        badge = f'<span class="g-card-badge g-badge-green">{len(tv_items)}건</span>' if tv_items else ""
        st.markdown(f'<div class="g-card"><div class="g-card-header">📺 TV·건강 뉴스 {badge}{source_label}</div>', unsafe_allow_html=True)
        if tv_items and tv_source == "api":
            for item in tv_items:
                st.markdown(
                    f'<div class="d-item">'
                    f'<div class="d-title">{item["title"]}</div>'
                    f'<div class="d-meta">{item.get("pubDate","")}'
                    f' · <a href="{item["link"]}" target="_blank" class="d-link">원문 →</a></div>'
                    f'<div style="font-size:0.8rem;color:#64748b;margin-top:4px">{item.get("description","")[:120]}</div>'
                    f'</div>', unsafe_allow_html=True)
        elif tv_items:
            for tv in tv_items:
                st.markdown(
                    f'<div class="d-item">'
                    f'<div class="d-title">{tv["title"]}</div>'
                    f'<div class="d-meta">{tv["program"]} ({tv["channel"]}) · {tv["date"]}</div>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.caption("관련 뉴스 없음")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r2:
        mfds_items = dc.get("mfds", [])
        badge = f'<span class="g-card-badge g-badge-yellow">{len(mfds_items)}건</span>' if mfds_items else ""
        st.markdown(f'<div class="g-card"><div class="g-card-header">🏛️ 식약처 기능성 인정 현황 {badge}</div>', unsafe_allow_html=True)
        if mfds_items:
            for item in mfds_items[:5]:
                fnclty = item["functionality"].replace("\r\n"," ").replace("\n"," ")[:100]
                st.markdown(
                    f'<div class="d-item">'
                    f'<div class="d-title">{item["name"]}</div>'
                    f'<div class="d-meta">{item["company"]} · 인정일 {item["approval_date"][:4]}.{item["approval_date"][4:6]}'
                    f' · <a href="{item["url"]}" target="_blank" class="d-link">원문 →</a></div>'
                    f'<div style="font-size:0.8rem;color:#64748b;margin-top:4px">기능성: {fnclty}...</div>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.caption("관련 식약처 데이터 없음")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Row 3: 검색 트렌드 (풀 폭) ──
    trend_cached = dc.get("trend", {})
    source_label = "" if trend_cached.get("source") == "api" else ' <span class="g-card-badge g-badge-gray">샘플</span>'
    st.markdown(f'<div class="g-card"><div class="g-card-header">📈 검색 트렌드 (네이버){source_label}</div>', unsafe_allow_html=True)
    if trend_cached.get("source") == "api" and trend_cached.get("data"):
        td = trend_cached["data"]
        trend_df = pd.DataFrame(td)
        trend_df.columns = ["월", "검색량"]
        trend_df["월"] = trend_df["월"].str[:7]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=trend_df["월"],y=trend_df["검색량"],name="네이버 검색량",line=dict(color="#03c75a",width=2.5),fill="tozeroy",fillcolor="rgba(3,199,90,0.06)"))
        fig.update_layout(height=260,margin=dict(t=10,b=20,l=20,r=20),legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",yaxis=dict(gridcolor="#f1f5f9",title="상대 검색량"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        trend_df = generate_trend_data(sel_ing["name_kr"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=trend_df["월"],y=trend_df["네이버"],name="네이버",line=dict(color="#03c75a",width=2.5),fill="tozeroy",fillcolor="rgba(3,199,90,0.06)"))
        fig.add_trace(go.Scatter(x=trend_df["월"],y=trend_df["구글"],name="구글",line=dict(color="#4285f4",width=2.5),fill="tozeroy",fillcolor="rgba(66,133,244,0.06)"))
        fig.update_layout(height=260,margin=dict(t=10,b=20,l=20,r=20),legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",yaxis=dict(gridcolor="#f1f5f9"))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── AI 인사이트 요약 ──
    st.markdown(f'<div class="s-header">🤖 "{sel_ing["name_kr"]}" 수집 데이터 AI 인사이트</div>', unsafe_allow_html=True)

    ai_cache_key = f"ai_summary_{sel_ing['name_kr']}"

    # 요약 데이터 준비
    def _build_summary_prompt():
        parts = []
        # 논문
        articles = dc.get("pubmed", [])
        if articles:
            parts.append("## PubMed 논문")
            for a in articles[:5]:
                parts.append(f"- {a['title']} ({a.get('journal','')}, {a.get('pub_date','')})")
        # 임상시험
        trials = dc.get("clinical", [])
        if trials:
            parts.append("\n## 임상시험 (ClinicalTrials.gov)")
            for t in trials[:5]:
                parts.append(f"- [{t['status']}] {t['title']} (Phase {t['phase']})")
        # 뉴스
        tv_cached = dc.get("tv", {})
        tv_items = tv_cached.get("data", []) if tv_cached else []
        if tv_items and tv_cached.get("source") == "api":
            parts.append("\n## TV·건강 뉴스")
            for n in tv_items[:5]:
                parts.append(f"- {n['title']}")
        # 식약처
        mfds_items = dc.get("mfds", [])
        if mfds_items:
            parts.append("\n## 식약처 기능성 인정 현황")
            for m in mfds_items[:5]:
                parts.append(f"- {m['name']} ({m['company']}): {m['functionality'][:80]}")
        return "\n".join(parts)

    if ai_cache_key in st.session_state:
        st.markdown(
            f'<div class="g-card">'
            f'<div class="g-card-header">🧠 AI 분석 결과 <span class="g-card-badge g-badge-blue">Claude</span></div>'
            f'<div style="font-size:0.9rem; line-height:1.7; color:#1e293b">{st.session_state[ai_cache_key]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        _, btn_col, _ = st.columns([2, 2, 2])
        with btn_col:
            if st.button("🤖 AI 인사이트 분석 실행", key="ai_summary_btn", type="primary", use_container_width=True):
                summary_text = _build_summary_prompt()
                if not summary_text.strip():
                    st.warning("분석할 데이터가 없습니다.")
                else:
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                        with st.spinner("AI가 수집 데이터를 분석하고 있습니다..."):
                            msg = client.messages.create(
                                model="claude-haiku-4-5-20251001",
                                max_tokens=1000,
                                messages=[{"role": "user", "content": f"""당신은 건강기능식품 마케팅 전문 분석가입니다. 아래 "{sel_ing['name_kr']}" 성분에 대해 수집된 데이터를 분석하고, 마케팅 관점에서 핵심 인사이트를 요약해주세요.

{summary_text}

다음 항목으로 정리해주세요:
1. **논문 트렌드 요약** (최신 연구 동향 2-3줄)
2. **미디어 동향** (TV/뉴스에서 어떻게 다뤄지고 있는지 1-2줄)
3. **규제 현황** (식약처 인정 현황 1-2줄)
4. **마케팅 활용 포인트** (이 데이터로 활용 가능한 마케팅 메시지 2-3개)

한국어로 간결하게 작성해주세요. 식약처 광고 심의 기준을 준수하여 "치료", "완치" 등의 표현은 피해주세요."""}]
                            )
                            result = msg.content[0].text
                            st.session_state[ai_cache_key] = result
                            st.rerun()
                    except Exception as e:
                        err_msg = str(e)
                        if "credit balance" in err_msg.lower():
                            st.warning("Anthropic API 크레딧이 부족합니다. 콘솔에서 크레딧을 충전해주세요.")
                        else:
                            st.error(f"AI 분석 실패: {err_msg}")


# ═══════════════════════════════════════════
# 페이지 3: 상품 USP 도출
# ═══════════════════════════════════════════
def page_usp():
    render_page_header("🎯","상품 USP 도출","상품의 성분 데이터를 분석하여 타겟별 마케팅 USP를 도출합니다","purple")

    products_data = load_products()
    products = products_data["products"]

    st.markdown('<div class="s-header">상품 선택</div>', unsafe_allow_html=True)
    n_cols = min(len(products), 7)
    btn_cols = st.columns(n_cols)
    for i, p in enumerate(products):
        with btn_cols[i % n_cols]:
            is_sel = st.session_state.get("usp_product") == i
            css = "p-card-sel" if is_sel else "p-card"
            st.markdown(
                f'<div class="{css}" style="min-height:70px;padding:12px">'
                f'<div class="p-brand" style="font-size:0.88rem">{p["brand"]}</div>'
                f'<div class="p-cat">{p["category"]}</div>'
                f'</div>', unsafe_allow_html=True)
            if st.button("✓" if is_sel else "선택", key=f"usp_btn_{i}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state["usp_product"] = i
                st.rerun()

    if st.session_state.get("usp_product") is None:
        st.info("분석할 상품을 선택하세요.")
        return

    product = products[st.session_state["usp_product"]]
    kr_keywords = product.get("ingredient_keywords_kr", [])
    en_keywords = product.get("ingredient_keywords_en", [])

    # ── 데이터 수집 (5소스 통합) ──
    usp_dc_key = f"usp_dc_{product['brand']}"
    if usp_dc_key not in st.session_state:
        with st.spinner(f"'{product['brand']}' 핵심 성분 데이터를 수집하고 있습니다 (PubMed + 임상시험 + 뉴스 + 식약처 + 트렌드)..."):
            collected = {}
            query = build_product_query(product)
            # 1) PubMed
            try:
                pmids = search_pubmed(query, max_results=15, days_back=1825)
                time.sleep(0.4)
                collected["pubmed"] = fetch_article_details(pmids)
            except Exception:
                collected["pubmed"] = []
            # 2) ClinicalTrials
            try:
                ct_q = " ".join(en_keywords[:2]) + " supplement"
                collected["clinical"] = search_clinical_trials(ct_q, max_results=8)
            except Exception:
                collected["clinical"] = []
            # 3) TV·건강 뉴스
            try:
                news = search_tv_health_news(kr_keywords[0] if kr_keywords else product["brand"], display=5)
                collected["tv"] = news if news else []
            except Exception:
                collected["tv"] = []
            # 4) 식약처
            try:
                mfds = []
                for kw in en_keywords[:2] + kr_keywords[:1]:
                    for item in search_health_food(kw, max_results=5):
                        if not any(r["report_no"]==item["report_no"] for r in mfds):
                            mfds.append(item)
                        if len(mfds)>=5: break
                    if len(mfds)>=5: break
                collected["mfds"] = mfds
            except Exception:
                collected["mfds"] = []
            # 5) 트렌드
            try:
                td = fetch_search_trend(kr_keywords[:3], months_back=12)
                collected["trend"] = td if td else []
            except Exception:
                collected["trend"] = []

            st.session_state[usp_dc_key] = collected

    dc = st.session_state[usp_dc_key]
    articles = dc.get("pubmed", [])

    # 매칭 분석
    article_matches = []
    for a in articles:
        ms = match_article_to_products(a, products)
        pm = next((m for m in ms if m["brand"]==product["brand"]), None)
        article_matches.append({"article":a,"match":pm})

    sorted_matches = sorted(article_matches, key=lambda x: x["match"]["score"] if x["match"] else 0, reverse=True)
    top_articles = [am for am in sorted_matches if am["match"]][:5]

    # ── 수집 현황 메트릭 ──
    st.markdown(f'<div class="s-header">📊 {product["brand"]} — 수집 데이터 기반 인사이트</div>', unsafe_allow_html=True)

    matched_count = sum(1 for am in article_matches if am["match"])
    mc = st.columns(5)
    metrics = [
        (str(len(articles)), "PubMed 논문", "m-val-blue"),
        (str(len(dc.get("clinical",[]))), "임상시험", "m-val-blue"),
        (str(len(dc.get("tv",[]))), "뉴스", "m-val-green"),
        (str(len(dc.get("mfds",[]))), "식약처", "m-val-orange"),
        (str(matched_count), "매칭 논문", ""),
    ]
    for col, (val, lbl, cls) in zip(mc, metrics):
        with col:
            st.markdown(f'<div class="m-card"><div class="m-val {cls}">{val}</div><div class="m-lbl">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("")
    r1l, r1r = st.columns([1, 1.5])

    with r1l:
        st.markdown('<div class="g-card"><div class="g-card-header">🧬 활용 가능 성분</div>', unsafe_allow_html=True)
        for kw in kr_keywords[:6]:
            cnt = sum(1 for am in article_matches if am["match"] and any(kw.lower() in t.lower() or kw in t for t in am["match"].get("matched_terms",[])))
            stars, clr = ("★★★","#059669") if cnt>=5 else (("★★","#d97706") if cnt>=2 else ("★","#94a3b8"))
            st.markdown(f'<div class="d-item" style="display:flex;justify-content:space-between;align-items:center"><span style="font-weight:600">{kw}</span><span style="font-size:0.82rem"><span style="color:{clr};font-weight:700">{stars}</span> · {cnt}건</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with r1r:
        st.markdown('<div class="g-card"><div class="g-card-header">📊 논문 매칭 점수</div>', unsafe_allow_html=True)
        if article_matches:
            cd = [{"논문":am["article"]["title"][:28]+"...","점수":am["match"]["score"] if am["match"] else 0,"활용도":am["match"]["relevance"] if am["match"] else "비연관"} for am in article_matches]
            df = pd.DataFrame(cd).sort_values("점수",ascending=True)
            fig = px.bar(df,x="점수",y="논문",orientation="h",color="활용도",color_discrete_map={"★★★ 즉시 활용":"#22c55e","★★ 콘텐츠 기획":"#eab308","★ 모니터링":"#94a3b8","비연관":"#e2e8f0"})
            fig.update_layout(height=max(180,len(cd)*26),margin=dict(t=5,b=5,l=5,r=5),yaxis=dict(tickfont=dict(size=10)),showlegend=False,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",xaxis=dict(gridcolor="#f1f5f9"))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 핵심 근거 (논문 + 임상시험 + 뉴스 통합)
    st.markdown('<div class="g-card"><div class="g-card-header">📄 핵심 근거 자료</div>', unsafe_allow_html=True)
    if top_articles:
        for i, am in enumerate(top_articles[:3]):
            a, m = am["article"], am["match"]
            sc = "#22c55e" if m["score"]>=15 else ("#eab308" if m["score"]>=8 else "#94a3b8")
            st.markdown(
                f'<div class="d-item"><div style="display:flex;justify-content:space-between;align-items:start">'
                f'<div class="d-title" style="flex:1">📰 {a["title"][:90]}</div>'
                f'<div style="background:{sc};color:white;padding:2px 10px;border-radius:20px;font-size:0.72rem;font-weight:700;margin-left:8px;white-space:nowrap">{m["relevance"]}</div>'
                f'</div><div class="d-meta">{a.get("journal","")} · {a.get("pub_date","")}'
                f' · <a href="{a.get("url","#")}" target="_blank" class="d-link">원문 →</a></div></div>', unsafe_allow_html=True)
    for t in dc.get("clinical",[])[:2]:
        sc2 = {"RECRUITING":"#059669","COMPLETED":"#2563eb"}.get(t["status"],"#64748b")
        st.markdown(
            f'<div class="d-item"><div class="d-title">🏥 {t["title"][:90]}</div>'
            f'<div class="d-meta"><span style="color:{sc2};font-weight:600">{t["status"]}</span> · Phase {t["phase"]}'
            f' · <a href="{t["url"]}" target="_blank" class="d-link">원문 →</a></div></div>', unsafe_allow_html=True)
    for n in dc.get("tv",[])[:2]:
        st.markdown(
            f'<div class="d-item"><div class="d-title">📺 {n["title"][:90]}</div>'
            f'<div class="d-meta">{n.get("pubDate","")}'
            f' · <a href="{n.get("link","#")}" target="_blank" class="d-link">원문 →</a></div></div>', unsafe_allow_html=True)
    if not top_articles and not dc.get("clinical") and not dc.get("tv"):
        st.caption("근거 자료 없음")
    st.markdown('</div>', unsafe_allow_html=True)

    # 타겟별 USP
    st.markdown('<div class="s-header">💬 타겟별 USP 마케팅 메시지</div>', unsafe_allow_html=True)

    if top_articles:
        best_a, best_m = top_articles[0]["article"], top_articles[0]["match"]
        usps = generate_usp_template(best_a, best_m)

        for u in usps:
            kw_tags = "".join(f'<span class="usp-tag usp-t-kw">🔑 {k}</span>' for k in u.get("keywords",[]))
            st.markdown(
                f'<div class="usp-card"><div class="usp-head">'
                f'<span class="usp-seg">🎯 {u["segment"]}</span>'
                f'<span class="usp-age">{u["age"]} · {u["gender"]}</span>'
                f'</div><div class="usp-body">'
                f'<div class="usp-hl">{u.get("headline","")}</div>'
                f'<div class="usp-sub">{u.get("sub_message","")}</div>'
                f'<div class="usp-tags">'
                f'<span class="usp-tag usp-t-ch">📺 {u.get("channels","")}</span>'
                f'<span class="usp-tag usp-t-tn">🎨 {u.get("tone","")}</span>'
                f'{kw_tags}</div></div></div>', unsafe_allow_html=True)

        st.markdown("")
        with st.expander("🤖 AI 기반 고급 USP 생성 (Anthropic API 필요)", expanded=False):
            api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
            if st.button("AI USP 생성", type="primary"):
                if api_key:
                    with st.spinner("AI가 USP를 생성하고 있습니다..."):
                        ai_usps = generate_usp_with_ai(best_a, best_m, api_key=api_key)
                    if ai_usps and ai_usps[0].get("source")=="ai":
                        st.markdown(ai_usps[0]["ai_response"])
                    else:
                        st.warning("AI 생성 실패. 위 템플릿 USP를 참고하세요.")
                else:
                    st.warning("API Key를 입력하세요.")
    else:
        st.info("매칭된 논문이 없어 USP를 생성할 수 없습니다.")


# ═══════════════════════════════════════════
# 페이지 4: 경쟁사 모니터링
# ═══════════════════════════════════════════
def page_competitor():
    render_page_header("🔍","경쟁사 모니터링","카테고리별 경쟁사 마케팅 현황을 분석합니다","orange")

    products_data = load_products()
    products = products_data["products"]
    competitor_db = load_competitor_db()

    st.markdown('<div class="s-header">자사 상품 선택</div>', unsafe_allow_html=True)
    n_cols = min(len(products), 7)
    btn_cols = st.columns(n_cols)
    for i, p in enumerate(products):
        with btn_cols[i % n_cols]:
            is_sel = st.session_state.get("comp_product") == i
            css = "p-card-sel" if is_sel else "p-card"
            st.markdown(
                f'<div class="{css}" style="min-height:70px;padding:12px">'
                f'<div class="p-brand" style="font-size:0.88rem">{p["brand"]}</div>'
                f'<div class="p-cat">{p["category"]}</div>'
                f'</div>', unsafe_allow_html=True)
            if st.button("✓" if is_sel else "선택", key=f"comp_btn_{i}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state["comp_product"] = i
                st.rerun()

    if st.session_state.get("comp_product") is None:
        st.info("분석할 자사 상품을 선택하세요.")
        return

    product = products[st.session_state["comp_product"]]
    cat_data = competitor_db.get("categories",{}).get(product["category"])
    if not cat_data:
        # 카테고리가 없으면 빈 구조 생성
        competitor_db.setdefault("categories",{})[product["category"]] = {
            "ckd_brand": product["brand"], "competitors": [],
            "ckd_position": {"premium_score":5,"price_score":5,"usp":{"headline":"","selling_points":[],"target":"","key_claim":""}},
            "differentiation": []
        }
        save_competitor_db(competitor_db)
        cat_data = competitor_db["categories"][product["category"]]

    competitors = cat_data.get("competitors",[])
    ckd = cat_data.get("ckd_position",{})
    ckd_ingredient_names = [ing.lower() for ing in product.get("ingredient_keywords_kr",[])]

    # ── 자동 경쟁사 탐색 (상품 선택 시 자동 실행) ──
    scan_key = f"comp_scan_{product['brand']}"
    if scan_key not in st.session_state:
        with st.spinner(f"'{product['category']}' 카테고리 경쟁사를 네이버 쇼핑에서 탐색하고 있습니다..."):
            scanned = scan_competitors(product["category"], ckd_brand=product["brand"])
            st.session_state[scan_key] = scanned

    scanned = st.session_state.get(scan_key, [])

    # ── 헤더 + 경쟁사 추가 ──
    col_hdr, col_addbtn = st.columns([5, 1])
    with col_hdr:
        st.markdown(f'<div class="s-header">⚔️ "{product["brand"]}" 카테고리 경쟁사 분석</div>', unsafe_allow_html=True)
    with col_addbtn:
        st.markdown("")
        if st.button("＋ 경쟁사 추가", type="primary", use_container_width=True):
            st.session_state["comp_add_mode"] = True

    if st.session_state.get("comp_add_mode"):
        with st.expander("경쟁사 추가 — 상품 URL 입력", expanded=True):
            comp_url = st.text_input("경쟁사 상품 URL을 입력하세요", placeholder="https://smartstore.naver.com/... 또는 https://www.coupang.com/...")
            st.caption("네이버 스마트스토어, 쿠팡, 일반 쇼핑몰 URL 모두 가능합니다")
            with st.form("add_competitor_form"):
                ac1, ac2 = st.columns(2)
                with ac1:
                    new_comp_company = st.text_input("회사명 *")
                    new_comp_brand = st.text_input("브랜드/상품명 *")
                    new_comp_headline = st.text_input("USP 헤드라인")
                with ac2:
                    new_comp_sp = st.text_area("셀링포인트 (줄바꿈으로 구분)")
                    new_comp_target = st.text_input("타겟 고객층")
                    new_comp_ingredients = st.text_input("주요 성분 (쉼표 구분)")
                if st.form_submit_button("등록", type="primary"):
                    if new_comp_company and new_comp_brand:
                        cat_data["competitors"].append({
                            "company": new_comp_company, "brand": new_comp_brand,
                            "search_keyword": f"{new_comp_brand} {new_comp_company}",
                            "product_url": comp_url or "",
                            "usp": {"headline": new_comp_headline or new_comp_brand,
                                    "selling_points": [s.strip() for s in new_comp_sp.split("\n") if s.strip()],
                                    "target": new_comp_target, "key_claim": ""},
                            "manual_ingredients": [s.strip() for s in new_comp_ingredients.split(",") if s.strip()],
                            "channels": [], "price_position": "중", "premium_score": 5, "price_score": 5,
                        })
                        save_competitor_db(competitor_db)
                        st.session_state.pop("comp_add_mode", None)
                        st.session_state.pop(scan_key, None)
                        st.rerun()

    # ── 유틸 함수 ──
    def _get_usp_details(usp_data):
        if isinstance(usp_data, dict): return usp_data
        return {"headline": usp_data or "", "selling_points": [], "target": "", "key_claim": ""}

    def _ingredient_compare_html(comp_ingredients):
        diff = compare_ingredients(ckd_ingredient_names, comp_ingredients)
        html = '<div style="margin-top:8px;padding-top:8px;border-top:1px solid #f1f5f9">'
        html += '<div style="font-size:0.72rem;color:#94a3b8;margin-bottom:4px">🧬 성분 비교 (자사 기준)</div><div style="display:flex;flex-wrap:wrap;gap:3px">'
        for s in diff["common"]:
            html += f'<span style="background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:12px;font-size:0.72rem;font-weight:600">🔵 {s}</span>'
        for s in diff["ckd_only"]:
            html += f'<span style="background:#dcfce7;color:#15803d;padding:2px 8px;border-radius:12px;font-size:0.72rem;font-weight:600">✅ {s}</span>'
        for s in diff["competitor_only"]:
            html += f'<span style="background:#fef2f2;color:#dc2626;padding:2px 8px;border-radius:12px;font-size:0.72rem;font-weight:600">⚠️ {s}</span>'
        html += '</div></div>'
        return html

    # ── 채널별 가격 수집 (자사 + 경쟁사) ──
    price_cache_key = f"comp_allprices_{product['brand']}"
    if price_cache_key not in st.session_state:
        with st.spinner("자사 및 경쟁사 채널별 가격을 조회하고 있습니다..."):
            all_prices = {}
            all_prices["ckd"] = search_product_prices(f"종근당 {product['brand']}", brand_keywords=["종근당","종근당건강","ckd"])
            for sc in scanned[:10]:
                all_prices[sc["brand"]] = search_product_prices(sc["product_name"][:30], brand_keywords=[sc["brand"], sc.get("mall","")])
            st.session_state[price_cache_key] = all_prices
    all_prices = st.session_state[price_cache_key]

    def _price_chips(pd_data, brand_name=""):
        """채널별 가격 칩 HTML (1일당 가격 포함)."""
        import urllib.parse
        enc = urllib.parse.quote(brand_name[:30])
        html = '<div style="display:flex;gap:8px;flex-wrap:wrap">'
        for ch_key, ch_name, ch_color, fallback in [("naver","네이버","#03c75a",None),("coupang","쿠팡","#ef4444",f"https://www.coupang.com/np/search?q={enc}"),("brand","자사몰","#2563eb",f"https://www.ckdmall.co.kr/search?q={enc}")]:
            items = pd_data.get(ch_key,[])
            if items and items[0].get("daily_price",0) > 0:
                it = items[0]
                html += (f'<a href="{it["link"]}" target="_blank" style="text-decoration:none">'
                         f'<span style="background:{ch_color};color:#fff;padding:3px 8px;border-radius:8px;font-size:0.72rem;font-weight:700">{ch_name}</span>'
                         f' <span style="font-weight:700;font-size:0.85rem">{it["price"]:,}원</span>'
                         f' <span style="font-size:0.68rem;color:#94a3b8">({it["quantity"]}, 1일 {it["daily_price"]:,}원)</span></a>')
            elif items:
                it = items[0]
                html += (f'<a href="{it["link"]}" target="_blank" style="text-decoration:none">'
                         f'<span style="background:{ch_color};color:#fff;padding:3px 8px;border-radius:8px;font-size:0.72rem;font-weight:700">{ch_name}</span>'
                         f' <span style="font-weight:700;font-size:0.85rem">{it["price"]:,}원</span></a>')
            elif fallback:
                html += (f'<a href="{fallback}" target="_blank" style="text-decoration:none">'
                         f'<span style="background:{ch_color};opacity:0.5;color:#fff;padding:3px 8px;border-radius:8px;font-size:0.72rem;font-weight:700">{ch_name}</span>'
                         f' <span style="color:#94a3b8;font-size:0.75rem">검색 →</span></a>')
        html += '</div>'
        return html

    # ── 자사 카드 ──
    ckd_kr_ings = product.get("ingredient_keywords_kr",[])
    ckd_claims = product.get("health_claims",[])
    target_info = product.get("target_demographic",{})
    ckd_ings_html = "".join(f'<span style="background:rgba(37,99,235,0.15);color:#93c5fd;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px">{ing}</span>' for ing in ckd_kr_ings)
    ckd_claims_html = "".join(f'<span style="background:rgba(34,197,94,0.15);color:#86efac;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px">{c}</span>' for c in ckd_claims)
    ckd_pd = all_prices.get("ckd",{"naver":[],"coupang":[],"brand":[]})

    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:16px;padding:20px;margin-bottom:16px;color:#fff">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
        f'<div><span style="font-size:1.1rem;font-weight:800">종근당 {product["brand"]}</span>'
        f'<span style="background:rgba(37,99,235,0.3);padding:3px 10px;border-radius:20px;font-size:0.75rem;margin-left:8px">자사</span></div>'
        f'<span style="color:#94a3b8;font-size:0.82rem">🎯 타겟: {target_info.get("primary_age","")}</span></div>'
        # 제품명
        f'<div style="font-size:0.72rem;color:rgba(255,255,255,0.4);margin-bottom:2px">제품명</div>'
        f'<div style="font-size:0.88rem;color:#e2e8f0;margin-bottom:12px;padding:8px 12px;background:rgba(255,255,255,0.06);border-radius:8px">{product["brand"]} ({", ".join(product.get("sub_products",[])[:3])})</div>'
        # 가격
        f'<div style="font-size:0.72rem;color:rgba(255,255,255,0.4);margin-bottom:4px">채널별 가격</div>'
        f'{_price_chips(ckd_pd, product["brand"])}'
        # 주요 성분
        f'<div style="margin-top:12px;font-size:0.72rem;color:rgba(255,255,255,0.4);margin-bottom:4px">주요 성분</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:3px">{ckd_ings_html}</div>'
        # 건강기능 표시
        f'<div style="margin-top:8px;font-size:0.72rem;color:rgba(255,255,255,0.4);margin-bottom:4px">건강기능 표시</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:3px">{ckd_claims_html}</div>'
        f'</div>', unsafe_allow_html=True)

    # ── 네이버 쇼핑 상위 경쟁 브랜드 ──
    if scanned:
        st.markdown(f'<div class="s-header">🛒 네이버 쇼핑 상위 경쟁 브랜드 ({len(scanned[:10])}개)</div>', unsafe_allow_html=True)

        for si, sc in enumerate(scanned[:10]):
            diff = compare_ingredients(ckd_ingredient_names, sc["ingredients"])
            in_ckd = diff["common"]
            not_in_ckd = diff["competitor_only"]
            ckd_only = diff["ckd_only"]

            all_ings = sc["ingredients"]
            ings_html = "".join(f'<span style="background:#f1f5f9;color:#475569;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px">{s}</span>' for s in all_ings) if all_ings else '<span style="color:#cbd5e1;font-size:0.75rem">성분 정보 없음</span>'
            in_ckd_html = "".join(f'<span style="background:#dcfce7;color:#15803d;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px">✅ {s}</span>' for s in in_ckd) if in_ckd else '<span style="color:#cbd5e1;font-size:0.75rem">—</span>'
            not_in_ckd_html = "".join(f'<span style="background:#fef2f2;color:#dc2626;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px">⚠️ {s}</span>' for s in not_in_ckd) if not_in_ckd else '<span style="color:#cbd5e1;font-size:0.75rem">—</span>'
            ckd_only_html = "".join(f'<span style="background:#dbeafe;color:#2563eb;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px">💪 {s}</span>' for s in ckd_only) if ckd_only else '<span style="color:#cbd5e1;font-size:0.75rem">—</span>'

            sc_pd = all_prices.get(sc["brand"],{"naver":[],"coupang":[],"brand":[]})

            st.markdown(
                f'<div style="background:linear-gradient(160deg,#ffffff,#f8fafd);border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                f'<div><span style="font-size:0.95rem;font-weight:700;color:#1e293b">{sc["brand"]}</span>'
                f'<span style="background:#fff7ed;color:#ea580c;padding:2px 8px;border-radius:20px;font-size:0.68rem;font-weight:600;margin-left:8px">쇼핑 상위</span></div>'
                f'<a href="{sc["link"]}" target="_blank" class="d-link" style="font-size:0.75rem">상품 보기 →</a></div>'
                # 제품명
                f'<div style="font-size:0.72rem;font-weight:700;color:#94a3b8;margin-bottom:2px">제품명</div>'
                f'<div style="font-size:0.85rem;color:#475569;margin-bottom:10px;padding:8px 12px;background:#f8fafc;border-radius:8px">{sc["product_name"]}</div>'
                # 채널별 가격
                f'<div style="font-size:0.72rem;font-weight:700;color:#94a3b8;margin-bottom:4px">채널별 가격</div>'
                f'{_price_chips(sc_pd, sc["brand"])}'
                # 주요 성분
                f'<div style="margin-top:10px;font-size:0.72rem;font-weight:700;color:#94a3b8;margin-bottom:4px">주요 성분</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:3px;margin-bottom:10px">{ings_html}</div>'
                # 성분 분석 — 3열
                f'<div style="font-size:0.72rem;font-weight:700;color:#94a3b8;margin-bottom:6px">성분 분석 (자사 상품 기준)</div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">'
                f'<div style="background:#dbeafe;border-radius:10px;padding:10px 12px">'
                f'<div style="font-size:0.72rem;font-weight:700;color:#2563eb;margin-bottom:4px">💪 자사에만 있어요!</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:3px">{ckd_only_html}</div></div>'
                f'<div style="background:#f0fdf4;border-radius:10px;padding:10px 12px">'
                f'<div style="font-size:0.72rem;font-weight:700;color:#15803d;margin-bottom:4px">✅ 자사에도 있어요!</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:3px">{in_ckd_html}</div></div>'
                f'<div style="background:#fef2f2;border-radius:10px;padding:10px 12px">'
                f'<div style="font-size:0.72rem;font-weight:700;color:#dc2626;margin-bottom:4px">⚠️ 자사에는 없어요!</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:3px">{not_in_ckd_html}</div></div>'
                f'</div>'
                f'</div>', unsafe_allow_html=True)

    # ── 채널별 1일당 가격 비교 차트 ──
    if scanned:
        with st.container(border=True):
            st.markdown("**💰 채널별 1일당 가격 비교** _(네이버 쇼핑 실시간 데이터 · 동일 단위 환산)_")
            chart_data = []
            chart_brands = [("종근당 " + product["brand"][:4], "ckd")] + [(sc["brand"][:8], sc["brand"]) for sc in scanned[:10]]
            for label, key in chart_brands:
                pd_data = all_prices.get(key, {"naver":[],"coupang":[],"brand":[]})
                for ch_name, ch_key in [("네이버","naver"),("쿠팡","coupang"),("자사몰","brand")]:
                    if pd_data[ch_key] and pd_data[ch_key][0].get("daily_price",0) > 0:
                        chart_data.append({"브랜드":label,"채널":ch_name,"1일당 가격":pd_data[ch_key][0]["daily_price"]})

            if chart_data:
                fig_price = px.bar(
                    pd.DataFrame(chart_data), x="브랜드", y="1일당 가격", color="채널", barmode="group",
                    color_discrete_map={"네이버":"#03c75a","쿠팡":"#ef4444","자사몰":"#2563eb"},
                    text="1일당 가격",
                )
                fig_price.update_traces(texttemplate="%{text:,}원/일", textposition="outside", textfont_size=9)
                fig_price.update_layout(
                    height=380, margin=dict(t=20,b=20,l=20,r=20),
                    yaxis=dict(title="1일당 가격 (원)", gridcolor="#f1f5f9"),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                )
                st.plotly_chart(fig_price, use_container_width=True)
            else:
                st.caption("가격 데이터를 가져올 수 없습니다.")

    # ── 차별화 포인트 ──
    st.markdown('<div class="s-header">💡 자사 차별화 포인트</div>', unsafe_allow_html=True)
    for i, pt in enumerate(cat_data.get("differentiation",[])):
        st.markdown(f'<div class="diff-c"><b>{i+1}.</b> {pt}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════
# 라우팅
# ═══════════════════════════════════════════

# ═══════════════════════════════════════════
# 페이지 5: 검색 트렌드
# ═══════════════════════════════════════════
def page_trend():
    render_page_header("📊","검색쿼리 분석","네이버 검색광고 + 데이터랩 기반 키워드별 추정 검색량을 조회합니다","blue")

    trend_kw = load_trend_keywords()

    # 상단: 카테고리 + 기간 설정
    from datetime import datetime as _dt, timedelta as _td
    cat_col, d1_col, d2_col, unit_col, btn_col = st.columns([1.5, 1.2, 1.2, 1, 1])
    with cat_col:
        category = st.selectbox("카테고리", ["자사", "경쟁사", "제품", "시즌"], key="trend_cat")
    with d1_col:
        start_date = st.date_input("시작일", value=_dt.now() - _td(days=365), key="trend_start")
    with d2_col:
        end_date = st.date_input("종료일", value=_dt.now(), key="trend_end")
    with unit_col:
        time_unit_map = {"일별":"date","월별":"month","연도별":"year"}
        time_unit_label = st.selectbox("단위", list(time_unit_map.keys()), index=1, key="trend_unit")
        time_unit = time_unit_map[time_unit_label]
    with btn_col:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        search_btn = st.button("🔍 조회", type="primary", use_container_width=True, key="trend_search")

    st.markdown("---")

    # 카테고리별 키워드 결정
    if category == "자사":
        all_keywords = trend_kw.get("자사", [])
        kw_label = "자사 키워드"
    elif category == "경쟁사":
        all_keywords = trend_kw.get("경쟁사", [])
        kw_label = "경쟁사 키워드"
    elif category == "시즌":
        all_keywords = trend_kw.get("시즌", [])
        kw_label = "시즌 키워드"
    else:  # 제품
        product_kws = trend_kw.get("제품", {})
        product_names = list(product_kws.keys())
        if not product_names:
            st.info("제품 키워드가 없습니다.")
            return
        selected_product = st.selectbox("제품 카테고리 선택", product_names, key="trend_product")
        all_keywords = product_kws.get(selected_product, [])
        kw_label = f"'{selected_product}' 키워드"

    if not all_keywords:
        st.info("키워드가 없습니다. 아래에서 추가해주세요.")

    # 조회 실행
    trend_cache_key = f"trend_vol_{category}_{start_date}_{end_date}_{time_unit}_{'_'.join(all_keywords[:5])}"

    if search_btn and all_keywords:
        with st.spinner(f"{len(all_keywords)}개 키워드 추정 검색량을 산출하고 있습니다..."):
            result = estimate_search_volume(
                all_keywords,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                time_unit,
            )
            st.session_state[trend_cache_key] = result

    # 결과 표시
    if trend_cache_key in st.session_state:
        result = st.session_state[trend_cache_key]

        graph_col, filter_col = st.columns([3, 1])

        # 우측: 체크박스 필터
        with filter_col:
            st.markdown(f"**{kw_label}**")

            def _toggle_all():
                val = st.session_state.get("trend_all", True)
                for kw in all_keywords:
                    st.session_state[f"trend_kw_{kw}"] = val

            st.checkbox("전체 선택/해제", value=True, key="trend_all", on_change=_toggle_all)

            # 개별 체크박스 초기값 설정
            for kw in all_keywords:
                if f"trend_kw_{kw}" not in st.session_state:
                    st.session_state[f"trend_kw_{kw}"] = True

            selected_kws = []
            for kw in all_keywords:
                has_data = bool(result.get(kw))
                checked = st.checkbox(kw, key=f"trend_kw_{kw}", disabled=not has_data)
                if checked and has_data:
                    selected_kws.append(kw)

        # 좌측: 그래프
        with graph_col:
            if selected_kws:
                fig = go.Figure()
                colors = ['#03C75A','#185ADB','#FF6B6B','#FFC947','#A259FF','#00BCD4','#FF5722','#795548','#607D8B','#E91E63']
                for idx, kw in enumerate(selected_kws):
                    data_points = result.get(kw, [])
                    if data_points:
                        periods = [d["period"][:10] for d in data_points]
                        volumes = [d["volume"] for d in data_points]
                        fig.add_trace(go.Scatter(
                            x=periods, y=volumes, name=kw,
                            line=dict(color=colors[idx % len(colors)], width=2.5),
                            mode="lines+markers", marker=dict(size=4),
                        ))
                fig.update_layout(
                    height=450, margin=dict(t=20,b=40,l=40,r=20),
                    xaxis=dict(title="날짜", gridcolor="#f1f5f9", tickangle=-45),
                    yaxis=dict(title="추정 검색량", gridcolor="#f1f5f9", rangemode="tozero"),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("표시할 키워드를 선택해주세요.")

        # 데이터 테이블
        if selected_kws:
            with st.expander("📋 데이터 테이블 보기"):
                table_data = {}
                for kw in selected_kws:
                    for d in result.get(kw, []):
                        period = d["period"][:10]
                        if period not in table_data:
                            table_data[period] = {"날짜": period}
                        table_data[period][kw] = f'{d["volume"]:,}' if isinstance(d["volume"], int) else d["volume"]
                if table_data:
                    df_table = pd.DataFrame(list(table_data.values())).sort_values("날짜")
                    st.dataframe(df_table, use_container_width=True, hide_index=True)

    elif all_keywords:
        st.info("🔍 조회 버튼을 클릭하면 검색 트렌드가 표시됩니다.")

    st.caption("키워드 관리는 ⚙️ 설정 > 🔤 검색 키워드 관리에서 가능합니다.")


# ═══════════════════════════════════════════
# 페이지 6: 광고배너 (플레이스홀더)
# ═══════════════════════════════════════════
def page_adbanner():
    render_page_header("🎨","광고배너 조사","META 광고 라이브러리 기반 경쟁사 광고 소재를 조사합니다","orange")
    st.info("META 광고 라이브러리 크롤링 기반 광고배너 조사 기능은 준비 중입니다.")


# ═══════════════════════════════════════════
# 심의: AI 사전검토
# ═══════════════════════════════════════════
def page_ai_review():
    render_page_header("📋","AI 사전검토","광고 문구를 입력하면 심의 기준에 맞는지 사전 검토합니다","blue")

    # 제품 선택 (3개만)
    review_products = ["콘드로이친", "락토핏 골드", "포스파티딜세린"]
    products_data = load_products()
    products = [p for p in products_data["products"] if p["brand"] in review_products]

    sel_col, _ = st.columns([2, 3])
    with sel_col:
        product_names = ["(제품 선택)"] + [p["brand"] for p in products]
        sel_product = st.selectbox("검토 대상 제품", product_names, key="review_product")

    if sel_product != "(제품 선택)":
        product = next(p for p in products if p["brand"] == sel_product)
        category = product.get("category", "")
    else:
        category = ""

    # 허용 표현 + 광고 문구 입력
    if category:
        allowed = ALLOWED_CLAIMS.get(category, [])
        if allowed:
            st.markdown(
                '<div style="background:var(--c-success-light);border:1px solid #bbf7d0;border-radius:var(--radius);padding:14px 18px;margin-bottom:14px">'
                '<div style="font-size:var(--font-sm);font-weight:700;color:var(--c-success);margin-bottom:8px">식약처 인정 기능성 표현</div>'
                + "".join(f'<div style="font-size:var(--font-sm);color:#15803d;padding:2px 0">✅ {a}</div>' for a in allowed)
                + '</div>', unsafe_allow_html=True)

    ad_text = st.text_area("광고 문구를 입력하세요", height=180, placeholder="예: 콘드로이친은 관절 건강에 도움을 줄 수 있는 건강기능식품입니다...")
    review_btn = st.button("사전 검토 실행", type="primary", use_container_width=True)

    # 검토 실행 → 세션에 저장
    if review_btn and ad_text.strip():
        result = review_ad_text(ad_text, category)
        st.session_state["review_result"] = result
        st.session_state["review_ad_text"] = ad_text
        st.session_state["review_category"] = category

    if "review_result" not in st.session_state:
        st.markdown("")
        st.markdown(
            '<div style="background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--radius);padding:20px">'
            '<div style="font-size:var(--font-base);font-weight:700;color:var(--c-text);margin-bottom:10px">광고 심의 사전 검토 안내</div>'
            '<div style="font-size:var(--font-sm);color:var(--c-text-sub);line-height:1.8">'
            '1. 검토 대상 <b>제품을 선택</b>하면 해당 제품의 식약처 인정 기능성 표현을 확인할 수 있습니다.<br>'
            '2. <b>광고 문구를 입력</b>하고 검토 실행을 클릭하면 금지 표현을 자동 감지합니다.<br>'
            '3. 검토 결과는 참고용이며, <b>공식 심의를 대체하지 않습니다</b>.<br><br>'
            '<span style="color:var(--c-text-muted)">검토 기준: 식품 등의 표시·광고에 관한 법률 제8조<br>'
            '심의 기관: 한국건강기능식품협회 (ad.khff.or.kr)</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        return

    result = st.session_state["review_result"]
    ad_text = st.session_state.get("review_ad_text", ad_text)
    category = st.session_state.get("review_category", category)
    violations = result["violations"]
    warnings = result["warnings"]
    score = result["score"]
    summary = result["summary"]

    st.markdown("---")

    # 점수 + 요약 (다크 카드)
    score_color = "#dc2626" if score < 40 else ("#d97706" if score < 70 else "#059669")
    score_bg = "#fef2f2" if score < 40 else ("#fffbeb" if score < 70 else "#ecfdf5")
    score_label = "부적합 위험" if score < 40 else ("수정 필요" if score < 70 else "적합 가능")
    bar_width = max(5, score)

    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:var(--radius);padding:24px;margin-bottom:20px;color:#fff">'
        f'<div style="display:flex;align-items:center;gap:24px">'
        # 점수 원형
        f'<div style="width:80px;height:80px;border-radius:50%;background:{score_bg};'
        f'display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0">'
        f'<div style="font-size:1.8rem;font-weight:800;color:{score_color};line-height:1">{score}</div>'
        f'<div style="font-size:0.6rem;color:{score_color};font-weight:600">/ 100</div></div>'
        # 정보
        f'<div style="flex:1">'
        f'<div style="font-size:var(--font-lg);font-weight:800;color:#fff;margin-bottom:4px">{score_label}</div>'
        f'<div style="font-size:var(--font-sm);color:#94a3b8;margin-bottom:10px">{summary}</div>'
        # 진행바
        f'<div style="background:rgba(255,255,255,0.1);border-radius:20px;height:6px;width:100%">'
        f'<div style="background:{score_color};border-radius:20px;height:6px;width:{bar_width}%"></div></div>'
        f'<div style="display:flex;gap:16px;margin-top:10px">'
        f'<span style="font-size:var(--font-xs);color:#ef4444">위반 {len(violations)}건</span>'
        f'<span style="font-size:var(--font-xs);color:#eab308">주의 {len(warnings)}건</span>'
        f'</div></div></div></div>',
        unsafe_allow_html=True,
    )

    # 메트릭 카드
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.markdown(f'<div class="m-card"><div class="m-val" style="color:#ef4444">{len(violations)}</div><div class="m-lbl">위반 항목</div></div>', unsafe_allow_html=True)
    with mc2:
        st.markdown(f'<div class="m-card"><div class="m-val" style="color:#eab308">{len(warnings)}</div><div class="m-lbl">주의 항목</div></div>', unsafe_allow_html=True)
    with mc3:
        safe_count = len(ALLOWED_CLAIMS.get(category, []))
        st.markdown(f'<div class="m-card"><div class="m-val" style="color:var(--c-success)">{safe_count}</div><div class="m-lbl">허용 표현</div></div>', unsafe_allow_html=True)

    st.markdown("")

    # 위반 + 주의 + 허용 탭으로 구분
    if violations:
        st.markdown('<div class="s-header">위반 감지 항목</div>', unsafe_allow_html=True)
        for i, v in enumerate(violations):
            level_color = "#dc2626" if v["level"] == "critical" else "#d97706"
            level_label = "치명적" if v["level"] == "critical" else "주요"
            st.markdown(
                f'<div style="background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--radius);'
                f'padding:16px;margin-bottom:8px;position:relative;overflow:hidden">'
                f'<div style="position:absolute;top:0;left:0;bottom:0;width:4px;background:{level_color}"></div>'
                f'<div style="margin-left:12px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                f'<span style="font-weight:700;color:var(--c-text);font-size:var(--font-sm)">{v["type"]}</span>'
                f'<span style="background:{level_color};color:#fff;padding:3px 12px;border-radius:20px;'
                f'font-size:var(--font-xs);font-weight:700">{level_label}</span></div>'
                f'<div style="background:{level_color}10;border-radius:8px;padding:10px 12px;margin-bottom:8px">'
                f'<span style="font-size:var(--font-sm);color:{level_color};font-weight:700">"{v["matched"]}"</span></div>'
                f'<div style="font-size:var(--font-xs);color:var(--c-text-muted);line-height:1.6">'
                f'{v["desc"]}<br>근거: <b>{v["law"]}</b></div>'
                f'</div></div>', unsafe_allow_html=True)

    if warnings:
        st.markdown('<div class="s-header">주의 항목</div>', unsafe_allow_html=True)
        for w in warnings:
            st.markdown(
                f'<div style="background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--radius);'
                f'padding:14px;margin-bottom:6px;position:relative;overflow:hidden">'
                f'<div style="position:absolute;top:0;left:0;bottom:0;width:4px;background:#eab308"></div>'
                f'<div style="margin-left:12px">'
                f'<div style="font-weight:600;color:var(--c-text);font-size:var(--font-sm);margin-bottom:4px">'
                f'{w["type"]} — <span style="color:#d97706;font-weight:700">"{w["matched"]}"</span></div>'
                f'<div style="font-size:var(--font-xs);color:var(--c-text-muted)">{w["desc"]} ({w["law"]})</div>'
                f'</div></div>', unsafe_allow_html=True)

    if category:
        allowed = ALLOWED_CLAIMS.get(category, [])
        if allowed:
            st.markdown('<div class="s-header">사용 가능한 표현 (식약처 인정)</div>', unsafe_allow_html=True)
            st.markdown(
                '<div style="background:var(--c-success-light);border:1px solid #bbf7d0;border-radius:var(--radius);padding:16px">',
                unsafe_allow_html=True)
            for a in allowed:
                st.markdown(
                    f'<div style="font-size:var(--font-sm);color:#15803d;padding:4px 0;font-weight:500">✅ {a}</div>',
                    unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── AI 심층 분석 + 증빙자료 ──
    st.markdown('<div class="s-header">AI 심층 분석 + 증빙자료</div>', unsafe_allow_html=True)

    ai_review_key = f"ai_review_{hash(ad_text)}"
    if ai_review_key not in st.session_state:
        if st.button("AI 심층 분석 실행", type="primary", use_container_width=True):
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                st.warning("Anthropic API Key가 설정되지 않았습니다.")
            else:
                with st.spinner("AI가 광고 문구를 분석하고 증빙자료를 수집하고 있습니다..."):
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)

                        # 허용 표현 목록
                        allowed_list = "\n".join(f"- {a}" for a in ALLOWED_CLAIMS.get(category, []))
                        violation_list = "\n".join(f"- [{v['level']}] \"{v['matched']}\" ({v['type']}, {v['law']})" for v in violations)
                        warning_list = "\n".join(f"- \"{w['matched']}\" ({w['type']})" for w in warnings)

                        prompt = f"""당신은 건강기능식품 광고 심의 전문가입니다. 아래 광고 문구를 분석하고 3가지를 제공해주세요.

## 광고 문구
{ad_text}

## 제품 카테고리
{category or "미선택"}

## 식약처 인정 기능성 표현 (이 범위 내에서만 광고 가능)
{allowed_list or "없음"}

## 자동 감지된 위반 사항
{violation_list or "없음"}

## 자동 감지된 주의 사항
{warning_list or "없음"}

## 요청 사항

### 1. 문구 분석
- 위반/주의 항목에 대해 왜 문제가 되는지 구체적으로 설명
- 식약처 인정 기능성 범위를 초과하는 표현이 있는지 분석

### 2. 수정 제안
- 위반 표현을 식약처 기준에 맞게 수정한 대안 문구를 제시
- 전체 광고 문구의 수정 버전을 작성

### 3. 증빙자료 추천
- 이 광고에서 주장하는 효능을 뒷받침할 수 있는 과학적 근거 유형 제안
- PubMed에서 검색할 수 있는 관련 키워드 3~5개 제안

한국어로 간결하게 작성해주세요. 식약처 광고 심의 기준을 엄격히 적용해주세요.
중요: 마크다운 헤딩(#, ##, ###)은 사용하지 마세요. 볼드(**텍스트**)와 리스트(-)만 사용하세요. 표는 간단하게만 사용하세요."""

                        msg = client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=1500,
                            messages=[{"role": "user", "content": prompt}],
                        )
                        ai_result = msg.content[0].text

                        # PubMed 증빙자료 자동 검색
                        evidence = {}
                        if category:
                            en_keywords = []
                            sel_p = next((p for p in products if p.get("category") == category), None)
                            if sel_p:
                                en_keywords = sel_p.get("ingredient_keywords_en", [])[:3]
                            if en_keywords:
                                try:
                                    query = " OR ".join(f'"{kw}"[tiab]' for kw in en_keywords)
                                    query += ' AND "supplement"[tiab]'
                                    pmids = search_pubmed(query, max_results=5, days_back=1825)
                                    time.sleep(0.4)
                                    articles = fetch_article_details(pmids)
                                    evidence["pubmed"] = articles
                                except Exception:
                                    evidence["pubmed"] = []
                            try:
                                ct_query = " ".join(en_keywords) + " supplement"
                                evidence["clinical"] = search_clinical_trials(ct_query, max_results=3)
                            except Exception:
                                evidence["clinical"] = []

                        st.session_state[ai_review_key] = {"analysis": ai_result, "evidence": evidence}
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI 분석 실패: {e}")

    if ai_review_key in st.session_state:
        ai_data = st.session_state[ai_review_key]

        # AI 분석 결과
        st.markdown(
            '<div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:var(--radius);'
            'padding:14px 18px;margin:20px 0 10px;color:#fff;font-size:var(--font-base);font-weight:700">'
            'AI 심층 분석 리포트</div>',
            unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(ai_data["analysis"])

        # 증빙자료
        evidence = ai_data.get("evidence", {})
        pubmed_articles = evidence.get("pubmed", [])
        clinical_trials = evidence.get("clinical", [])

        if pubmed_articles or clinical_trials:
            st.markdown('<div class="s-header">📄 증빙자료 (자동 수집)</div>', unsafe_allow_html=True)

            if pubmed_articles:
                st.markdown(f"**PubMed 관련 논문 ({len(pubmed_articles)}건)**")
                for a in pubmed_articles:
                    st.markdown(
                        f'<div class="d-item">'
                        f'<div class="d-title">{a["title"][:100]}</div>'
                        f'<div class="d-meta">{a.get("journal","")} · {a.get("pub_date","")}'
                        f' · <a href="{a.get("url","#")}" target="_blank" class="d-link">원문 →</a></div>'
                        f'</div>', unsafe_allow_html=True)

            if clinical_trials:
                st.markdown(f"**ClinicalTrials.gov 임상시험 ({len(clinical_trials)}건)**")
                for t in clinical_trials:
                    sc = {"RECRUITING":"#059669","COMPLETED":"#2563eb"}.get(t["status"],"#64748b")
                    st.markdown(
                        f'<div class="d-item">'
                        f'<div class="d-title">{t["title"][:100]}</div>'
                        f'<div class="d-meta"><span style="color:{sc};font-weight:600">{t["status"]}</span>'
                        f' · Phase {t["phase"]}'
                        f' · <a href="{t["url"]}" target="_blank" class="d-link">원문 →</a></div>'
                        f'</div>', unsafe_allow_html=True)

            st.caption("위 자료는 심의 신청 시 증빙자료로 활용할 수 있습니다.")

    # 면책 문구
    st.markdown("")
    st.caption("⚠️ 본 검토 결과는 참고용이며, 한국건강기능식품협회의 공식 심의를 대체하지 않습니다. 실제 심의는 ad.khff.or.kr에서 신청하세요.")


# ═══════════════════════════════════════════
# 심의: 심의현황 대시보드
# ═══════════════════════════════════════════
def page_review_dashboard():
    render_page_header("📊","심의현황 대시보드","심의 요청/진행/완료 현황을 관리합니다","blue")
    st.info("심의현황 대시보드 기능은 준비 중입니다.")


# ═══════════════════════════════════════════
# EASY 리포팅: 소재 실적관리
# ═══════════════════════════════════════════
def page_creative_report():
    render_page_header("🎯","소재 실적관리","소재별 실적을 직관적으로 관리하고 ON/OFF를 제어합니다","green")
    st.info("소재 실적관리 기능은 준비 중입니다.")


# ═══════════════════════════════════════════
# EASY 리포팅: 라벨링 리포트
# ═══════════════════════════════════════════
def page_label_report():
    render_page_header("🏷️","라벨링 리포트","제품별/타겟별/퍼널별 라벨링 기반 리포트를 조회합니다","green")
    st.info("라벨링 리포트 기능은 준비 중입니다.")


# ═══════════════════════════════════════════
# 설정: API 키 관리
# ═══════════════════════════════════════════
def page_api_keys():
    render_page_header("🔑","API 키 관리","외부 API 인증 키를 관리합니다","orange")

    st.markdown('<div class="s-header">현재 API 키 상태</div>', unsafe_allow_html=True)

    api_list = [
        ("네이버 데이터랩", "NAVER_DATALAB_ID", "NAVER_DATALAB_SECRET"),
        ("네이버 검색", "NAVER_SEARCH_ID", "NAVER_SEARCH_SECRET"),
        ("네이버 검색광고", "NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY"),
        ("Anthropic (Claude)", "ANTHROPIC_API_KEY", None),
    ]

    for name, key1, key2 in api_list:
        v1 = os.environ.get(key1, "")
        status = "✅ 설정됨" if v1 else "❌ 미설정"
        color = "#059669" if v1 else "#dc2626"
        st.markdown(
            f'<div class="d-item" style="display:flex;justify-content:space-between;align-items:center">'
            f'<span style="font-weight:600">{name}</span>'
            f'<span style="color:{color};font-weight:700;font-size:0.85rem">{status}</span>'
            f'</div>', unsafe_allow_html=True)

    st.markdown("")
    st.caption("API 키는 `.env` 파일(로컬) 또는 Streamlit Cloud Secrets에서 관리합니다.")


# ═══════════════════════════════════════════
# 설정: 경쟁사 DB 관리
# ═══════════════════════════════════════════
def page_competitor_db_mgmt():
    render_page_header("🏢","경쟁사 DB 관리","카테고리별 경쟁사 정보를 추가/수정/삭제합니다","orange")

    competitor_db = load_competitor_db()
    categories = competitor_db.get("categories", {})

    for cat_name, cat_data in categories.items():
        comps = cat_data.get("competitors", [])
        with st.expander(f"📁 {cat_name} ({len(comps)}개)", expanded=False):
            # 현재 경쟁사 뱃지 표시
            if comps:
                st.markdown(" · ".join(f'`{c.get("company","")} {c.get("brand","")}`' for c in comps))
            else:
                st.caption("등록된 경쟁사 없음")

            # 추가 폼
            with st.form(f"cdb_add_{cat_name}"):
                st.markdown("**경쟁사 추가** (회사명, 브랜드, USP를 입력하세요)")
                a1, a2 = st.columns(2)
                with a1:
                    add_company = st.text_input("회사명", key=f"cdb_co_{cat_name}")
                    add_brand = st.text_input("브랜드명", key=f"cdb_br_{cat_name}")
                with a2:
                    add_headline = st.text_input("USP 헤드라인", key=f"cdb_hl_{cat_name}")
                    add_sp = st.text_area("셀링포인트 (줄바꿈 구분)", height=60, key=f"cdb_sp_{cat_name}")
                if st.form_submit_button("추가", type="primary"):
                    if add_company and add_brand:
                        comps.append({
                            "company": add_company, "brand": add_brand,
                            "search_keyword": f"{add_brand} {add_company}",
                            "usp": {"headline": add_headline or add_brand,
                                    "selling_points": [s.strip() for s in add_sp.split("\n") if s.strip()],
                                    "target": "", "key_claim": ""},
                            "channels": [], "price_position": "중", "premium_score": 5, "price_score": 5,
                        })
                        save_competitor_db(competitor_db)
                        st.rerun()

            # 수정/삭제
            if comps:
                st.markdown("**경쟁사 수정/삭제**")
                comp_labels = [f'{c.get("company","")} {c.get("brand","")}' for c in comps]
                sel_idx = st.selectbox("경쟁사 선택", range(len(comps)), format_func=lambda i: comp_labels[i], key=f"cdb_sel_{cat_name}")

                c = comps[sel_idx]
                usp = c.get("usp", {})
                hl = usp.get("headline", "") if isinstance(usp, dict) else str(usp)
                sp = usp.get("selling_points", []) if isinstance(usp, dict) else []
                tgt = usp.get("target", "") if isinstance(usp, dict) else ""

                with st.form(f"cdb_edit_{cat_name}_{sel_idx}"):
                    e1, e2 = st.columns(2)
                    with e1:
                        ed_company = st.text_input("회사명", value=c.get("company",""))
                        ed_brand = st.text_input("브랜드명", value=c.get("brand",""))
                    with e2:
                        ed_headline = st.text_input("USP 헤드라인", value=hl)
                        ed_sp = st.text_area("셀링포인트 (줄바꿈 구분)", value="\n".join(sp), height=60)
                        ed_target = st.text_input("타겟 고객층", value=tgt)
                    bc1, bc2, _ = st.columns([1, 1, 4])
                    with bc1:
                        save_btn = st.form_submit_button("저장", type="primary")
                    with bc2:
                        del_btn = st.form_submit_button("삭제")

                    if save_btn:
                        c["company"] = ed_company
                        c["brand"] = ed_brand
                        c["search_keyword"] = f"{ed_brand} {ed_company}"
                        c["usp"] = {"headline": ed_headline,
                                    "selling_points": [s.strip() for s in ed_sp.split("\n") if s.strip()],
                                    "target": ed_target, "key_claim": ""}
                        save_competitor_db(competitor_db)
                        st.rerun()
                    if del_btn:
                        comps.pop(sel_idx)
                        save_competitor_db(competitor_db)
                        st.rerun()


# ═══════════════════════════════════════════
# 설정: 검색 키워드 관리
# ═══════════════════════════════════════════
def page_keyword_mgmt():
    render_page_header("🔤","검색 키워드 관리","자사/경쟁사/제품/시즌 키워드를 통합 관리합니다","orange")

    trend_kw = load_trend_keywords()

    for cat in ["자사", "경쟁사", "시즌"]:
        keywords = trend_kw.get(cat, [])
        with st.expander(f"📁 {cat} ({len(keywords)}개)", expanded=True):
            # 현재 키워드 표시
            if keywords:
                st.markdown(" · ".join(f'`{kw}`' for kw in keywords))
            else:
                st.caption("키워드 없음")

            # 추가
            with st.form(f"kw_add_{cat}"):
                new_kws = st.text_area("추가할 키워드 (쉼표/줄바꿈 구분)", height=60, key=f"kw_input_{cat}")
                col_add, col_del = st.columns(2)
                with col_add:
                    if st.form_submit_button("추가", type="primary"):
                        import re
                        parsed = [k.strip() for k in re.split(r"[,\n]", new_kws) if k.strip()]
                        for kw in parsed:
                            if kw not in trend_kw[cat]:
                                trend_kw[cat].append(kw)
                        save_trend_keywords(trend_kw)
                        st.rerun()

            # 삭제
            if keywords:
                with st.form(f"kw_del_{cat}"):
                    del_checks = {}
                    for kw in keywords:
                        del_checks[kw] = st.checkbox(kw, key=f"kwdel_{cat}_{kw}")
                    if st.form_submit_button("선택 삭제"):
                        to_del = [kw for kw, v in del_checks.items() if v]
                        trend_kw[cat] = [k for k in trend_kw[cat] if k not in to_del]
                        save_trend_keywords(trend_kw)
                        st.rerun()

    # 제품 카테고리
    product_kws = trend_kw.get("제품", {})
    for pname, pkws in product_kws.items():
        with st.expander(f"📁 제품 > {pname} ({len(pkws)}개)", expanded=False):
            if pkws:
                st.markdown(" · ".join(f'`{kw}`' for kw in pkws))
            with st.form(f"kw_add_prod_{pname}"):
                new_kws = st.text_area("추가 (쉼표/줄바꿈)", height=60, key=f"kw_pinput_{pname}")
                if st.form_submit_button("추가", type="primary"):
                    import re
                    parsed = [k.strip() for k in re.split(r"[,\n]", new_kws) if k.strip()]
                    for kw in parsed:
                        if kw not in pkws:
                            pkws.append(kw)
                    save_trend_keywords(trend_kw)
                    st.rerun()


# ═══════════════════════════════════════════
# 설정: 계정 설정
# ═══════════════════════════════════════════
def page_account():
    render_page_header("👤","계정 설정","사용자 정보 및 알림 설정을 관리합니다","orange")
    st.info("계정 설정 기능은 준비 중입니다.")


# ═══════════════════════════════════════════
# 라우팅
# ═══════════════════════════════════════════
pg = st.session_state["current_page"]
# 심의
if pg=="ai_review": page_ai_review()
elif pg=="review_dashboard": page_review_dashboard()
# EASY 리포팅
elif pg=="creative_report": page_creative_report()
elif pg=="label_report": page_label_report()
# 시장조사
elif pg=="search_query": page_trend()
elif pg=="ad_research": page_adbanner()
elif pg=="competitor": page_competitor()
# 설정
elif pg=="products": page_product_management()
elif pg=="api_keys": page_api_keys()
elif pg=="competitor_db": page_competitor_db_mgmt()
elif pg=="keyword_mgmt": page_keyword_mgmt()
elif pg=="account": page_account()
# 하위 호환 (이전 key)
elif pg=="trend": page_trend()
elif pg=="data": page_data_collection()
elif pg=="usp": page_usp()
elif pg=="adbanner": page_adbanner()

st.markdown('<div class="footer">CKD Insight Radar v1.0 — 성분 기반 트렌드 선점 마케팅 솔루션 · 종근당건강</div>', unsafe_allow_html=True)
