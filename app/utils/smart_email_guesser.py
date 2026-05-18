"""
Trouve ou devine l'email RH d'une entreprise par plusieurs méthodes :
1. Scraping du site web (pages carrières, contact, à propos)
2. Patterns d'email standards (hr@, careers@, recrutement@, emploi@...)
3. Hunter.io domain-search pour valider que le domaine reçoit des emails
"""
import re
import asyncio
import socket
from typing import Optional, List
from urllib.parse import urlparse
import httpx
from loguru import logger

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

SCRAPE_PATHS = [
    "", "/contact", "/nous-contacter", "/contactez-nous",
    "/careers", "/carrieres", "/emplois", "/jobs", "/join-us",
    "/about", "/a-propos", "/equipe", "/team",
    "/recrutement", "/recruitment", "/hr", "/rh",
    "/about-us", "/qui-sommes-nous",
]

HR_PATTERNS = [
    "careers", "career", "carrieres", "recrutement", "recruitment",
    "hr", "rh", "emploi", "jobs", "job", "talent", "people",
    "hiring", "apply", "candidature",
]

IGNORED_EMAIL_DOMAINS = {
    "example.com", "test.com", "domain.com", "email.com",
    "gmail.com", "hotmail.com", "yahoo.com", "outlook.com",
    "sentry.io", "w3.org", "schema.org",
}

LEGAL_SUFFIXES = [
    " inc", " inc.", " corp", " corp.", " ltd", " ltd.", " llc",
    " s.a.s", " sarl", " s.a.r.l", " s.a.", " sa", " sas",
    " gmbh", " ag", " pty", " nv", " bv",
    " services", " solutions", " group", " groupe",
    " canada", " québec", " quebec", " france", " international",
    " technologies", " technology", " consulting", " conseil",
    " platform", " systems", " global",
]

AGGREGATORS = {
    "linkedin.com", "indeed.com", "jobbank.gc.ca", "francetravail.fr",
    "candidat.francetravail.fr", "hh.ru", "google.com", "jobteaser.com",
    "glassdoor.com", "monster.com", "workopolis.com", "aerocontact.com",
}


def _domain_resolves(domain: str) -> bool:
    """Verifie qu'un domaine existe dans le DNS (filtre les domaines completement inventes)."""
    try:
        socket.setdefaulttimeout(3)
        socket.getaddrinfo(domain, None)
        return True
    except Exception:
        return False


def _company_to_domain(company: str) -> Optional[str]:
    """Devine le domaine d'une entreprise à partir de son nom (max 2 mots significatifs)."""
    if not company or len(company.strip()) < 3:
        return None
    name = company.lower().strip()
    # Supprimer tout ce qui suit une parenthèse ou un slash (ex: "Crees (Eeyou...)/Cree Nation")
    name = re.split(r"[(/\\|]", name)[0].strip()
    for suffix in LEGAL_SUFFIXES:
        name = name.replace(suffix, "")
    # Garder seulement les 2 premiers mots significatifs (longueur > 2)
    words = [w for w in re.split(r"\s+", name.strip()) if len(w) > 2]
    if not words:
        return None
    # Utiliser au max 2 mots pour former le domaine
    domain = "".join(words[:2])
    domain = re.sub(r"[^a-z0-9]", "", domain)
    if len(domain) < 3 or len(domain) > 30:
        domain = re.sub(r"[^a-z0-9]", "", words[0])
    if len(domain) < 3:
        return None
    return domain  # ex: "ecora", "grandcrees", "missionhill"


