"""
Rattrapage reponses entreprises :
- Cherche dans TOUS les emails des 30 derniers jours (lus + non lus)
- Envoie un SMS pour chaque vraie reponse d'entreprise trouvee
- Utilise les memes criteres que reply-check.yml mais sans filtre UNSEEN
"""
import asyncio
from loguru import logger
from app.config.settings import Settings
from app.config.logging import setup_logging
from app.database.models import JobDatabase
from app.notifier.inbox_monitor import InboxMonitor
from app.notifier.sms_sender import SmsSender


async def main():
    settings = Settings()
    setup_logging(settings.log_level)
    db = JobDatabase(settings)
    monitor = InboxMonitor(settings, db=db)
    sms = SmsSender(settings)

    logger.info("Recherche reponses entreprises (30 derniers jours)...")
    replies = monitor.check_for_replies(check_all=True)

    if not replies:
        logger.info("Aucune reponse d'entreprise trouvee dans les 30 derniers jours")
        return

    logger.info(f"{len(replies)} reponse(s) trouvee(s) — envoi SMS...")
    for reply in replies:
        logger.info(f"  -> {reply['sender']} | {reply['subject']} [{reply.get('priority','?')}]")
        await sms.notify_company_reply(
            sender=reply["sender"],
            subject=reply["subject"],
            preview=reply["preview"],
            priority=reply.get("priority", "NORMALE"),
        )
    logger.info("SMS envoyes.")


if __name__ == "__main__":
    asyncio.run(main())
