import aiosmtplib
from email.mime.text import MIMEText
from typing import Dict
from loguru import logger
from app.config.settings import Settings


class SmsSender:
    """Envoie des SMS via la passerelle email-to-SMS de Bell Canada (gratuit)"""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_sms(self, subject: str, body: str):
        """Envoie un SMS — message court (160 caracteres max pour Bell)"""
        if not self.settings.sms_email:
            return

        # Bell coupe a 160 caracteres
        message = f"{subject}: {body}"[:160]

        try:
            msg = MIMEText(message)
            msg["Subject"] = subject[:40]
            msg["From"] = self.settings.smtp_user
            msg["To"] = self.settings.sms_email

            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=True,
            )
            logger.info(f"SMS envoye : {message[:60]}...")
        except Exception as e:
            logger.error(f"Erreur envoi SMS: {e}")

    async def notify_new_jobs(self, count: int, top_job: Dict):
        """SMS pour nouvelles offres trouvees"""
        title = top_job.get("title", "")[:40]
        company = top_job.get("company", "")[:30]
        await self.send_sms(
            subject="[Job Bot] Nouvelles offres",
            body=f"{count} offre(s) | Meilleure: {title} @ {company}. Consulte ton email."
        )

    async def notify_company_reply(self, sender: str, subject: str, preview: str, priority: str = "NORMALE"):
        """SMS pour reponse d'une entreprise — URGENT si entreprise connue"""
        if priority == "HAUTE":
            sms_subject = "!!! REPONSE STAGE URGENT !!!"
            body = f"ENTREPRISE CONNUE repond! De: {sender[:25]} | {subject[:40]}"
        else:
            sms_subject = "URGENT - Reponse entreprise"
            body = f"De: {sender[:30]} | Objet: {subject[:40]} | {preview[:40]}"
        await self.send_sms(subject=sms_subject, body=body)
