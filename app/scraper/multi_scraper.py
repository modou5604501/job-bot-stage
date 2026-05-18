"""
Scraper multi-sources :
- Indeed France / Suisse / Canada  (RSS — contourne l'anti-scraping)
- Welcome to the Jungle            (JSON interne)
- jobs.ch / jobup.ch               (Suisse)
- studentjob.fr                    (stages France étudiants)
- Hellowork France                 (HTML)
- Euraxess Europe                  (HTML)
- Adzuna API                       (optionnel, FR + CH + CA, clé gratuite)
"""
import re
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from urllib.parse import urlencode, quote
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from app.scraper.rate_limiter import RateLimiter

INDEED_NS = "http://www.indeed.com/about/rss"

# ── Requêtes par source ───────────────────────────────────────────────────

INDEED_FR_QUERIES = [
    "stage geomatique",
    "stage SIG",
    "stage teledetection",
    "stage cartographie",
    "stage environnement geospatial",
    "stage qgis arcgis",
    "stage amenagement territoire",
    "stage analyse spatiale",
    "stage remote sensing",
    "stage ecologie environnement",
    "stage hydrologie",
    "stage webmapping",
]

INDEED_CH_QUERIES = [
    "stage geomatique",
    "stage SIG",
    "geomatics internship",
    "stage environnement",
    "stage cartographie",
    "GIS intern",
]

INDEED_CA_QUERIES = [
    "geomatics intern",
    "GIS internship",
    "remote sensing intern",
    "environmental GIS intern",
    "spatial analysis intern",
    "stage geomatique",
    "geospatial analyst intern",
]

WTTJ_QUERIES = [
    "geomatique",
    "SIG cartographie",
    "teledetection",
    "environnement SIG",
    "amenagement territoire",
    "geomatics",
    "GIS environment",
    "cartographie",
    "remote sensing",
    "analyse spatiale",
]

HELLOWORK_QUERIES = [
    "stage geomatique",
    "stage SIG cartographie",
    "stage teledetection",
    "stage environnement geospatial",
    "stage qgis",
    "stage arcgis",
    "stage analyse spatiale",
]

EURAXESS_QUERIES = [
    "geomatics",
    "GIS remote sensing",
    "environmental mapping",
    "spatial analysis",
    "cartography",
    "teledetection",
    "geographic information systems",
]

JOBS_CH_QUERIES = [
    "geomatics",
    "SIG GIS",
    "cartographie",
    "geographie",
    "teledetection",
    "environnement geospatial",
    "analyse spatiale",
]

JOBUP_QUERIES = [
    "geomatique",
    "SIG",
    "cartographie",
    "teledetection",
    "environnement",
    "geomatics",
    "GIS",
]

STUDENTJOB_QUERIES = [
    "geomatique",
    "SIG",
    "cartographie",
    "teledetection",
    "environnement",
    "qgis",
    "arcgis",
]

ADZUNA_QUERIES = {
    "fr": ["stage geomatique", "stage SIG", "stage teledetection",
           "stage cartographie", "stage environnement", "stage qgis"],
    "ch": ["stage geomatique", "geomatics intern", "stage SIG",
           "stage environnement", "stage cartographie"],
    "ca": ["geomatics intern", "GIS intern", "remote sensing intern",
           "environmental GIS", "spatial analysis intern"],
}


