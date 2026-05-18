"""
Trouve l'email RH d'une entreprise en visitant son site web.
Strategie : chercher sur /contact, /carrieres, /jobs, /about, /equipe
"""
import re
from typing import Optional, List
from urllib.parse import urljoin, urlparse
import httpx
from loguru import logger


# Pages contact/emploi courantes a visiter sur un site d'entreprise
CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/contactez-nous",
    "/carrieres",
    "/careers",
    "/emplois",
    "/jobs",
    "/recrutement",
    "/recruitment",
    "/nous-joindre",
    "/about",
    "/a-propos",
    "/equipe",
    "/team",
    "/rh",
    "/hr",
]

# Mots-cles dans un email qui indiquent qu'il est lie aux RH/recrutement
HR_EMAIL_KEYWORDS = [
    "rh", "hr", "recrutement", "recruit", "carriere", "career",
    "emploi", "job", "talent", "humain", "people", "contact",
    "info", "admin",
]

# Portails a ne pas suivre
BLOCKED_DOMAINS = [
    "linkedin.com", "indeed.com", "jobbank", "workopolis", "monster",
    "glassdoor", "ziprecruiter", "taleo", "greenhouse", "lever.co",
    "workday", "icims", "smartrecruiters", "bamboohr", "successfactors",
    "google.com", "facebook.com", "twitter.com", "instagram.com",
    "canada.ca", "gc.ca", "gouvernement", "government",
]

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')


def _is_valid_contact_email(email: str) -> bool:
    """Verifie si un email ressemble a un email de contact valide"""
    em = email.lower()
    # Rejeter les emails HTML mal decodes et les placeholders
    if em.startswith("u003") or em.startswith(">"):
        return False
    ignored = [
        "noreply", "no-reply", "bounce", "daemon", "sentry", "example",
        "support@gmail", "test@", "webmaster@", "user@domain", "talent.com",
        "@talent.com",
    ]
    if any(ig in em for ig in ignored):
        return False
    return True


def _score_email(email: str) -> int:
    """Score un email — plus il ressemble a un email RH, plus le score est eleve"""
    em = email.lower()
    for kw in HR_EMAIL_KEYWORDS:
        if kw in em:
            return 2
    return 1


async def find_company_email(company_website: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Tente de trouver l'email de contact/RH d'une entreprise.
    Retourne le premier email valide trouve, en prioritisant les emails RH.
    """
    domain = urlparse(company_website).netloc
    if not domain or any(bd in domain.lower() for bd in BLOCKED_DOMAINS):
        return None

    base = f"{urlparse(company_website).scheme}://{domain}"
    candidates: List[tuple] = []  # (score, email)

    pages_to_try = [company_website] + [urljoin(base, p) for p in CONTACT_PATHS]

    for page_url in pages_to_try[:6]:  # Limiter a 6 pages pour ne pas surcharger
        try:
            r = await client.get(page_url, timeout=12, follow_redirects=True)
            if r.status_code != 200:
                continue

            # Chercher d'abord les liens mailto: (plus fiables)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.content, "html.parser")
            for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
                em = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
                if em and "@" in em and _is_valid_contact_email(em):
                    score = _score_email(em)
                    candidates.append((score, em))

            # Puis dans le texte
            page_text = r.text
            emails = EMAIL_PATTERN.findall(page_text)
            for em in emails:
                em = em.lower()
                if _is_valid_contact_email(em):
                    score = _score_email(em)
                    candidates.append((score, em))

            if candidates:
                break  # On a trouve des emails, inutile de continuer

        except Exception:
            continue

    if not candidates:
        return None

    # Retourner l'email avec le meilleur score
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_email = candidates[0][1]
    logger.debug(f"Email entreprise trouve sur {domain}: {best_email}")
    return best_email


async def extract_company_website(job_page_soup) -> Optional[str]:
    """Extrait le site web de l'entreprise depuis la page d'une offre Job Bank"""
    import re
    # Chercher les liens externes qui semblent etre un site d'entreprise
    for a in job_page_soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        domain = urlparse(href).netloc.lower()
        if any(bd in domain for bd in BLOCKED_DOMAINS):
            continue
        # Exclure les URLs de page gouvernementales
        if "canada.ca" in domain or "gc.ca" in domain:
            continue
        return href
    return None