async def _scrape_emails_from_site(domain_base: str) -> List[str]:
    """Scrape les emails depuis le site web de l'entreprise."""
    found = []
    tlds = [".ca", ".com", ".fr", ".ch", ".org", ".net"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(timeout=8, verify=False, follow_redirects=True, headers=headers) as client:
        for tld in tlds:
            base_url = f"https://www.{domain_base}{tld}"
            for path in SCRAPE_PATHS[:8]:  # Limiter à 8 paths par TLD
                try:
                    r = await client.get(base_url + path)
                    if r.status_code == 200:
                        emails = EMAIL_RE.findall(r.text)
                        for e in emails:
                            e_lower = e.lower()
                            e_domain = e_lower.split("@")[-1]
                            if e_domain in IGNORED_EMAIL_DOMAINS:
                                continue
                            if domain_base in e_domain:
                                found.append(e)
                        if found:
                            return found
                except Exception:
                    pass
    return found


def _pick_best_email(emails: List[str]) -> Optional[str]:
    """Choisit l'email le plus probablement RH parmi une liste."""
    for pattern in HR_PATTERNS:
        for e in emails:
            if pattern in e.lower():
                return e
    return emails[0] if emails else None


def _guess_hr_emails(domain_base: str) -> List[str]:
    """Génère une liste de patterns d'email RH standard pour un domaine."""
    guesses = []
    for tld in [".ca", ".com", ".fr", ".ch"]:
        domain = f"{domain_base}{tld}"
        for prefix in ["careers", "hr", "recrutement", "emploi", "jobs", "rh",
                       "recruitment", "talent", "apply", "contact", "info"]:
            guesses.append(f"{prefix}@{domain}")
    return guesses


def _extract_domain_from_url(url: str) -> Optional[str]:
    """Extrait le domaine depuis l'URL du job (si pas un agrégateur)."""
    try:
        host = urlparse(url).hostname or ""
        if host and not any(agg in host for agg in AGGREGATORS):
            host = re.sub(r"^www\.", "", host)
            return host  # ex: "ecora.ca"
    except Exception:
        pass
    return None


async def find_email_for_job(job: dict, hunter_cache: dict = None) -> Optional[str]:
    """
    Trouve l'email RH pour un job, dans cet ordre :
    1. Scraping du site de l'entreprise
    2. Pattern deviné le plus probable (careers@domain)
    Retourne l'email ou None si impossible de deviner.
    """
    company = job.get("company", "").strip()
    url = job.get("apply_url") or job.get("url") or ""

    # 1. Domaine direct depuis l'URL du job (si c'est le site de l'entreprise)
    direct_domain = _extract_domain_from_url(url)
    if direct_domain:
        scraped = await _scrape_emails_from_site(direct_domain.rsplit(".", 1)[0])
        best = _pick_best_email(scraped)
        if best:
            logger.debug(f"Email scrape (URL directe) pour {company}: {best}")
            return best

    # 2. Deviner le domaine depuis le nom de l'entreprise
    domain_base = _company_to_domain(company)
    if not domain_base:
        return None

    # Cache pour éviter de re-scraper la même entreprise
    if hunter_cache and domain_base in hunter_cache:
        return hunter_cache[domain_base]

    # 3. Scraping du site web
    scraped = await _scrape_emails_from_site(domain_base)
    best = _pick_best_email(scraped)
    if best:
        logger.info(f"Email scrape pour {company}: {best}")
        if hunter_cache is not None:
            hunter_cache[domain_base] = best
        return best

    # 4. Deviner le pattern — seulement si le domaine resout dans le DNS
    for tld in [".ca", ".com", ".fr", ".ch"]:
        domain = f"{domain_base}{tld}"
        if _domain_resolves(domain):
            guessed = f"careers@{domain}"
            logger.info(f"Email devine pour {company}: {guessed}")
            if hunter_cache is not None:
                hunter_cache[domain_base] = guessed
            return guessed
        logger.debug(f"Domaine inexistant (DNS) : {domain} — ignore")

    logger.info(f"Aucun domaine DNS valide trouve pour {company} — candidature ignoree")
    return None


async def enrich_jobs_smart(jobs: list) -> list:
    """
    Enrichit tous les jobs sans email en cherchant/devinant les emails RH.
    """
    cache = {}
    enriched = 0
    for job in jobs:
        if job.get("apply_email"):
            continue
        if not job.get("company", "").strip():
            continue  # France Travail sans nom d'entreprise — impossible
        email = await find_email_for_job(job, cache)
        if email:
            job["apply_email"] = email
            enriched += 1
    if enriched:
        logger.info(f"Smart email guesser : {enriched} emails trouves/devines")
    return jobs
