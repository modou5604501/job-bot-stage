"""
Scraper France Travail (ex Pôle Emploi)
- Mode API officielle (OAuth2) si france_travail_client_id + secret configurés dans .env
- Mode fallback Adzuna FR si adzuna_app_id + adzuna_app_key configurés dans .env
- Sinon : retourne 0 (LinkedIn couvre déjà la France via linkedin_scraper)
Inscription gratuite France Travail : https://francetravail.io
Inscription gratuite Adzuna : https://developer.adzuna.com
"""
import re
from typing import List, Dict, Optional
import httpx
from loguru import logger
from app.scraper.rate_limiter import RateLimiter

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
API_URL   = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

API_QUERIES = [
    "geomatique",
    "SIG cartographie",
    "teledetection",
    "systeme information geographique",
    "analyse spatiale",
    "qgis arcgis",
    "environnement geospatial",
    "amenagement territoire SIG",
    "geomatics",
    "remote sensing",
    "lidar drone",
    "webmapping",
    "gestion risques naturels",
]

ADZUNA_QUERIES = [
    "stage geomatique",
    "stage SIG",
    "stage teledetection",
    "stage cartographie",
    "stage environnement geospatial",
    "stage qgis",
    "stage arcgis",
    "stage amenagement territoire",
    "stage analyse spatiale",
    "stage geomatics",
    "stage remote sensing",
    "stage ecologie SIG",
    "stage hydrologie",
    "stage gestion risques",
    "stage webmapping",
]


