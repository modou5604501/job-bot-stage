"""
Envoie un SMS de test au 819-919-8401 pour verifier que la passerelle Bell fonctionne.
Usage : python send_test_sms.py
"""
import asyncio
from app.config.settings import Settings
from app.config.logging import setup_logging
from app.notifier.sms_sender import SmsSender
from loguru import logger


async def main():
    settings = Settings()
    setup_logging(settings.log_level)
    sms = SmsSender(settings)
    logger.info(f"Envoi SMS de test a {sms._sms_to} ...")
    await sms.send_test_sms()
    logger.info("Termine. Verifie ton telephone dans 30 secondes.")


if __name__ == "__main__":
    asyncio.run(main())
