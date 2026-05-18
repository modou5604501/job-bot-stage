#!/usr/bin/env python3
"""
Job Bot Intelligent — recherche Europe + Canada + Russie, depot automatique
Sources : Job Bank CA, LinkedIn, France Travail, HH.ru, WTTJ, Indeed, Euraxess,
          Meteojob, Hellowork, Handshake
"""
import asyncio
import argparse
from loguru import logger
from app.config.settings import Settings
from app.config.logging import setup_logging
from app.scraper.indeed_scraper import IndeedScraper
from app.scraper.linkedin_scraper import LinkedInScraper
from app.scraper.multi_scraper import MultiScraper
from app.scraper.francetravail_scraper import FranceTravailScraper
from app.scraper.hh_scraper import HHScraper
from app.scraper.google_jobs_scraper import GoogleJobsScraper
from app.scraper.jobteaser_scraper import JobTeaserScraper
from app.database.models import JobDatabase
from app.notifier.email_sender import EmailSender
from app.notifier.sms_sender import SmsSender
from app.notifier.inbox_monitor import InboxMonitor
from app.notifier.auto_apply import AutoApply
from app.utils.triage import triage_jobs
from app.utils.hunter_email_finder import HunterEmailFinder
from app.utils.smart_email_guesser import enrich_jobs_smart

INTERVAL_HEURES = 2


async def main():
    parser = argparse.ArgumentParser(description="Job Bot Intelligent")
    parser.add_argument("--run-once", action="store_true", help="Lancer une fois")
    parser.add_argument("--continuous", action="store_true",
                        help=f"Lancer toutes les {INTERVAL_HEURES}h")
    parser.add_argument("--check-replies", action="store_true",
                        help="Verifier les reponses uniquement")
    args = parser.parse_args()

    settings = Settings()
    setup_logging(settings.log_level)
    logger.info("Demarrage du Job Bot (Canada + Europe + Russie) — sources: Job Bank, LinkedIn, France Travail, Google Jobs, JobTeaser, HH.ru...")

    jobbank    = IndeedScraper(settings)
    linkedin   = LinkedInScraper()
    multi      = MultiScraper(settings)
    ft         = FranceTravailScraper(settings)
    hh         = HHScraper()
    google     = GoogleJobsScraper()
    jobteaser  = JobTeaserScraper()
    db         = JobDatabase(settings)
    notifier   = EmailSender(settings)
    sms        = SmsSender(settings)
    monitor    = InboxMonitor(settings, db=db)
    applier    = AutoApply(settings)
    hunter     = HunterEmailFinder(settings.hunter_io_api_key) if settings.hunter_io_api_key else None

    if args.check_replies:
        await check_company_replies(monitor, sms)
    elif args.run_once:
        await run_workflow(jobbank, linkedin, multi, ft, hh, google, jobteaser,
                           db, notifier, sms, monitor, applier, hunter)
    elif args.continuous:
        while True:
            await run_workflow(jobbank, linkedin, multi, ft, hh, google, jobteaser,
                               db, notifier, sms, monitor, applier, hunter)
            logger.info(f"Prochaine execution dans {INTERVAL_HEURES} heures...")
            await asyncio.sleep(INTERVAL_HEURES * 3600)
    else:
        logger.info("Usage : python main.py --run-once | --continuous | --check-replies")


