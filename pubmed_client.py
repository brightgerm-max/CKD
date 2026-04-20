"""PubMed E-utilities API 클라이언트 — 논문 검색 및 상세 조회"""

import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search_pubmed(query: str, max_results: int = 20, days_back: int = 365) -> list[str]:
    """PubMed에서 키워드로 논문 검색, PMID 목록 반환."""
    min_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    max_date = datetime.now().strftime("%Y/%m/%d")

    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "date",
        "retmode": "json",
        "datetype": "pdat",
        "mindate": min_date,
        "maxdate": max_date,
    }
    resp = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data["esearchresult"]["idlist"]


def fetch_article_details(pmids: list[str]) -> list[dict]:
    """PMID 목록으로 논문 상세 정보(제목, 초록, 저널 등) 조회."""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }
    resp = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=15)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    articles = []

    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", "")
        title = article.findtext(".//ArticleTitle", "")

        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(
            (a.text or "") for a in abstract_parts
        )

        year = article.findtext(".//PubDate/Year", "")
        month = article.findtext(".//PubDate/Month", "")
        day = article.findtext(".//PubDate/Day", "")
        journal = article.findtext(".//Journal/Title", "")

        # MeSH terms
        mesh_terms = [
            m.findtext("DescriptorName", "")
            for m in article.findall(".//MeshHeading")
        ]

        # Keywords
        keywords = [
            k.text or ""
            for k in article.findall(".//Keyword")
        ]

        pub_date = f"{year}"
        if month:
            pub_date += f"-{month}"
        if day:
            pub_date += f"-{day}"

        articles.append({
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "pub_date": pub_date,
            "journal": journal,
            "mesh_terms": mesh_terms,
            "keywords": keywords,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return articles


# 종근당 제품별 PubMed 검색 쿼리
INGREDIENT_QUERIES = {
    "콘드로이친 (Chondroitin)": (
        '("chondroitin"[tiab] OR "Chondroitin Sulfates"[MeSH]) '
        'AND ("supplement"[tiab] OR "joint"[tiab] OR "cartilage"[tiab] OR "osteoarthritis"[tiab])'
    ),
    "포스파티딜세린 (Phosphatidylserine)": (
        '("phosphatidylserine"[tiab] OR "Phosphatidylserines"[MeSH]) '
        'AND ("supplement"[tiab] OR "cognit*"[tiab] OR "memory"[tiab] OR "brain"[tiab])'
    ),
    "비피더스유산균 (Probiotics)": (
        '("bifidobacterium"[tiab] OR "Bifidobacterium"[MeSH] OR "probiotics"[tiab] OR "Probiotics"[MeSH]) '
        'AND ("supplement"[tiab] OR "gut"[tiab] OR "health"[tiab])'
    ),
    "루테인 (Lutein)": (
        '("lutein"[tiab] OR "Lutein"[MeSH]) '
        'AND ("supplement"[tiab] OR "eye"[tiab] OR "macular"[tiab] OR "vision"[tiab])'
    ),
    "오메가3 (Omega-3)": (
        '("omega-3"[tiab] OR "Fatty Acids, Omega-3"[MeSH] OR "EPA"[tiab] OR "DHA"[tiab]) '
        'AND ("supplement"[tiab] OR "cardiovascular"[tiab] OR "triglyceride"[tiab])'
    ),
    "밀크씨슬 (Milk Thistle)": (
        '("milk thistle"[tiab] OR "silymarin"[tiab] OR "Silymarin"[MeSH]) '
        'AND ("supplement"[tiab] OR "liver"[tiab] OR "hepato*"[tiab])'
    ),
    "콜라겐 (Collagen)": (
        '("collagen"[tiab] AND "supplement"[tiab]) '
        'AND ("skin"[tiab] OR "wrinkle"[tiab] OR "derma*"[tiab])'
    ),
    "칼슘 비타민D (Calcium Vitamin D)": (
        '("calcium"[tiab] OR "Calcium"[MeSH]) AND ("vitamin D"[tiab] OR "Vitamin D"[MeSH]) '
        'AND ("supplement"[tiab] OR "bone"[tiab] OR "osteoporosis"[tiab])'
    ),
    "홍국 (Red Yeast Rice)": (
        '("red yeast rice"[tiab] OR "monacolin"[tiab] OR "Monascus"[tiab]) '
        'AND ("cholesterol"[tiab] OR "lipid"[tiab] OR "supplement"[tiab])'
    ),
    "비타민C (Vitamin C)": (
        '("vitamin C"[tiab] OR "ascorbic acid"[tiab] OR "Ascorbic Acid"[MeSH]) '
        'AND ("supplement"[tiab] OR "immune"[tiab] OR "antioxidant"[tiab])'
    ),
    "쏘팔메토 (Saw Palmetto)": (
        '("saw palmetto"[tiab] OR "Serenoa"[MeSH]) '
        'AND ("prostate"[tiab] OR "BPH"[tiab] OR "urinary"[tiab] OR "supplement"[tiab])'
    ),
    "크랜베리 (Cranberry)": (
        '("cranberry"[tiab] OR "Vaccinium macrocarpon"[tiab] OR "proanthocyanidin"[tiab]) '
        'AND ("urinary"[tiab] OR "UTI"[tiab] OR "supplement"[tiab])'
    ),
    "가르시니아 (Garcinia)": (
        '("garcinia"[tiab] OR "hydroxycitric acid"[tiab] OR "HCA"[tiab]) '
        'AND ("weight"[tiab] OR "body fat"[tiab] OR "obesity"[tiab] OR "supplement"[tiab])'
    ),
}


def search_all_ingredients(max_per_ingredient: int = 10, days_back: int = 365) -> dict[str, list[dict]]:
    """모든 성분에 대해 PubMed 검색 실행."""
    results = {}
    for name, query in INGREDIENT_QUERIES.items():
        pmids = search_pubmed(query, max_results=max_per_ingredient, days_back=days_back)
        time.sleep(0.4)
        articles = fetch_article_details(pmids)
        results[name] = articles
        time.sleep(0.4)
    return results


if __name__ == "__main__":
    print("=== PubMed 성분별 최신 논문 검색 ===\n")
    all_results = search_all_ingredients(max_per_ingredient=3, days_back=365)
    for ingredient, articles in all_results.items():
        print(f"\n{'='*60}")
        print(f"  {ingredient} — {len(articles)}건")
        print(f"{'='*60}")
        for a in articles:
            print(f"  [{a['pmid']}] {a['title']}")
            print(f"    Journal: {a['journal']} | Date: {a['pub_date']}")
            print(f"    URL: {a['url']}")
            print()
