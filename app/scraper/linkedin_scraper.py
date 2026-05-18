"""
Scraper LinkedIn Jobs public (sans connexion)
Essaie deux endpoints selon ce qui répond : guest API puis page publique.
Couvre France, Suisse, Canada.
"""
import re
import json
from typing import List, Dict, Optional
from urllib.parse import urlencode, quote
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from app.scraper.rate_limiter import RateLimiter

# geoId LinkedIn : France=105015875, Suisse=106693272, Canada=101174742
SEARCH_CONFIG = [
    {"region": "France",  "geoId": "105015875", "queries": [
        "stage geomatique",
        "stage SIG cartographie",
        "stage teledetection",
        "stage environnement geospatial",
        "stage amenagement territoire",
        "stage ecologie milieu naturel",
        "stage webmapping",
    ]},
    {"region": "Suisse",  "geoId": "106693272", "queries": [
        "stage geomatique",
        "stage SIG GIS",
        "stage environnement",
        "geomatics internship",
        "stage cartographie",
    ]},
    {"region": "Canada",  "geoId": "101174742", "queries": [
        "geomatics intern",
        "GIS internship",
        "environmental geospatial intern",
        "stage geomatique",
        "remote sensing intern",
    ]},
]

GUEST_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
PUBLIC_URL = "https://www.linkedin.com/jobs/search/"


