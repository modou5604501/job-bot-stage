from typing import Dict
from telegram import Bot
from loguru import logger
from app.config.settings import Settings

class TelegramNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None
        self.chat_id = settings.telegram_chat_id

    async def send_notification(self, job: Dict):
        """Envoie une notification Telegram"""
        if not self.bot:
            logger.warning("Telegram token non configuré — notification ignorée")
            return
        if not self.chat_id:
            logger.warning("Telegram chat_id non configuré — notification ignorée")
            return

        try:
            message = self._format_message(job)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.info(f"Notification envoyée : {job['title']} @ {job['company']}")

        except Exception as e:
            logger.error(f"Erreur notification Telegram: {e}")

    def _format_message(self, job: Dict) -> str:
        """Formate le message de notification"""
        analysis = job.get("analysis", {})
        return (
            f"<b>Nouvelle offre pertinente !</b>\n\n"
            f"<b>{job['title']}</b>\n"
            f"<i>{job['company']}</i>\n"
            f"{job['location']}\n\n"
            f"Score : {analysis.get('score', 0)}/10\n"
            f"{analysis.get('reason', '')}\n\n"
            f"<a href=\"{job['url']}\">Voir l'offre</a>"
        )
