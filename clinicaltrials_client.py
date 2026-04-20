"""ClinicalTrials.gov API 클라이언트 — 임상시험 검색"""

import requests


def search_clinical_trials(keyword: str, max_results: int = 10) -> list[dict]:
    """
    ClinicalTrials.gov API v2로 키워드 검색.
    반환: [{"nct_id", "title", "status", "phase", "conditions", "url"}, ...]
    """
    try:
        resp = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={
                "query.term": keyword,
                "pageSize": max_results,
                "sort": "LastUpdatePostDate:desc",
                "fields": "NCTId,BriefTitle,OverallStatus,Phase,Condition,StartDate,CompletionDate",
                "format": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for study in data.get("studies", []):
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            cond_mod = proto.get("conditionsModule", {})

            nct_id = ident.get("nctId", "")
            results.append({
                "nct_id": nct_id,
                "title": ident.get("briefTitle", ""),
                "status": status_mod.get("overallStatus", ""),
                "phase": ", ".join(design.get("phases", [])) if design.get("phases") else "N/A",
                "conditions": ", ".join(cond_mod.get("conditions", [])[:3]) if cond_mod.get("conditions") else "",
                "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
            })
        return results

    except Exception:
        return []


if __name__ == "__main__":
    print("=== ClinicalTrials.gov 검색: 'probiotics gut health' ===\n")
    trials = search_clinical_trials("probiotics gut health supplement", max_results=5)
    for i, t in enumerate(trials):
        print(f"{i+1}. [{t['status']}] {t['title']}")
        print(f"   Phase: {t['phase']} | {t['conditions']}")
        print(f"   {t['url']}")
        print()
