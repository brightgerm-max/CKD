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
from naver_client import fetch_search_trend, search_tv_health_news
from mfds_client import search_health_food
from clinicaltrials_client import search_clinical_trials
from price_client import search_product_prices

# ─── 경로 & 데이터 ───
DATA_DIR = Path(__file__).parent / "data"

def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_product_db(data):
    with open(DATA_DIR / "product_ingredient_db.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_products():
    return load_json("product_ingredient_db.json")

def load_competitor_db():
    return load_json("competitor_db.json")

def load_tv_data():
    return load_json("sample_tv_data.json")

def load_regulatory_data():
    return load_json("sample_regulatory_data.json")

# ─── 페이지 설정 ───
st.set_page_config(page_title="CKD Insight Radar", page_icon="🔬", layout="wide", initial_sidebar_state="expanded")

# ─── 글로벌 CSS ───
st.markdown("""
<style>
/* ── 전체 ── */
.stApp { background: #f0f4f8; }
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
    color: #7a94af !important;
    text-align: left !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
    margin: 1px 0 !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.06) !important;
    color: #cdd9e5 !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.4) !important;
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
.sidebar-hr { border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 12px 16px; }
.sidebar-label { font-size: 0.68rem !important; font-weight: 700 !important; color: #3d5a73 !important; text-transform: uppercase; letter-spacing: 1.5px; padding: 8px 16px 4px; }
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
.pg-title { font-size: 1.5rem; font-weight: 800; color: #0f172a; }
.pg-desc  { font-size: 0.88rem; color: #64748b; margin-top: 2px; }

/* ── 카드 시스템 ── */
.g-card {
    background: linear-gradient(160deg, #ffffff 0%, #f8fafd 100%);
    border: 1px solid #e2e8f0; border-radius: 16px;
    padding: 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    transition: all 0.2s; position: relative; overflow: hidden;
}
.g-card::after {
    content: ""; position: absolute; top: 0; right: 0; width: 120px; height: 120px;
    background: radial-gradient(circle at top right, rgba(37,99,235,0.03) 0%, transparent 70%);
    pointer-events: none;
}
.g-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.07); transform: translateY(-1px); }
.g-card-header {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.95rem; font-weight: 700; color: #1e293b;
    margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #eef2f7;
}
.g-card-badge {
    margin-left: auto; font-size: 0.72rem; font-weight: 700;
    padding: 3px 10px; border-radius: 20px;
}
.g-badge-blue   { background: #eff6ff; color: #2563eb; }
.g-badge-green  { background: #ecfdf5; color: #059669; }
.g-badge-yellow { background: #fffbeb; color: #d97706; }
.g-badge-gray   { background: #f1f5f9; color: #64748b; }

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
.p-card:hover { border-color: #93c5fd; box-shadow: 0 8px 24px rgba(37,99,235,0.12); transform: translateY(-3px); }
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
    background: linear-gradient(160deg, #ffffff 0%, #f5f7fb 100%);
    border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 20px 14px; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    position: relative; overflow: hidden;
}
.m-card::before {
    content: ""; position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #e2e8f0, #cbd5e1);
}
.m-card:nth-child(1)::before { background: linear-gradient(90deg, #1e293b, #475569); }
.m-card:nth-child(2)::before { background: linear-gradient(90deg, #2563eb, #60a5fa); }
.m-card:nth-child(3)::before { background: linear-gradient(90deg, #059669, #34d399); }
.m-card:nth-child(4)::before { background: linear-gradient(90deg, #ea580c, #fb923c); }
.m-val { font-size: 2rem; font-weight: 800; color: #0f172a; line-height: 1; }
.m-lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 6px; font-weight: 500; }
.m-val-blue   { color: #2563eb; }
.m-val-green  { color: #059669; }
.m-val-orange { color: #ea580c; }

/* ── 데이터 아이템 ── */
.d-item {
    padding: 13px 16px; border-radius: 12px;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    margin-bottom: 8px; border: 1px solid #eef2f7;
    transition: all 0.15s; border-left: 3px solid #cbd5e1;
}
.d-item:hover { background: linear-gradient(135deg, #eef2f7 0%, #e8edf3 100%); border-left-color: #2563eb; }
.d-title { font-size: 0.88rem; font-weight: 600; color: #1e293b; line-height: 1.4; margin-bottom: 3px; }
.d-meta  { font-size: 0.76rem; color: #94a3b8; }
.d-link  { font-size: 0.76rem; color: #2563eb; text-decoration: none; font-weight: 500; }
.d-link:hover { text-decoration: underline; }

/* ── 섹션 헤더 ── */
.s-header {
    font-size: 1.05rem; font-weight: 700; color: #0f172a;
    padding: 14px 20px; margin: 24px 0 16px;
    background: linear-gradient(90deg, #e0ecff 0%, #eff6ff 40%, transparent 100%);
    border-left: 4px solid #2563eb; border-radius: 0 12px 12px 0;
    box-shadow: 0 1px 4px rgba(37,99,235,0.06);
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
.ing-pill:hover { border-color: #93c5fd; box-shadow: 0 6px 16px rgba(37,99,235,0.12); transform: translateY(-2px); }
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
.footer { text-align: center; color: #94a3b8; font-size: 0.78rem; padding: 30px 0 12px; }

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
MENU_ITEMS = [
    {"key": "products",   "icon": "📦", "label": "자사 상품관리"},
    {"key": "data",       "icon": "📡", "label": "데이터 수집"},
    {"key": "usp",        "icon": "🎯", "label": "상품 USP 도출"},
    {"key": "competitor", "icon": "🔍", "label": "경쟁사 모니터링"},
]

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "products"

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
        f'<hr class="sidebar-hr">'
        f'<div class="sidebar-label">메뉴</div>',
        unsafe_allow_html=True,
    )

    for item in MENU_ITEMS:
        is_active = st.session_state["current_page"] == item["key"]
        btn_label = f'{item["icon"]}  {item["label"]}'
        if st.button(btn_label, key=f"nav_{item['key']}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state["current_page"] = item["key"]
            st.rerun()

    st.markdown(
        '<hr class="sidebar-hr"><div class="sidebar-label">모니터링 소스</div>',
        unsafe_allow_html=True,
    )
    for name, on in [("PubMed",True),("ClinicalTrials.gov",True),("식약처 공지",True),("TV 건강 프로그램",True),("네이버 데이터랩",True)]:
        dot = "sidebar-dot sidebar-dot-on" if on else "sidebar-dot sidebar-dot-off"
        st.markdown(f'<div class="sidebar-src"><span class="{dot}"></span> {name}</div>', unsafe_allow_html=True)

    st.markdown('<hr class="sidebar-hr"><div class="sidebar-ver">v1.0 — 종근당건강 제안용</div>', unsafe_allow_html=True)

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
        st.warning(f"'{product['category']}' 카테고리의 경쟁사 데이터가 준비되지 않았습니다.")
        return

    competitors = cat_data.get("competitors",[])
    ckd = cat_data.get("ckd_position",{})

    st.markdown(f'<div class="s-header">⚔️ "{product["brand"]}" 카테고리 USP 비교</div>', unsafe_allow_html=True)

    # 실시간 가격 수집
    comp_price_key = f"comp_prices_{product['brand']}"
    if comp_price_key not in st.session_state:
        with st.spinner("네이버 쇼핑에서 실시간 가격을 조회하고 있습니다..."):
            prices = {}
            # 자사
            prices["ckd"] = search_product_prices(f"종근당 {product['brand']}", brand_keywords=["종근당","종근당건강","ckd","ckdmall"])
            # 경쟁사 — 각 회사명을 자사몰 키워드로
            for c in competitors:
                prices[c["brand"]] = search_product_prices(f"{c['brand']} {c['company']}", brand_keywords=[c["company"], c["brand"]])
            st.session_state[comp_price_key] = prices

    prices = st.session_state[comp_price_key]

    def _price_chip(label, color, item, fallback_url=None):
        """채널 가격 칩 HTML."""
        if item and item.get("daily_price", 0) > 0:
            return (f'<a href="{item["link"]}" target="_blank" style="text-decoration:none;display:inline-block;margin:3px">'
                    f'<div style="background:{color};color:#fff;padding:6px 12px;border-radius:10px;font-size:0.78rem;font-weight:700;display:inline-block">{label}</div>'
                    f'<div style="margin-top:2px;text-align:center">'
                    f'<span style="font-weight:800;font-size:0.95rem">{item["price"]:,}원</span>'
                    f'<br><span style="font-size:0.72rem;color:#64748b">({item["quantity"]}) 1일 {item["daily_price"]:,}원</span>'
                    f'</div></a>')
        elif item:
            return (f'<a href="{item["link"]}" target="_blank" style="text-decoration:none;display:inline-block;margin:3px">'
                    f'<div style="background:{color};color:#fff;padding:6px 12px;border-radius:10px;font-size:0.78rem;font-weight:700;display:inline-block">{label}</div>'
                    f'<div style="margin-top:2px;text-align:center"><span style="font-weight:800;font-size:0.95rem">{item["price"]:,}원</span></div></a>')
        elif fallback_url:
            return (f'<a href="{fallback_url}" target="_blank" style="text-decoration:none;display:inline-block;margin:3px">'
                    f'<div style="background:{color};opacity:0.5;color:#fff;padding:6px 12px;border-radius:10px;font-size:0.78rem;font-weight:700;display:inline-block">{label}</div>'
                    f'<div style="margin-top:2px;text-align:center;font-size:0.75rem;color:#94a3b8">검색 →</div></a>')
        return ""

    def _price_html(price_data):
        """채널별 가격 HTML 생성."""
        nv = price_data["naver"][0] if price_data["naver"] else None
        cp = price_data["coupang"][0] if price_data["coupang"] else None
        br = price_data["brand"][0] if price_data["brand"] else None
        cp_url = price_data.get("coupang_search_url", "#")
        br_url = price_data.get("brand_search_url", "#")
        html = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px">'
        html += _price_chip("네이버", "#03c75a", nv)
        html += _price_chip("쿠팡", "#ef4444", cp, cp_url)
        html += _price_chip("자사몰", "#2563eb", br, br_url)
        html += '</div>'
        return html

    def _get_usp_details(usp_data):
        """USP 데이터가 문자열이든 객체든 통일된 형태로 반환."""
        if isinstance(usp_data, dict):
            return usp_data
        return {"headline": usp_data or "", "selling_points": [], "target": "", "key_claim": ""}

    def _usp_selling_html(usp_info, dark=False):
        """셀링포인트 HTML."""
        html = ""
        sp = usp_info.get("selling_points", [])
        if sp:
            color = "rgba(255,255,255,0.7)" if dark else "#475569"
            for point in sp:
                html += f'<div style="font-size:0.82rem;color:{color};padding:3px 0;line-height:1.5">• {point}</div>'
        target = usp_info.get("target", "")
        key_claim = usp_info.get("key_claim", "")
        if target or key_claim:
            tc = "rgba(255,255,255,0.45)" if dark else "#94a3b8"
            parts = []
            if target:
                parts.append(f'🎯 {target}')
            if key_claim:
                parts.append(f'💎 {key_claim}')
            html += f'<div style="font-size:0.75rem;color:{tc};margin-top:6px">{" · ".join(parts)}</div>'
        return html

    # 자사 USP 카드 + 가격
    ckd_prices = prices.get("ckd", {"naver":[],"coupang":[],"brand":[]})
    ckd_usp = _get_usp_details(ckd.get("usp", ""))
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:16px;padding:20px;margin-bottom:16px;color:#fff">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
        f'<div><span style="font-size:1.1rem;font-weight:800">종근당 {product["brand"]}</span>'
        f'<span style="background:rgba(37,99,235,0.3);padding:3px 10px;border-radius:20px;font-size:0.75rem;margin-left:8px">자사</span></div></div>'
        f'<div style="background:rgba(255,255,255,0.08);border-radius:12px;padding:14px 16px;font-size:1rem;font-weight:600;margin-bottom:10px">'
        f'💡 {ckd_usp.get("headline","")}</div>'
        f'{_usp_selling_html(ckd_usp, dark=True)}'
        f'{_price_html(ckd_prices)}'
        f'</div>', unsafe_allow_html=True)

    # 경쟁사 USP 카드들 + 가격
    for c in competitors:
        c_prices = prices.get(c["brand"], {"naver":[],"coupang":[],"brand":[]})
        c_usp = _get_usp_details(c.get("usp", ""))
        st.markdown(
            f'<div style="background:linear-gradient(160deg,#ffffff,#f8fafd);border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;margin-bottom:10px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
            f'<div><span style="font-size:0.95rem;font-weight:700;color:#1e293b">{c["company"]}</span>'
            f'<span style="color:#64748b;font-weight:500;margin-left:6px">{c["brand"]}</span>'
            f'<span style="background:#fef2f2;color:#ef4444;padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:600;margin-left:8px">경쟁사</span></div></div>'
            f'<div style="background:#f8fafc;border-left:3px solid #ef4444;border-radius:0 10px 10px 0;padding:10px 14px;font-size:0.92rem;font-weight:600;color:#1e293b;margin-bottom:8px">'
            f'{c_usp.get("headline","")}</div>'
            f'{_usp_selling_html(c_usp)}'
            f'{_price_html(c_prices)}'
            f'</div>', unsafe_allow_html=True)

    st.markdown("")

    # 1일당 가격 비교 차트
    with st.container(border=True):
        st.markdown("**💰 1일당 가격 비교** _(네이버 쇼핑 실시간 데이터 · 동일 단위 환산)_")
        chart_data = []
        all_brands = [("종근당 " + product["brand"], "ckd")] + [(f"{c['brand']}", c["brand"]) for c in competitors]
        for brand_label, price_key in all_brands:
            pd_data = prices.get(price_key, {"naver":[],"coupang":[],"brand":[]})
            for ch_name, ch_key in [("네이버", "naver"), ("쿠팡", "coupang"), ("자사몰", "brand")]:
                if pd_data[ch_key] and pd_data[ch_key][0].get("daily_price", 0) > 0:
                    chart_data.append({"브랜드": brand_label[:10], "채널": ch_name, "1일당 가격": pd_data[ch_key][0]["daily_price"]})

        if chart_data:
            fig_price = px.bar(
                pd.DataFrame(chart_data), x="브랜드", y="1일당 가격", color="채널", barmode="group",
                color_discrete_map={"네이버":"#03c75a","쿠팡":"#ef4444","자사몰":"#2563eb"},
                text="1일당 가격",
            )
            fig_price.update_traces(texttemplate="%{text:,}원/일", textposition="outside", textfont_size=10)
            fig_price.update_layout(
                height=350, margin=dict(t=20,b=20,l=20,r=20),
                yaxis=dict(title="1일당 가격 (원)", gridcolor="#f1f5f9"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
            )
            st.plotly_chart(fig_price, use_container_width=True)
        else:
            st.caption("가격 데이터를 가져올 수 없습니다.")

    st.markdown('<div class="s-header">💡 자사 차별화 포인트</div>', unsafe_allow_html=True)
    for i, pt in enumerate(cat_data.get("differentiation",[])):
        st.markdown(f'<div class="diff-c"><b>{i+1}.</b> {pt}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════
# 라우팅
# ═══════════════════════════════════════════
pg = st.session_state["current_page"]
if pg=="products": page_product_management()
elif pg=="data": page_data_collection()
elif pg=="usp": page_usp()
elif pg=="competitor": page_competitor()

st.markdown('<div class="footer">CKD Insight Radar v1.0 — 성분 기반 트렌드 선점 마케팅 솔루션 · 종근당건강</div>', unsafe_allow_html=True)