class LinkedInScraper:

    def __init__(self):
        self.rate_limiter = RateLimiter(min_delay=3.0, max_delay=5.0)

    async def scrape_all_regions(self) -> List[Dict]:
        all_jobs: List[Dict] = []
        seen: set = set()

        for cfg in SEARCH_CONFIG:
            region  = cfg["region"]
            geo_id  = cfg["geoId"]
            queries = cfg["queries"]
            logger.info(f"LinkedIn — {region}")

            for query in queries:
                jobs = await self._scrape_query(query, region, geo_id)
                for job in jobs:
                    if job["url"] not in seen:
                        seen.add(job["url"])
                        all_jobs.append(job)
                await self.rate_limiter.wait()

        logger.info(f"LinkedIn : {len(all_jobs)} offres uniques, récupération des détails...")
        for job in all_jobs:
            details = await self._fetch_job_details(job["url"])
            job.update(details)
            await self.rate_limiter.wait()

        return all_jobs

    async def _scrape_query(self, query: str, region: str, geo_id: str) -> List[Dict]:
        # Attempt 1 — guest API (returns HTML fragment)
        jobs = await self._try_guest_api(query, region, geo_id)
        if jobs:
            logger.info(f"LinkedIn {region} '{query}': {len(jobs)} offres (guest API)")
            return jobs

        # Attempt 2 — public search page (SSR partial)
        jobs = await self._try_public_page(query, region, geo_id)
        if jobs:
            logger.info(f"LinkedIn {region} '{query}': {len(jobs)} offres (page publique)")
        return jobs

    async def _try_guest_api(self, query: str, region: str, geo_id: str) -> List[Dict]:
        jobs: List[Dict] = []
        params = {
            "keywords": query,
            "location": region,
            "geoId": geo_id,
            "f_JT": "I",      # Internship
            "f_TPR": "r2592000",  # derniers 30 jours
            "start": "0",
            "count": "10",
        }
        try:
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True,
                headers=self._headers_api(), verify=False,
            ) as client:
                r = await client.get(GUEST_API, params=params)
                if r.status_code != 200:
                    logger.debug(f"LinkedIn guest API {region}/{query}: HTTP {r.status_code}")
                    return jobs

                soup = BeautifulSoup(r.content, "html.parser")

                # Multiple selectors — LinkedIn change parfois ses classes
                cards = (
                    soup.find_all("div", class_="base-card")
                    or soup.find_all("li", class_=re.compile(r"job-search-card|result-card"))
                    or soup.find_all("div", class_=re.compile(r"job-search-card|base-search-card"))
                    or soup.find_all("article")
                )

                for card in cards[:10]:
                    job = self._parse_card(card, region, query)
                    if job:
                        jobs.append(job)
        except Exception as e:
            logger.debug(f"LinkedIn guest API {region}/{query}: {e}")
        return jobs

    async def _try_public_page(self, query: str, region: str, geo_id: str) -> List[Dict]:
        jobs: List[Dict] = []
        params = {
            "keywords": query,
            "location": region,
            "geoId": geo_id,
            "f_JT": "I",
            "position": "1",
            "pageNum": "0",
        }
        try:
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True,
                headers=self._headers_browser(), verify=False,
            ) as client:
                r = await client.get(PUBLIC_URL, params=params)
                if r.status_code != 200:
                    return jobs

                soup = BeautifulSoup(r.content, "html.parser")

                # Try standard card selectors
                cards = (
                    soup.find_all("div", class_="base-card")
                    or soup.find_all("li", class_=re.compile(r"job-search-card"))
                    or soup.find_all("div", {"data-entity-urn": re.compile(r"jobPosting")})
                )
                for card in cards[:10]:
                    job = self._parse_card(card, region, query)
                    if job:
                        jobs.append(job)

                # Try JSON-LD structured data
                if not jobs:
                    for script in soup.find_all("script", type="application/ld+json"):
                        try:
                            data = json.loads(script.string or "")
                            if isinstance(data, list):
                                for item in data:
                                    job = self._parse_jsonld(item, region, query)
                                    if job:
                                        jobs.append(job)
                            elif isinstance(data, dict):
                                job = self._parse_jsonld(data, region, query)
                                if job:
                                    jobs.append(job)
                        except Exception:
                            continue
        except Exception as e:
            logger.debug(f"LinkedIn public page {region}/{query}: {e}")
        return jobs

    def _parse_card(self, card, region: str, query: str) -> Optional[Dict]:
        try:
            title_tag = (
                card.find("h3", class_=re.compile(r"base-search-card__title|title"))
                or card.find("h3")
                or card.find("h2")
            )
            title = title_tag.get_text(strip=True) if title_tag else ""

            company_tag = (
                card.find("h4", class_=re.compile(r"base-search-card__subtitle|company"))
                or card.find("h4")
                or card.find(class_=re.compile(r"company|employer"))
            )
            company = company_tag.get_text(strip=True) if company_tag else ""

            location_tag = (
                card.find("span", class_=re.compile(r"job-search-card__location|location"))
                or card.find(class_=re.compile(r"location|city"))
            )
            location = location_tag.get_text(strip=True) if location_tag else region

            link_tag = card.find("a", href=re.compile(r"linkedin\.com/jobs/view"))
            if not link_tag:
                link_tag = card.find("a", href=True)
            url = link_tag["href"].split("?")[0] if link_tag and link_tag.get("href") else ""

            if not title or not url:
                return None

            return {
                "title": title,
                "company": company,
                "location": location,
                "description": "",
                "url": url,
                "apply_email": None,
                "apply_url": url,
                "source": "linkedin.com",
                "region": region,
                "search_query": query,
            }
        except Exception:
            return None

    def _parse_jsonld(self, data: dict, region: str, query: str) -> Optional[Dict]:
        try:
            if data.get("@type") not in ("JobPosting",):
                return None
            title   = data.get("title", "").strip()
            company = data.get("hiringOrganization", {}).get("name", "")
            loc_obj = data.get("jobLocation", {})
            if isinstance(loc_obj, list):
                loc_obj = loc_obj[0] if loc_obj else {}
            location = loc_obj.get("address", {}).get("addressLocality", region)
            url = data.get("url", "") or data.get("@id", "")
            description = re.sub(r"<[^>]+>", "", data.get("description", ""))[:600]

            if not title or not url:
                return None

            return {
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": url,
                "apply_email": None,
                "apply_url": url,
                "source": "linkedin.com",
                "region": region,
                "search_query": query,
            }
        except Exception:
            return None

    async def _fetch_job_details(self, url: str) -> Dict:
        details: Dict = {"description": "", "apply_email": None}
        try:
            async with httpx.AsyncClient(
                timeout=20, follow_redirects=True,
                headers=self._headers_browser(), verify=False,
            ) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return details
                soup = BeautifulSoup(r.content, "html.parser")

                desc_div = (
                    soup.find("div", class_=re.compile(r"description|show-more-less"))
                    or soup.find("section", class_=re.compile(r"description"))
                )
                if desc_div:
                    details["description"] = re.sub(r"\s+", " ", desc_div.get_text(strip=True))[:800]

                text = soup.get_text()
                for em in re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text):
                    if not any(ig in em.lower() for ig in ["linkedin", "example", "noreply", "sentry", "google"]):
                        details["apply_email"] = em
                        break

                # Lien "Apply on company website" (ATS externe : Greenhouse, Lever, Workday...)
                if not details.get("apply_email"):
                    for a in soup.find_all("a", href=True):
                        href = a.get("href", "")
                        if href and "linkedin.com" not in href and any(
                            kw in href for kw in [
                                "greenhouse.io", "lever.co", "bamboohr.com",
                                "workday.com", "myworkdayjobs.com", "breezy.hr",
                                "teamtailor.com", "taleo.net", "icims.com",
                                "/careers/", "/jobs/apply", "/apply/",
                            ]
                        ):
                            details["apply_url"] = href
                            break
        except Exception as e:
            logger.debug(f"LinkedIn details ({url}): {e}")
        return details

    def _headers_api(self) -> Dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.linkedin.com/jobs/search/",
        }

    def _headers_browser(self) -> Dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
