"""
Scraper JobTeaser — plateforme de stages pour etudiants en Europe.
Tente plusieurs strategies pour contourner la protection WAF/Cloudflare :
  1. API publique de recherche (endpoint JSON)
  2. Page HTML avec parsing BeautifulSoup
  3. Retourne 0 proprement si tout est bloque (les offres JS-rendues sont inaccessibles)
"""
import re
import json
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from app.scraper.rate_limiter import RateLimiter

BASE = "https://www.jobteaser.com"

QUERIES_FR = [
    "geomatique",
    "SIG cartographie",
    "teledetection",
    "analyse spatiale",
    "environnement SIG",
    "geomatics",
]

QUERIES_EN = [
    "geomatics internship",
    "GIS internship",
    "remote sensing internship",
    "spatial analysis",
    "environmental GIS",
]

LANG_CONFIG = [
    {"lang": "fr", "region": "France",   "queries": QUERIES_FR, "contract": "Stage"},
    {"lang": "en", "region": "Suisse",   "queries": QUERIES_EN, "contract": "Internship"},
    {"lang": "en", "region": "Europe",   "queries": QUERIES_EN, "contract": "Internship"},
]


class JobTeaserScraper:

    def __init__(self):
        self.rate_limiter = RateLimiter(min_delay=3.0, max_delay=6.0)

    def _headers(self, lang: str = "fr") -> Dict:
        accept_lang = "fr-FR,fr;q=0.9,en;q=0.8" if lang == "fr" else "en-US,en;q=0.9,fr;q=0.8"
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": accept_lang,
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

    async def scrape_all(self) -> List[Dict]:
        all_jobs: List[Dict] = []
        seen: set = set()

        for cfg in LANG_CONFIG:
            lang    = cfg["lang"]
            region  = cfg["region"]
            queries = cfg["queries"]

            for query in queries:
                jobs = await self._scrape_query(query, lang, region)
                for job in jobs:
                    if job["url"] not in seen:
                        seen.add(job["url"])
                        all_jobs.append(job)
                await self.rate_limiter.wait()

        if all_jobs:
            logger.info(f"JobTeaser : {len(all_jobs)} offres uniques")
        else:
            logger.info(
                "JobTeaser : 0 offres (site protege par WAF/Cloudflare — "
                "les offres JS-rendues sont inaccessibles sans navigateur)"
            )
        return all_jobs

    async def _scrape_query(self, query: str, lang: str, region: str) -> List[Dict]:
        """Essaie plusieurs strategies pour une requete donnee."""
        jobs = await self._try_html(query, lang, region)
        if jobs:
            logger.info(f"JobTeaser '{query}' ({region}): {len(jobs)} offres")
        return jobs

    async def _try_html(self, query: str, lang: str, region: str) -> List[Dict]:
        """Tente de parser la page HTML de resultats."""
        jobs: List[Dict] = []
        prefix = "fr" if lang == "fr" else "en"
        path = "offres-demploi" if lang == "fr" else "job-offers"
        url = f"{BASE}/{prefix}/{path}"
        params = {"keywords": query}

        try:
            async with httpx.AsyncClient(
                timeout=20, verify=False, follow_redirects=True,
                headers=self._headers(lang),
            ) as client:
                r = await client.get(url, params=params)
                if r.status_code != 200:
                    logger.debug(f"JobTeaser HTML {region}/{query}: HTTP {r.status_code}")
                    return jobs

                soup = BeautifulSoup(r.content, "html.parser")

                # Essai 1 : articles/cards avec attribut data-*
                cards = (
                    soup.find_all("article", attrs={"data-id": True})
                    or soup.find_all("li", class_=re.compile(r"job|offer|card", re.I))
                    or soup.find_all("div", class_=re.compile(r"JobCard|job-card|offer-card", re.I))
                )

                for card in cards:
                    job = self._parse_card(card, region, query)
                    if job:
                        jobs.append(job)

                # Essai 2 : JSON-LD structure
                if not jobs:
                    for script in soup.find_all("script", type="application/ld+json"):
                        try:
                            data = json.loads(script.string or "")
                            items = data if isinstance(data, list) else [data]
                            for item in items:
                                if item.get("@type") == "JobPosting":
                                    job = self._parse_jsonld(item, region, query)
                                    if job:
                                        jobs.append(job)
                        except Exception:
                            continue

                # Essai 3 : __NEXT_DATA__ (Next.js)
                if not jobs:
                    next_data_tag = soup.find("script", id="__NEXT_DATA__")
                    if next_data_tag:
                        try:
                            nd = json.loads(next_data_tag.string or "{}")
                            offers = (
                                nd.get("props", {}).get("pageProps", {}).get("jobOffers", [])
                                or nd.get("props", {}).get("pageProps", {}).get("offers", [])
                                or nd.get("props", {}).get("pageProps", {}).get("jobs", [])
                            )
                            for offer in offers:
                                job = self._parse_next_item(offer, region, query)
                                if job:
                                    jobs.append(job)
                        except Exception:
                            pass

        except Exception as e:
            logger.debug(f"JobTeaser HTML {region}/{query}: {e}")
        return jobs

    def _parse_card(self, card, region: str, query: str) -> Optional[Dict]:
        try:
            title_tag = card.find(["h2", "h3", "h4", "a"], class_=re.compile(r"title|name|job", re.I))
            title = title_tag.get_text(strip=True) if title_tag else ""
            company_tag = card.find(class_=re.compile(r"company|employer|organization", re.I))
            company = company_tag.get_text(strip=True) if company_tag else ""
            loc_tag = card.find(class_=re.compile(r"location|city|lieu", re.I))
            location = loc_tag.get_text(strip=True) if loc_tag else region
            link_tag = card.find("a", href=True)
            href = link_tag["href"] if link_tag else ""
            if href and not href.startswith("http"):
                href = BASE + href
            if not title or not href:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": "", "url": href.split("?")[0],
                "apply_email": None, "apply_url": href,
                "source": "jobteaser.com", "region": region, "search_query": query,
            }
        except Exception:
            return None

    def _parse_jsonld(self, data: dict, region: str, query: str) -> Optional[Dict]:
        try:
            title = data.get("title", "").strip()
            url = data.get("url", "") or data.get("@id", "")
            company = data.get("hiringOrganization", {}).get("name", "")
            loc = data.get("jobLocation", {})
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            location = loc.get("address", {}).get("addressLocality", region)
            desc = re.sub(r"<[^>]+>", "", data.get("description", ""))[:600]
            if not title or not url:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": desc, "url": url.split("?")[0],
                "apply_email": None, "apply_url": url,
                "source": "jobteaser.com", "region": region, "search_query": query,
            }
        except Exception:
            return None

    def _parse_next_item(self, item: dict, region: str, query: str) -> Optional[Dict]:
        try:
            title = (item.get("title") or item.get("name") or "").strip()
            slug = item.get("slug") or item.get("id") or ""
            url = f"{BASE}/en/job-offers/{slug}" if slug else ""
            company = (item.get("company") or {}).get("name", "") if isinstance(item.get("company"), dict) else str(item.get("company") or "")
            location = item.get("city") or item.get("location") or region
            desc = item.get("description") or item.get("shortDescription") or ""
            if not title or not url:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": str(desc)[:600], "url": url,
                "apply_email": None, "apply_url": url,
                "source": "jobteaser.com", "region": region, "search_query": query,
            }
        except Exception:
            return None
