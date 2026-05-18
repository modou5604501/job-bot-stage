from typing import List, Dict, Optional
from urllib.parse import urlencode
import re
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from app.config.settings import Settings
from app.scraper.rate_limiter import RateLimiter
from app.utils.company_email_finder import find_company_email, extract_company_website


class IndeedScraper:
    """Scraper Job Bank Canada — recupere les offres et les emails de contact"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.rate_limiter = RateLimiter()
        self.base_url = "https://www.jobbank.gc.ca/jobsearch/jobsearch"

    async def scrape_jobs(self) -> List[Dict]:
        all_jobs = []
        queries = [q.strip() for q in self.settings.indeed_search_queries.split(",")]

        for query in queries:
            logger.info(f"Recherche Job Bank Canada : '{query}'")
            jobs = await self._fetch_jobs(query)
            all_jobs.extend(jobs)
            logger.info(f"{len(jobs)} offres trouvees pour '{query}'")
            await self.rate_limiter.wait()

        # Deduplication par URL
        seen = set()
        unique_jobs = []
        for job in all_jobs:
            if job["url"] not in seen:
                seen.add(job["url"])
                unique_jobs.append(job)

        # Recuperer les details (email de contact, description complete)
        logger.info(f"Recuperation des details pour {len(unique_jobs)} offres...")
        for job in unique_jobs:
            details = await self._fetch_job_details(job["url"])
            job.update(details)
            await self.rate_limiter.wait()

        return unique_jobs

    async def _fetch_jobs(self, query: str) -> List[Dict]:
        jobs = []
        params = {"searchstring": query, "locationstring": self.settings.indeed_location}
        url = f"{self.base_url}?{urlencode(params)}"

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                articles = soup.find_all("article", class_="action-buttons")
                for article in articles[:10]:
                    job = self._parse_article(article, query)
                    if job:
                        jobs.append(job)
        except Exception as e:
            logger.error(f"Erreur Job Bank ({query}): {e}")

        return jobs

    async def _fetch_job_details(self, url: str) -> Dict:
        """Recupere la description complete et l'email de contact depuis la page de l'offre"""
        details = {"description": "", "apply_email": None, "apply_url": url}
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")

                # Description complete
                desc_tag = soup.find("div", {"id": "tp_jobDetailsSection"}) or \
                           soup.find("div", class_="job-posting-detail-requirements")
                if desc_tag:
                    details["description"] = re.sub(r'\s+', ' ', desc_tag.get_text(strip=True))[:800]

                # 1. Chercher d'abord les liens mailto: (le plus fiable)
                for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                    em = a["href"].replace("mailto:", "").split("?")[0].strip()
                    if em and "@" in em:
                        details["apply_email"] = em
                        logger.debug(f"Email trouve (mailto): {em}")
                        break

                # 2. Si pas de mailto, chercher un email dans le texte de la page
                if not details["apply_email"]:
                    page_text = soup.get_text()
                    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', page_text)
                    ignored = ["jobbank", "gc.ca", "google", "canada.ca", "example",
                               "sentry", "noreply", "user@domain", "talent.com"]
                    for em in emails:
                        # Rejeter les emails HTML mal decoded (u003e = >) et les placeholders
                        if em.startswith("u003") or em.startswith(">"):
                            continue
                        if not any(ig in em.lower() for ig in ignored):
                            details["apply_email"] = em
                            logger.debug(f"Email trouve (texte): {em}")
                            break

                # 3. URL externe de candidature — suivre si c'est un site d'entreprise
                apply_btn = soup.find("a", {"id": "applynowbutton"}) or \
                            soup.find("a", string=re.compile(r"postuler|apply now|apply", re.I))
                if apply_btn and apply_btn.get("href"):
                    href = apply_btn["href"]
                    if href.startswith("http"):
                        details["apply_url"] = href
                        # Si pas encore d'email, essayer de trouver sur la page de l'entreprise
                        if not details["apply_email"]:
                            company_email = await self._find_email_on_page(client, href)
                            if company_email:
                                details["apply_email"] = company_email

                # 4. Si toujours pas d'email, chercher le site web de l'entreprise
                #    et chercher l'email sur sa page /contact ou /carrieres
                if not details["apply_email"]:
                    company_site = await extract_company_website(soup)
                    if company_site:
                        details["company_website"] = company_site
                        email = await find_company_email(company_site, client)
                        if email:
                            details["apply_email"] = email
                            logger.info(f"Email RH trouve via site entreprise: {email}")

        except Exception as e:
            logger.debug(f"Impossible de recuperer les details pour {url}: {e}")

        return details

    async def _find_email_on_page(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Tente de trouver un email de contact sur une page externe (site entreprise)"""
        # Ne pas suivre les portails connus (pas d'email direct dessus)
        blocked_portals = ["linkedin.com", "indeed.com", "jobbank", "workopolis", "monster",
                           "glassdoor", "ziprecruiter", "taleo", "greenhouse", "lever.co",
                           "workday", "icims", "smartrecruiters", "bamboohr", "successfactors"]
        if any(p in url.lower() for p in blocked_portals):
            return None
        try:
            r = await client.get(url, timeout=15, follow_redirects=True)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, "html.parser")
                # Priorite aux liens mailto:
                for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                    em = a["href"].replace("mailto:", "").split("?")[0].strip()
                    if em and "@" in em:
                        logger.debug(f"Email trouve sur site entreprise: {em}")
                        return em
                # Puis dans le texte
                text = soup.get_text()
                emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
                ignored = ["example", "noreply", "no-reply", "sentry", "google",
                           "support@", "user@domain", "talent.com"]
                for em in emails:
                    if em.startswith("u003") or em.startswith(">"):
                        continue
                    if not any(ig in em.lower() for ig in ignored):
                        logger.debug(f"Email trouve sur site entreprise (texte): {em}")
                        return em
        except Exception:
            pass
        return None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
        }

    def _parse_article(self, article, query: str) -> Dict:
        try:
            title_tag = article.find("span", class_="noctitle")
            title = title_tag.get_text(strip=True) if title_tag else ""
            company_tag = article.find("li", class_="business")
            company = company_tag.get_text(strip=True) if company_tag else ""
            location_tag = article.find("li", class_="location")
            location = re.sub(r'^Location', '', location_tag.get_text(strip=True) if location_tag else "").strip()
            link_tag = article.find("a", class_="resultJobItem")
            link = link_tag["href"] if link_tag else ""
            link = re.sub(r';jsessionid=[^?]+', '', link)
            if link and not link.startswith("http"):
                link = f"https://www.jobbank.gc.ca{link}"

            if not title:
                return None

            return {
                "title": title,
                "company": company,
                "location": location,
                "description": "",
                "url": link,
                "apply_email": None,
                "apply_url": link,
                "source": "jobbank.gc.ca",
                "search_query": query
            }
        except Exception as e:
            logger.warning(f"Erreur parsing article: {e}")
            return None
