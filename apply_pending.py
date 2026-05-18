"""
Script de rattrapage : postule à tous les jobs en attente dans la DB.
1. Cherche les emails manquants via Hunter.io + scraping site entreprise
2. Applique le filtre domaine/stage
3. Envoie les candidatures avec CV ATS adapté
"""
import asyncio
from loguru import logger
from app.config.settings import Settings
from app.config.logging import setup_logging
from app.database.models import JobDatabase, Job
from app.notifier.auto_apply import AutoApply
from app.utils.hunter_email_finder import HunterEmailFinder
from app.utils.smart_email_guesser import enrich_jobs_smart

STAGE_KW = {"stage", "intern", "internship", "stagiaire", "coop", "cooperatif"}
DOMAIN_KW = {
    "geomatique", "geomatics", "gis", "sig", "qgis", "arcgis",
    "teledetection", "remote sensing", "cartographie", "cartography",
    "cartographe",  # singulier aussi
    "spatial", "geospatial", "geomaticien", "geomaticienne",
    "environnement", "environment", "ecologie", "ecology",
    "hydrologie", "hydrology", "biodiversite", "conservation",
    "milieu naturel", "impact environnemental", "topographie",
    "imagerie spatiale", "lidar", "drone", "photogrammetrie",
    "amenagement", "urbanisme",
}
SKIP_KW = {
    "receptionniste", "commis", "room service", "hotellerie", "restauration",
    "content creator", "community manager", "football", "logistique",
    "comptabilite", "cfo", "cfa", "recrutement", "avocat",
}


async def main():
    settings = Settings()
    setup_logging(settings.log_level)
    db = JobDatabase(settings)
    applier = AutoApply(settings)
    hunter = HunterEmailFinder(settings.hunter_io_api_key) if settings.hunter_io_api_key else None

    # Récupérer tous les jobs non postulés
    with db.SessionLocal() as session:
        pending = session.query(Job).filter_by(applied=False).order_by(
            Job.relevance_score.desc()
        ).all()
        jobs = [
            {
                "title": j.title, "company": j.company, "location": j.location,
                "description": j.description or "", "url": j.url, "source": j.source,
                "apply_email": j.apply_email, "relevance_score": j.relevance_score,
                "analysis": {"score": j.relevance_score},
            }
            for j in pending
        ]

    logger.info(f"{len(jobs)} jobs en attente dans la DB")

    # Filtrer : domaine + stage + pas de mots négatifs
    relevant = []
    for job in jobs:
        title = job["title"].lower()
        text = f"{title} {job['description'].lower()}"

        if any(k in title for k in SKIP_KW):
            continue
        is_stage = any(k in title for k in STAGE_KW)
        is_domain = any(k in text for k in DOMAIN_KW)
        if not (is_stage and is_domain):
            # Garder quand même si score très élevé (poste permanent pertinent)
            if job.get("relevance_score", 0) >= 12 and is_domain:
                pass  # garder
            else:
                continue
        relevant.append(job)

    logger.info(f"{len(relevant)} jobs pertinents à postuler")

    # Chercher les emails manquants
    no_email = [j for j in relevant if not j.get("apply_email")]
    with_email = [j for j in relevant if j.get("apply_email")]

    logger.info(f"  Avec email : {len(with_email)} | Sans email : {len(no_email)}")

    # 1. Hunter.io sur les jobs sans email
    if hunter and no_email:
        logger.info("Recherche emails via Hunter.io...")
        no_email = await hunter.enrich_jobs(no_email)

    # 2. Scraping avancé + devinette pour les restants
    still_no_email = [j for j in no_email if not j.get("apply_email")]
    if still_no_email:
        logger.info(f"Scraping + devinette pour {len(still_no_email)} jobs restants...")
        still_no_email = await enrich_jobs_smart(still_no_email)
        # Fusionner
        no_email = [j for j in no_email if j.get("apply_email")] + still_no_email

    all_relevant = with_email + no_email
    applied = 0
    skipped = 0

    for job in all_relevant:
        if not job.get("apply_email"):
            logger.info(f"Pas d'email : {job['title']} @ {job.get('company', '')} — ignore")
            skipped += 1
            continue

        success = await applier.apply_to_job(job)
        if success:
            applied += 1
            await db.mark_applied(job["url"], job.get("apply_email", ""))
        else:
            skipped += 1

    logger.info(f"BILAN RATTRAPAGE : {applied} candidatures envoyees | {skipped} ignorees (pas d'email)")


if __name__ == "__main__":
    asyncio.run(main())