class MultiScraper:

    def __init__(self, settings=None):
        self.settings = settings  # needed for optional Adzuna API credentials
        self.rate_limiter = RateLimiter(min_delay=2.0, max_delay=3.5)

    async def scrape_all(self) -> List[Dict]:
        sources = [
            ("Indeed FR (RSS)",      self._scrape_indeed_rss("fr")),
            ("Indeed CH (RSS)",      self._scrape_indeed_rss("ch")),
            ("Indeed CA (RSS)",      self._scrape_indeed_rss("ca")),
            ("Welcome to the Jungle", self._scrape_wttj()),
            ("jobs.ch Suisse",       self._scrape_jobs_ch()),
            ("jobup.ch Suisse",      self._scrape_jobup()),
            ("StudentJob France",    self._scrape_studentjob()),
            ("Hellowork France",     self._scrape_hellowork()),
            ("Euraxess Europe",      self._scrape_euraxess()),
        ]
        if (self.settings
                and getattr(self.settings, "adzuna_app_id", None)
                and getattr(self.settings, "adzuna_app_key", None)):
            sources.append(("Adzuna FR/CH/CA", self._scrape_adzuna()))

        all_jobs: List[Dict] = []
        for name, coro in sources:
            try:
                jobs = await coro
                if jobs:
                    logger.info(f"{name} : {len(jobs)} offres")
                all_jobs.extend(jobs)
            except Exception as e:
                logger.warning(f"{name} indisponible : {e}")

        seen: set = set()
        unique: List[Dict] = []
        for job in all_jobs:
            if job["url"] not in seen:
                seen.add(job["url"])
                unique.append(job)

        return unique

    # ── Indeed RSS (FR / CH / CA) ─────────────────────────────────────────

    async def _scrape_indeed_rss(self, country: str) -> List[Dict]:
        domain_map = {
            "fr": ("https://fr.indeed.com/rss", "France",  INDEED_FR_QUERIES),
            "ch": ("https://ch.indeed.com/rss", "Suisse",  INDEED_CH_QUERIES),
            "ca": ("https://ca.indeed.com/rss", "Canada",  INDEED_CA_QUERIES),
        }
        base_url, region, queries = domain_map[country]
        jobs: List[Dict] = []
        seen: set = set()

        for query in queries:
            rss_url = f"{base_url}?q={quote(query)}&sort=date&fromage=60"
            try:
                async with httpx.AsyncClient(
                    timeout=20, follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"},
                    verify=False,
                ) as client:
                    r = await client.get(rss_url)
                    if r.status_code == 200:
                        root = ET.fromstring(r.content)
                        for item in root.findall(".//item"):
                            job = self._parse_indeed_rss_item(item, query, region, country)
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"Indeed {country.upper()} RSS '{query}': {e}")

        return jobs

    def _parse_indeed_rss_item(self, item, query: str, region: str, country: str) -> Optional[Dict]:
        try:
            title = item.findtext("title", "").strip()
            url   = item.findtext("link", "").strip()
            if not title or not url:
                return None

            description = re.sub(r"<[^>]+>", "", item.findtext("description", ""))[:600].strip()
            company  = item.findtext(f"{{{INDEED_NS}}}company", "").strip()
            city     = item.findtext(f"{{{INDEED_NS}}}city", "").strip()
            state    = item.findtext(f"{{{INDEED_NS}}}state", "").strip()
            location = f"{city}, {state}".strip(", ") or region

            if not company and " - " in title:
                parts = title.split(" - ")
                if len(parts) >= 2:
                    company = parts[-2].strip()
                    title   = parts[0].strip()

            source_map = {"fr": "fr.indeed.com", "ch": "ch.indeed.com", "ca": "ca.indeed.com"}
            return {
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": url,
                "apply_email": None,
                "apply_url": url,
                "source": source_map.get(country, "indeed.com"),
                "region": region,
                "search_query": query,
            }
        except Exception:
            return None

    # ── Welcome to the Jungle ─────────────────────────────────────────────

    async def _scrape_wttj(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()
        base = "https://www.welcometothejungle.com/fr/jobs"

        for query in WTTJ_QUERIES:
            params = {"query": query, "contract_type[]": "internship", "page": "1"}
            url = f"{base}?{urlencode(params)}"
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers=self._headers("fr"), verify=False,
                ) as client:
                    r = await client.get(url)
                    if r.status_code != 200:
                        await self.rate_limiter.wait()
                        continue

                    soup = BeautifulSoup(r.content, "html.parser")

                    # Try to extract Next.js pre-rendered JSON
                    next_data_tag = soup.find("script", id="__NEXT_DATA__")
                    if next_data_tag and next_data_tag.string:
                        try:
                            nd = json.loads(next_data_tag.string)
                            items = (
                                nd.get("props", {}).get("pageProps", {})
                                  .get("jobs", {}).get("data", [])
                                or nd.get("props", {}).get("pageProps", {})
                                     .get("results", {}).get("jobs", [])
                                or []
                            )
                            for item in items[:8]:
                                job = self._parse_wttj_json(item, query)
                                if job and job["url"] not in seen:
                                    seen.add(job["url"])
                                    jobs.append(job)
                        except Exception:
                            pass

                    # Fallback HTML parsing
                    if not jobs:
                        cards = (
                            soup.find_all("li", {"data-testid": re.compile("search-results-list-item")})
                            or soup.find_all("article")
                            or soup.find_all("li", class_=re.compile(r"job|result|card", re.I))
                        )
                        for card in cards[:8]:
                            job = self._parse_wttj_card(card, query)
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)

                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"WTTJ '{query}': {e}")

        return jobs

    def _parse_wttj_json(self, item: dict, query: str) -> Optional[Dict]:
        try:
            title   = item.get("name", "") or item.get("title", "")
            company = item.get("organization", {}).get("name", "") if isinstance(item.get("organization"), dict) else ""
            slug    = item.get("slug", "")
            org_slug = item.get("organization", {}).get("slug", "") if isinstance(item.get("organization"), dict) else ""
            url = f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{slug}" if slug else ""
            location = item.get("office", {}).get("city", "France") if isinstance(item.get("office"), dict) else "France"
            description = re.sub(r"<[^>]+>", "", item.get("description", ""))[:600]
            if not title or not url:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": description, "url": url, "apply_email": None,
                "apply_url": url, "source": "welcometothejungle.com",
                "region": "France", "search_query": query,
            }
        except Exception:
            return None

    def _parse_wttj_card(self, card, query: str) -> Optional[Dict]:
        try:
            title_tag = card.find(["h2", "h3", "h4", "span"], class_=re.compile(r"title|name|job", re.I))
            title = title_tag.get_text(strip=True) if title_tag else ""
            company_tag = card.find(["span", "p"], class_=re.compile(r"company|employer|org", re.I))
            company = company_tag.get_text(strip=True) if company_tag else ""
            link = card.find("a", href=True)
            url = link["href"] if link else ""
            if url and not url.startswith("http"):
                url = f"https://www.welcometothejungle.com{url}"
            if not title or not url:
                return None
            return {
                "title": title, "company": company, "location": "France",
                "description": "", "url": url, "apply_email": None,
                "apply_url": url, "source": "welcometothejungle.com",
                "region": "France", "search_query": query,
            }
        except Exception:
            return None

    # ── jobs.ch (Suisse) ──────────────────────────────────────────────────

    async def _scrape_jobs_ch(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()
        base = "https://www.jobs.ch/en/vacancies/"

        for query in JOBS_CH_QUERIES:
            params = {"term": query, "location": "Switzerland", "sort": "date"}
            url = f"{base}?{urlencode(params)}"
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers=self._headers("de"), verify=False,
                ) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.content, "html.parser")
                        cards = (
                            soup.find_all("article", class_=re.compile(r"vacancy|job|result", re.I))
                            or soup.find_all("div", class_=re.compile(r"vacancy-teaser|job-item", re.I))
                            or soup.find_all("li", class_=re.compile(r"vacancy|job", re.I))
                        )
                        for card in cards[:8]:
                            job = self._parse_generic_card(card, query, "jobs.ch", "Suisse", "https://www.jobs.ch")
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"jobs.ch '{query}': {e}")

        return jobs

    # ── jobup.ch (Suisse) ─────────────────────────────────────────────────

    async def _scrape_jobup(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()
        base = "https://www.jobup.ch/fr/emplois/"

        for query in JOBUP_QUERIES:
            params = {"term": query, "nfr": "1", "sort": "1"}   # nfr=1 = stage/apprentissage
            url = f"{base}?{urlencode(params)}"
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers=self._headers("fr"), verify=False,
                ) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.content, "html.parser")
                        cards = (
                            soup.find_all("article", class_=re.compile(r"job|offer|result", re.I))
                            or soup.find_all("div", class_=re.compile(r"job-item|listing-item", re.I))
                            or soup.find_all("li", class_=re.compile(r"job|result", re.I))
                        )
                        for card in cards[:8]:
                            job = self._parse_generic_card(card, query, "jobup.ch", "Suisse", "https://www.jobup.ch")
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"jobup.ch '{query}': {e}")

        return jobs

    # ── StudentJob France ─────────────────────────────────────────────────

    async def _scrape_studentjob(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()
        base = "https://www.studentjob.fr/stage"

        for query in STUDENTJOB_QUERIES:
            params = {"q": query, "type": "stage"}
            url = f"{base}?{urlencode(params)}"
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers=self._headers("fr"), verify=False,
                ) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.content, "html.parser")
                        cards = (
                            soup.find_all("article", class_=re.compile(r"job|offer|vacature|stage", re.I))
                            or soup.find_all("div", class_=re.compile(r"job-card|offer-card|listing", re.I))
                            or soup.find_all("li", class_=re.compile(r"job|stage", re.I))
                        )
                        for card in cards[:8]:
                            job = self._parse_generic_card(card, query, "studentjob.fr", "France", "https://www.studentjob.fr")
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"StudentJob '{query}': {e}")

        return jobs

    # ── Hellowork France ──────────────────────────────────────────────────

    async def _scrape_hellowork(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()

        for query in HELLOWORK_QUERIES:
            # URL format correct pour Hellowork
            encoded_q = query.replace(" ", "-").lower()
            url = f"https://www.hellowork.com/fr-fr/emplois/recherche.html?k={quote(query)}&c=stage"
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers=self._headers("fr"), verify=False,
                ) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.content, "html.parser")
                        cards = (
                            soup.find_all("article", attrs={"data-id": True})
                            or soup.find_all("li", class_=re.compile(r"job|offer|result", re.I))
                            or soup.find_all("div", class_=re.compile(r"job-card|offer-card", re.I))
                        )
                        for card in cards[:8]:
                            job = self._parse_generic_card(card, query, "hellowork.com", "France", "https://www.hellowork.com")
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"Hellowork '{query}': {e}")

        return jobs

    # ── Euraxess Europe ───────────────────────────────────────────────────

    async def _scrape_euraxess(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()
        base = "https://euraxess.ec.europa.eu/jobs/search"

        for query in EURAXESS_QUERIES:
            params = {"query": query, "f[0]": "type:traineeship"}
            url = f"{base}?{urlencode(params)}"
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers=self._headers("fr"), verify=False,
                ) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.content, "html.parser")
                        items = (
                            soup.find_all("div", class_=re.compile(r"job-item|views-row|result", re.I))
                            or soup.find_all("article", class_=re.compile(r"job|result"))
                            or soup.find_all("li", class_=re.compile(r"views-row|job"))
                        )
                        for item in items[:6]:
                            job = self._parse_euraxess_item(item, query)
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"Euraxess '{query}': {e}")

        return jobs

    def _parse_euraxess_item(self, item, query: str) -> Optional[Dict]:
        try:
            title_tag = item.find(["h2", "h3", "a"])
            title = title_tag.get_text(strip=True) if title_tag else ""
            link = item.find("a", href=True)
            href = link["href"] if link else ""
            url = f"https://euraxess.ec.europa.eu{href}" if href.startswith("/") else href
            loc_tag = item.find(class_=re.compile(r"location|country|place", re.I))
            location = loc_tag.get_text(strip=True) if loc_tag else "Europe"
            company_tag = item.find(class_=re.compile(r"institution|employer|org", re.I))
            company = company_tag.get_text(strip=True) if company_tag else ""
            if not title or not url or len(title) < 5:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": "", "url": url, "apply_email": None,
                "apply_url": url, "source": "euraxess.ec.europa.eu",
                "region": "Europe", "search_query": query,
            }
        except Exception:
            return None

    # ── Adzuna API (optionnel) ────────────────────────────────────────────

    async def _scrape_adzuna(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen: set = set()
        app_id  = self.settings.adzuna_app_id
        app_key = self.settings.adzuna_app_key
        country_map = {"fr": "France", "ch": "Suisse", "ca": "Canada"}

        for country, queries in ADZUNA_QUERIES.items():
            region = country_map[country]
            for query in queries:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                    f"?app_id={app_id}&app_key={app_key}"
                    f"&results_per_page=20&what={quote(query)}"
                    f"&what_exclude=CDI+CDD&content-type=application/json"
                )
                try:
                    async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=False) as client:
                        r = await client.get(url)
                        if r.status_code == 200:
                            data = r.json()
                            for item in data.get("results", []):
                                job = self._parse_adzuna(item, query, region)
                                if job and job["url"] not in seen:
                                    seen.add(job["url"])
                                    jobs.append(job)
                    await self.rate_limiter.wait()
                except Exception as e:
                    logger.debug(f"Adzuna {country}/{query}: {e}")

        return jobs

    def _parse_adzuna(self, item: dict, query: str, region: str) -> Optional[Dict]:
        try:
            title   = item.get("title", "").strip()
            url     = item.get("redirect_url", "").strip()
            company = item.get("company", {}).get("display_name", "")
            location = item.get("location", {}).get("display_name", region)
            description = re.sub(r"<[^>]+>", "", item.get("description", ""))[:600]
            if not title or not url:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": description, "url": url, "apply_email": None,
                "apply_url": url, "source": "adzuna.com",
                "region": region, "search_query": query,
            }
        except Exception:
            return None

    # ── Génériques ────────────────────────────────────────────────────────

    def _parse_generic_card(self, card, query: str, source: str, region: str, base_url: str) -> Optional[Dict]:
        try:
            title_tag = (
                card.find(["h2", "h3", "h4"], class_=re.compile(r"title|name|job", re.I))
                or card.find(["h2", "h3", "h4"])
            )
            title = title_tag.get_text(strip=True) if title_tag else ""

            link = card.find("a", href=True)
            url = link["href"] if link else ""
            if url and not url.startswith("http"):
                url = f"{base_url}{url}" if url.startswith("/") else f"{base_url}/{url}"

            company_tag = card.find(class_=re.compile(r"company|employer|recruteur", re.I))
            company = company_tag.get_text(strip=True) if company_tag else ""

            loc_tag = card.find(class_=re.compile(r"location|city|lieu", re.I))
            location = loc_tag.get_text(strip=True) if loc_tag else region

            if not title or not url or len(title) < 5:
                return None

            return {
                "title": title, "company": company, "location": location,
                "description": "", "url": url, "apply_email": None,
                "apply_url": url, "source": source,
                "region": region, "search_query": query,
            }
        except Exception:
            return None

    def _headers(self, lang: str = "fr") -> Dict:
        accept_lang = "fr-FR,fr;q=0.9,en;q=0.8" if lang == "fr" else "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7"
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": accept_lang,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }
