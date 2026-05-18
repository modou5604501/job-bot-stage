"""
Scraper Google Jobs via python-jobspy.
Utilise le moteur de recherche Google Jobs (udm=8) pour trouver des stages.
Note: Google peut retourner 0 si la detection bot est active ce cycle-la.
"""
import asyncio
import urllib3
import warnings
from typing import List, Dict
from loguru import logger
from app.scraper.rate_limiter import RateLimiter

warnings.filterwarnings("ignore")
urllib3.disable_warnings()

QUERIES_CA = [
    "geomatics intern",
    "GIS internship",
    "stage geomatique",
    "remote sensing intern",
    "spatial analyst internship",
    "cartography internship",
    "environmental GIS intern",
    "stage SIG cartographie",
]

QUERIES_FR = [
    "stage geomatique",
    "stage SIG",
    "stage teledetection",
    "stage cartographie environnement",
    "stage analyste SIG",
    "internship geomatics France",
]

QUERIES_CH = [
    "stage geomatique Suisse",
    "geomatics internship Switzerland",
    "GIS internship Switzerland",
    "stage SIG Suisse",
]

SEARCH_CONFIG = [
    {"region": "Canada",  "location": "Canada",      "queries": QUERIES_CA},
    {"region": "France",  "location": "France",      "queries": QUERIES_FR},
    {"region": "Suisse",  "location": "Switzerland", "queries": QUERIES_CH},
]


def _patch_ssl():
    """Patch SSL global pour que jobspy fonctionne sur Windows."""
    try:
        import requests
        original_send = requests.Session.send
        def _send_no_verify(self, req, **kw):
            kw["verify"] = False
            return original_send(self, req, **kw)
        requests.Session.send = _send_no_verify
    except Exception:
        pass


def _scrape_sync(query: str, location: str, region: str) -> List[Dict]:
    """Appel synchrone a jobspy.scrape_jobs (enveloppe pour asyncio.to_thread)."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        return []
    try:
        df = scrape_jobs(
            site_name=["google"],
            search_term=query,
            location=location,
            results_wanted=15,
            hours_old=168,   # derniere semaine
        )
        if df is None or df.empty:
            return []
        jobs = []
        for _, row in df.iterrows():
            url = str(row.get("job_url") or "")
            title = str(row.get("title") or "").strip()
            if not title or not url:
                continue
            jobs.append({
                "title":        title,
                "company":      str(row.get("company") or ""),
                "location":     str(row.get("location") or location),
                "description":  str(row.get("description") or "")[:800],
                "url":          url,
                "apply_email":  None,
                "apply_url":    str(row.get("job_url_direct") or url),
                "source":       "google.com/jobs",
                "region":       region,
                "search_query": query,
            })
        return jobs
    except Exception as e:
        logger.debug(f"Google Jobs '{query}' @ {location}: {e}")
        return []


class GoogleJobsScraper:

    def __init__(self):
        self.rate_limiter = RateLimiter(min_delay=4.0, max_delay=8.0)
        _patch_ssl()

    async def scrape_all(self) -> List[Dict]:
        all_jobs: List[Dict] = []
        seen: set = set()
        total = 0

        for cfg in SEARCH_CONFIG:
            region   = cfg["region"]
            location = cfg["location"]
            queries  = cfg["queries"]

            for query in queries:
                jobs = await asyncio.to_thread(_scrape_sync, query, location, region)
                for job in jobs:
                    if job["url"] not in seen:
                        seen.add(job["url"])
                        all_jobs.append(job)
                        total += 1
                await self.rate_limiter.wait()

        if total > 0:
            logger.info(f"Google Jobs : {total} offres uniques")
        else:
            logger.info(
                "Google Jobs : 0 offres (detection bot active ce cycle — "
                "les resultats varient d'un cycle a l'autre)"
            )
        return all_jobs
