"""
Scraper HH.ru — offres de stage en Russie
API publique JSON: api.hh.ru/vacancies
Cible: stages geomatique, SIG, environnement, teledetection
"""
import re
from typing import List, Dict
from urllib.parse import urlencode
import httpx
from loguru import logger
from app.scraper.rate_limiter import RateLimiter

# API publique HH.ru — pas d'authentification requise
API_URL = "https://api.hh.ru/vacancies"

# Termes de recherche (anglais + russe)
QUERIES = [
    # Anglais (filtres par employment=probation)
    "GIS intern",
    "geomatics intern",
    "cartography intern",
    "remote sensing intern",
    "spatial analysis",
    "geospatial analyst",
    # Russe — termes plus precis
    "\u043a\u0430\u0440\u0442\u043e\u0433\u0440\u0430\u0444\u0438\u044f \u0441\u0442\u0430\u0436\u0435\u0440",  # cartographie stagiaire
    "\u0433\u0435\u043e\u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0442\u0438\u043a\u0430 \u0441\u0442\u0430\u0436\u0435\u0440",  # geoinformatique stagiaire
    "\u0433\u0435\u043e\u0434\u0435\u0437\u0438\u044f \u0441\u0442\u0443\u0434\u0435\u043d\u0442",  # geodesie etudiant
    "\u044d\u043a\u043e\u043b\u043e\u0433\u0438\u044f \u0441\u0442\u0430\u0436\u0435\u0440",  # ecologie stagiaire
]

# Villes russes principales (area IDs HH.ru)
# 113 = Russie entiere, 1 = Moscou, 2 = Saint-Petersbourg
AREAS = [113]  # Toute la Russie


class HHScraper:
    """Scrape les offres de stage sur HH.ru (Russie)"""

    def __init__(self):
        self.rate_limiter = RateLimiter(min_delay=1.5, max_delay=3.0)

    async def scrape_all(self) -> List[Dict]:
        all_jobs = []
        seen_ids = set()

        for query in QUERIES:
            for area in AREAS:
                jobs = await self._scrape_query(query, area)
                for job in jobs:
                    jid = job.get("url", "")
                    if jid not in seen_ids:
                        seen_ids.add(jid)
                        all_jobs.append(job)
                await self.rate_limiter.wait()

        logger.info(f"HH.ru : {len(all_jobs)} offres uniques trouvees")
        return all_jobs

    async def _scrape_query(self, query: str, area: int) -> List[Dict]:
        jobs = []
        # Pour les requetes anglaises, filtrer par employment=probation (stage)
        # Pour les requetes russes, laisser plus large (le triage filtrera)
        is_russian = any(ord(c) > 127 for c in query)
        params = {
            "text": query,
            "area": area,
            "per_page": 10,
        }
        if not is_russian:
            params["employment"] = "probation"
        url = f"{API_URL}?{urlencode(params)}"

        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers=self._headers(),
                verify=False,
            ) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return jobs

                data = r.json()
                items = data.get("items", [])

                for item in items:
                    job = self._parse_item(item, query)
                    if job:
                        jobs.append(job)

                if items:
                    logger.info(f"HH.ru '{query}': {len(items)} offres trouvees")

        except Exception as e:
            logger.debug(f"HH.ru erreur '{query}': {e}")

        return jobs

    def _parse_item(self, item: Dict, query: str) -> Dict:
        try:
            title = item.get("name", "")
            company = item.get("employer", {}).get("name", "")
            area = item.get("area", {}).get("name", "Russie")
            url = item.get("alternate_url", "")
            vacancy_id = item.get("id", "")

            # Salaire
            salary = item.get("salary")
            salary_str = ""
            if salary:
                currency = salary.get("currency", "RUB")
                frm = salary.get("from")
                to = salary.get("to")
                if frm or to:
                    salary_str = f"{frm or ''}-{to or ''} {currency}"

            # Description courte
            snippet = item.get("snippet", {})
            description = " ".join(filter(None, [
                snippet.get("requirement", ""),
                snippet.get("responsibility", ""),
            ]))
            description = re.sub(r'<[^>]+>', ' ', description)  # Retirer HTML
            description = re.sub(r'\s+', ' ', description).strip()

            if not title or not url:
                return None

            return {
                "title": title,
                "company": company,
                "location": f"{area}, Russie",
                "description": description[:600],
                "url": url,
                "apply_email": None,
                "apply_url": url,
                "source": "hh.ru",
                "region": "Russie",
                "search_query": query,
                "salary": salary_str,
            }
        except Exception:
            return None

    def _headers(self) -> Dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