async def run_workflow(jobbank, linkedin, multi, ft, hh, google, jobteaser,
                       db, notifier, sms, monitor, applier, hunter=None):

    # 1. Verifier les reponses des entreprises (SMS urgent si detecte)
    await check_company_replies(monitor, sms)

    # 2. Job Bank Canada
    logger.info("=" * 50)
    logger.info("=== Job Bank Canada ===")
    canada_jobs = await jobbank.scrape_jobs()
    logger.info(f"Job Bank : {len(canada_jobs)} offres")

    # 3. LinkedIn France / Suisse / Canada
    logger.info("=== LinkedIn (France / Suisse / Canada) ===")
    linkedin_jobs = await linkedin.scrape_all_regions()
    logger.info(f"LinkedIn : {len(linkedin_jobs)} offres")

    # 4. France Travail (Pole Emploi)
    logger.info("=== France Travail (Pole Emploi) ===")
    ft_jobs = await ft.scrape_all()
    logger.info(f"France Travail : {len(ft_jobs)} offres")

    # 5. HH.ru (Russie)
    logger.info("=== HH.ru (Russie) ===")
    hh_jobs = await hh.scrape_all()
    logger.info(f"HH.ru : {len(hh_jobs)} offres")

    # 6. Google Jobs (via jobspy)
    logger.info("=== Google Jobs ===")
    google_jobs = await google.scrape_all()
    logger.info(f"Google Jobs : {len(google_jobs)} offres")

    # 7. JobTeaser (stages etudiants Europe)
    logger.info("=== JobTeaser (Europe) ===")
    jobteaser_jobs = await jobteaser.scrape_all()
    logger.info(f"JobTeaser : {len(jobteaser_jobs)} offres")

    # 8. Sources supplementaires
    logger.info("=== Sources supplementaires (WTTJ, Indeed, Euraxess, Meteojob...) ===")
    extra_jobs = await multi.scrape_all()
    logger.info(f"Sources supplementaires : {len(extra_jobs)} offres")

    all_jobs = canada_jobs + linkedin_jobs + ft_jobs + hh_jobs + google_jobs + jobteaser_jobs + extra_jobs
    logger.info("=" * 50)
    logger.info(f"TOTAL toutes sources : {len(all_jobs)} offres")

    # 9. Triage intelligent
    relevant_jobs, rejected = triage_jobs(all_jobs)
    logger.info(f"Triage : {len(relevant_jobs)} retenues | {len(rejected)} ignorees")

    # 10. Enrichissement emails — Hunter.io puis scraping/devinette
    if hunter:
        logger.info("=== Hunter.io : recherche emails RH manquants ===")
        relevant_jobs = await hunter.enrich_jobs(relevant_jobs)

    # Scraping avancé + devinette pour les jobs restants sans email
    logger.info("=== Smart email guesser : scraping + devinette ===")
    relevant_jobs = await enrich_jobs_smart(relevant_jobs)

    # 11. Sauvegarde (deduplication — evite de repostuler)
    new_jobs = await db.save_jobs(relevant_jobs)
    logger.info(f"Nouvelles offres (jamais traitees) : {len(new_jobs)}")

    if not new_jobs:
        logger.info("Aucune nouvelle offre — cycle termine")
        return

    # 9. Depot automatique — stage + domaine geomatique/environnement obligatoires
    STAGE_KW = {"stage", "intern", "internship", "stagiaire", "coop", "cooperatif"}
    DOMAIN_KW = {
        "geomatique", "geomatics", "gis", "sig", "qgis", "arcgis",
        "teledetection", "remote sensing", "cartographie", "cartography",
        "spatial", "geospatial", "environnement", "environment", "ecologie",
        "ecology", "hydrologie", "hydrology", "biodiversite", "conservation",
        "milieu naturel", "impact environnemental", "topographie",
    }
    applied_auto = 0
    manual_jobs = []
    sent_emails: set = set()  # deduplication dans ce cycle
    for job in new_jobs:
        title_lower = job.get("title", "").lower()
        # search_query exclus intentionnellement : contient le terme de recherche LinkedIn/JobBank
        # (ex. "stage environnement") qui ferait passer n'importe quel job hors-domaine
        text_lower = f"{title_lower} {job.get('description', '').lower()}"
        is_stage = any(k in title_lower for k in STAGE_KW)
        is_domain = any(k in text_lower for k in DOMAIN_KW)
        if not is_stage:
            logger.info(f"Ignore (non-stage) : {job['title']} @ {job.get('company', '')}")
            job["applied"] = False
            manual_jobs.append(job)
            continue
        if not is_domain:
            logger.info(f"Ignore (hors domaine) : {job['title']} @ {job.get('company', '')}")
            job["applied"] = False
            manual_jobs.append(job)
            continue
        email_key = (job.get("apply_email") or "").lower().strip()
        if email_key and email_key in sent_emails:
            logger.info(f"Deja envoye ce cycle (meme email) : {job['title']} — ignore")
            job["applied"] = False
            manual_jobs.append(job)
            continue
        success = await applier.apply_to_job(job)
        if success:
            job["applied"] = True
            applied_auto += 1
            if email_key:
                sent_emails.add(email_key)
            await db.mark_applied(job["url"], job.get("apply_email", ""))
        else:
            job["applied"] = False
            manual_jobs.append(job)

    logger.info(f"Depots auto envoyes : {applied_auto} | A traiter manuellement : {len(manual_jobs)}")
    if applied_auto > 0:
        logger.info("Candidatures automatiques envoyees avec lettre de motivation + CV")

    # 10. Email recapitulatif (toutes les offres avec statut + lettre de motivation)
    await notifier.send_digest(new_jobs)
    logger.info("Email recapitulatif envoye. Cycle termine.")


async def check_company_replies(monitor, sms):
    """SMS urgent si une entreprise a repondu"""
    logger.info("Verification des reponses d'entreprises...")
    replies = monitor.check_for_replies()
    if replies:
        logger.info(f"{len(replies)} reponse(s) detectee(s) !")
        for reply in replies:
            await sms.notify_company_reply(
                sender=reply["sender"],
                subject=reply["subject"],
                preview=reply["preview"],
                priority=reply.get("priority", "NORMALE"),
            )
    else:
        logger.info("Aucune reponse d'entreprise")


if __name__ == "__main__":
    asyncio.run(main())
