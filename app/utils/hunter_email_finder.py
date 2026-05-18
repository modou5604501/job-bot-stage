"""
Hunter.io Email Finder — enrichissement automatique des emails RH manquants.
Pour chaque offre sans apply_email, tente de trouver un email RH via Hunter.io.
API gratuite : 25 recherches/mois (inscription sur https://hunter.io)
Configurer dans .env : HUNTER_IO_API_KEY=votre_cle
"""
import re
from typing import Dict, List, Optional
import httpx
from loguru import logger

HUNTER_API = "https://api.hunter.io/v2"

# Roles RH/recrutement a privilegier dans les resultats Hunter.io
HR_ROLES = {
    "recruiter", "recruiting", "recruitment", "rh", "hr", "human resources",
    "talent", "careers", "career", "hiring", "people", "intern", "stage",
    "campus", "university", "student",
}


_AGGREGATORS = {
    "linkedin.com", "indeed.com", "jobbank.gc.ca", "google.com",
    "hh.ru", "francetravail.fr", "candidat.francetravail.fr",
    "adzuna.com", "jobteaser.com", "monster.com", "glassdoor.com",
    "workopolis.com", "eluta.ca", "emploiquebec.gouv.qc.ca",
    "gouvernement.qc.ca", "canada.ca", "gc.ca",
}


def _extract_domain(company_name: str, url: str) -> Optional[str]:
    """
    Extrait le domaine de l'entreprise depuis son URL.
    Si l'URL vient d'un agregateur, tente de deviner le domaine depuis le nom.
    """
    from urllib.parse import urlparse
    # 1. Domaine direct depuis l'URL de l'offre
    try:
        host = urlparse(url).hostname or ""
        if host and not any(agg in host for agg in _AGGREGATORS):
            return re.sub(r"^www\.", "", host)
    except Exception:
        pass

    # 2. Deviner depuis le nom de l'entreprise (pour les agregateurs)
    if not company_name:
        return None
    # Nettoyage : retire les formes juridiques et termes generiques
    name = company_name.lower()
    for suffix in [
        " inc.", " inc", " corp.", " corp", " ltd.", " ltd", " llc",
        " s.a.s", " s.a.s.", " s.a.r.l", " sarl", " s.a.", " sa",
        " gmbh", " ag", " pty", " services", " solutions", " group",
        " groupe", " canada", " québec", " quebec", " international",
        " technologies", " technology", " consulting", " conseil",
    ]:
        name = name.replace(suffix, "")
    name = re.sub(r"[^a-z0-9]", "", name).strip()
    if len(name) < 3:
        return None
    return f"{name}.com"  # Essai principal — Hunter.io verifie lui-meme


def _is_hr_email(email_data: dict) -> bool:
    """Verifie si un email est lie au recrutement."""
    position = (email_data.get("position") or "").lower()
    dept = (email_data.get("department") or "").lower()
    return any(role in position or role in dept for role in HR_ROLES)


class HunterEmailFinder:
    """Trouve les emails RH manquants via Hunter.io API."""

    MONTHLY_CAP = 60  # marge de securite sous la limite gratuite de 75/mois

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache: Dict[str, Optional[str]] = {}  # domain -> email trouvé
        self._quota_exceeded = False
        self._calls_this_session = 0

    async def enrich_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """
        Enrichit les offres sans apply_email en cherchant un email RH via Hunter.io.
        Modifie les offres en place et retourne la liste enrichie.
        """
        if self._quota_exceeded:
            logger.warning("Hunter.io : quota depasse — enrichissement desactive pour ce cycle")
            return jobs

        enriched = 0
        for job in jobs:
            if self._quota_exceeded:
                break
            if job.get("apply_email"):
                continue  # Deja un email direct, pas besoin

            url = job.get("apply_url") or job.get("url") or ""
            domain = _extract_domain(job.get("company", ""), url)
            if not domain:
                continue

            email = await self._find_hr_email(domain, job.get("company", ""))
            if email:
                job["apply_email"] = email
                enriched += 1
                logger.info(
                    f"Hunter.io : email RH trouve pour {job.get('company', '')} "
                    f"-> {email}"
                )

        if enriched > 0:
            logger.info(f"Hunter.io : {enriched} emails RH ajoutes aux offres")
        return jobs

    async def _find_hr_email(self, domain: str, company: str) -> Optional[str]:
        """Cherche un email RH pour un domaine donne."""
        if self._quota_exceeded:
            return None
        if domain in self._cache:
            return self._cache[domain]
        if self._calls_this_session >= self.MONTHLY_CAP:
            logger.warning(f"Hunter.io : cap session atteint ({self.MONTHLY_CAP} req) — pause")
            self._quota_exceeded = True
            return None

        email = None
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                r = await client.get(
                    f"{HUNTER_API}/domain-search",
                    params={
                        "domain": domain,
                        "api_key": self.api_key,
                        "type": "personal",
                        "limit": 10,
                    },
                )
                self._calls_this_session += 1

                if r.status_code == 200:
                    data = r.json().get("data", {})
                    emails = data.get("emails", [])

                    # Priorite 1 : emails RH/recrutement
                    for e in emails:
                        if _is_hr_email(e) and e.get("confidence", 0) >= 50:
                            email = e.get("value")
                            break

                    # Priorite 2 : n'importe quel email avec haute confiance
                    if not email:
                        for e in emails:
                            if e.get("confidence", 0) >= 70:
                                email = e.get("value")
                                break

                    # Priorite 3 : pattern generique du domaine
                    if not email:
                        generic = data.get("organization", {}).get("emails", [])
                        if generic:
                            email = generic[0].get("value")

                elif r.status_code == 429:
                    logger.warning("Hunter.io : quota mensuel atteint — desactive pour ce cycle")
                    self._quota_exceeded = True
                elif r.status_code == 401:
                    logger.warning("Hunter.io : cle API invalide — verifier HUNTER_IO_API_KEY")
                    self._quota_exceeded = True

        except Exception as e:
            logger.debug(f"Hunter.io '{domain}': {e}")

        self._cache[domain] = email
        return email

    async def find_email_for_company(self, company_name: str, domain: str) -> Optional[str]:
        """Recherche directe d'un email pour une entreprise."""
        return await self._find_hr_email(domain, company_name)