class FranceTravailScraper:

    def __init__(self, settings=None):
        self.settings = settings
        self.rate_limiter = RateLimiter(min_delay=1.5, max_delay=2.5)
        self._token: Optional[str] = None

    async def scrape_all(self) -> List[Dict]:
        has_ft_creds = (
            self.settings
            and getattr(self.settings, "france_travail_client_id", None)
            and getattr(self.settings, "france_travail_client_secret", None)
        )
        if has_ft_creds:
            jobs = await self._scrape_with_api()
            if jobs:
                logger.info(f"France Travail API : {len(jobs)} offres")
                return jobs

        # Fallback : Adzuna FR (si credentials)
        has_adzuna = (
            self.settings
            and getattr(self.settings, "adzuna_app_id", None)
            and getattr(self.settings, "adzuna_app_key", None)
        )
        if has_adzuna:
            jobs = await self._scrape_adzuna_fr()
            if jobs:
                logger.info(f"France (Adzuna fallback) : {len(jobs)} offres")
                return jobs

        # Ni France Travail ni Adzuna configurés — LinkedIn couvre la France
        logger.info(
            "France Travail : aucune clé API configurée. "
            "Pour activer : ajouter france_travail_client_id/secret dans .env "
            "(inscription gratuite sur https://francetravail.io) "
            "ou adzuna_app_id/adzuna_app_key (https://developer.adzuna.com)."
        )
        return []

    # ── API officielle OAuth2 ─────────────────────────────────────────────

    async def _get_token(self) -> Optional[str]:
        if self._token:
            return self._token
        try:
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                r = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.settings.france_travail_client_id,
                        "client_secret": self.settings.france_travail_client_secret,
                        "scope": "api_offresdemploiv2 o2dsoffre",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if r.status_code == 200:
                    self._token = r.json().get("access_token")
                    logger.info("France Travail : token OAuth2 OK")
                    return self._token
                logger.warning(f"France Travail token : HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"France Travail token : {e}")
        return None

    async def _scrape_with_api(self) -> List[Dict]:
        token = await self._get_token()
        if not token:
            return []

        all_jobs: List[Dict] = []
        seen: set = set()

        for query in API_QUERIES:
            for start in [0, 20]:
                jobs = await self._api_query(query, token, start)
                for job in jobs:
                    uid = job.get("url", "")
                    if uid not in seen:
                        seen.add(uid)
                        all_jobs.append(job)
            await self.rate_limiter.wait()

        # Enrichir les jobs sans email avec le detail complet (entreprise.url, urlPostulation)
        no_email = [j for j in all_jobs if not j.get("apply_email")]
        if no_email and token:
            logger.info(f"France Travail : detail complet pour {len(no_email)} jobs sans email...")
            for job in no_email:
                offre_id = job["url"].split("/")[-1]
                detail = await self._fetch_detail(offre_id, token)
                if detail:
                    self._enrich_from_detail(job, detail)
                await self.rate_limiter.wait()

        return all_jobs

    async def _fetch_detail(self, offre_id: str, token: str) -> Optional[Dict]:
        """Fetche le detail complet d'une offre (contact, entreprise.url)."""
        try:
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                r = await client.get(
                    f"https://api.francetravail.io/partenaire/offresdemploi/v2/offres/{offre_id}",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                if r.status_code == 200:
                    return r.json()
        except Exception as e:
            logger.debug(f"France Travail detail {offre_id}: {e}")
        return None

    def _enrich_from_detail(self, job: Dict, detail: Dict):
        """Enrichit un job depuis le detail complet : email, company_url, urlPostulation."""
        contact = detail.get("contact", {})

        # Email direct dans les coordonnees
        if not job.get("apply_email"):
            for field in ["courriel", "coordonnees1", "coordonnees2", "coordonnees3"]:
                val = contact.get(field, "") or ""
                if "@" in val:
                    job["apply_email"] = val.strip()
                    break

        # urlPostulation : peut etre mailto: ou HTTP
        url_post = contact.get("urlPostulation", "") or ""
        if not job.get("apply_email") and url_post.startswith("mailto:"):
            job["apply_email"] = url_post.replace("mailto:", "").split("?")[0].strip()
        elif url_post and not url_post.startswith("mailto:"):
            job["apply_url"] = url_post  # URL externe → sera scrappe par guesser

        # Site web de l'entreprise (meme pour employeur anonyme)
        company_url = detail.get("entreprise", {}).get("url", "") or ""
        if company_url:
            job["company_url"] = company_url
            if not job.get("company"):
                job["company"] = detail.get("entreprise", {}).get("nom", "") or ""

    async def _api_query(self, query: str, token: str, start: int = 0) -> List[Dict]:
        jobs: List[Dict] = []
        params = {
            "motsCles": query,
            "typeContrat": "ST",     # ST = stage (code API v2 officiel)
            "range": f"{start}-{start + 19}",
        }
        try:
            async with httpx.AsyncClient(timeout=20, verify=False) as client:
                r = await client.get(
                    API_URL,
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                if r.status_code != 200:
                    logger.debug(f"France Travail API '{query}' @{start}: HTTP {r.status_code}")
                    return jobs
                for offre in r.json().get("resultats", []):
                    job = self._parse_api_offre(offre, query)
                    if job:
                        jobs.append(job)
        except Exception as e:
            logger.debug(f"France Travail API '{query}': {e}")
        return jobs

    def _parse_api_offre(self, offre: Dict, query: str) -> Optional[Dict]:
        try:
            offre_id = offre.get("id", "")
            title = offre.get("intitule", "").strip()
            if not title:
                return None
            company  = offre.get("entreprise", {}).get("nom", "")
            location = offre.get("lieuTravail", {}).get("libelle", "France")
            description = offre.get("description", "")[:800]
            url      = f"https://candidat.francetravail.fr/offres/recherche/detail/{offre_id}"
            apply_url = offre.get("origineOffre", {}).get("urlOrigine", url)

            apply_email = None
            for field in ["coordonnees1", "coordonnees2", "coordonnees3", "courriel"]:
                val = offre.get("contact", {}).get(field, "")
                if val and "@" in val:
                    apply_email = val.strip()
                    break

            return {
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": url,
                "apply_email": apply_email,
                "apply_url": apply_url,
                "source": "francetravail.fr",
                "region": "France",
                "search_query": query,
            }
        except Exception:
            return None

    # ── Fallback : Adzuna FR (si credentials disponibles) ────────────────

    async def _scrape_adzuna_fr(self) -> List[Dict]:
        """Utilise Adzuna API pour les offres françaises (inscription gratuite)"""
        from urllib.parse import quote as _quote
        jobs: List[Dict] = []
        seen: set = set()
        app_id  = self.settings.adzuna_app_id
        app_key = self.settings.adzuna_app_key

        for query in ADZUNA_QUERIES[:10]:  # limiter les requetes
            url = (
                f"https://api.adzuna.com/v1/api/jobs/fr/search/1"
                f"?app_id={app_id}&app_key={app_key}"
                f"&results_per_page=20&what={_quote(query)}"
                f"&content-type=application/json"
            )
            try:
                async with httpx.AsyncClient(timeout=20, verify=False) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        for item in r.json().get("results", []):
                            job = self._parse_adzuna(item, query)
                            if job and job["url"] not in seen:
                                seen.add(job["url"])
                                jobs.append(job)
                await self.rate_limiter.wait()
            except Exception as e:
                logger.debug(f"Adzuna FR '{query}': {e}")

        return jobs

    def _parse_adzuna(self, item: dict, query: str) -> Optional[Dict]:
        try:
            title    = item.get("title", "").strip()
            url      = item.get("redirect_url", "").strip()
            company  = item.get("company", {}).get("display_name", "")
            location = item.get("location", {}).get("display_name", "France")
            description = re.sub(r"<[^>]+>", "", item.get("description", ""))[:600]
            if not title or not url:
                return None
            return {
                "title": title, "company": company, "location": location,
                "description": description, "url": url, "apply_email": None,
                "apply_url": url, "source": "adzuna.com (FR)",
                "region": "France", "search_query": query,
            }
        except Exception:
            return None
