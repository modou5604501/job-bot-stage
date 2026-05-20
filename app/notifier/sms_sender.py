import aiosmtplib
from email.mime.text import MIMEText
from typing import Dict
from loguru import logger
from app.config.settings import Settings

# Numéro Bell Canada — passerelle email-to-SMS gratuite
# Format : numero10chiffres@txt.bell.ca
SMS_GATEWAY = "8199198401@txt.bell.ca"


class SmsSender:
    """Envoie des SMS via la passerelle email-to-SMS de Bell Canada"""

    def __init__(self, settings: Settings):
        self.settings = settings
        # Forcer le numéro Bell même si le secret GitHub est mal configuré
        self._sms_to = (settings.sms_email or "").strip() or SMS_GATEWAY

    async def send_sms(self, text: str):
        """
        Envoie un SMS au numéro 819-919-8401 via Bell Canada.
        Le corps de l'email devient le texte du SMS (160 car. max).
        """
        text = text[:160]  # Bell coupe à 160 caractères
        try:
            msg = MIMEText(text, "plain", "utf-8")
            msg["Subject"] = ""          # Bell n'affiche pas le sujet
            msg["From"] = self.settings.smtp_user
            msg["To"] = self._sms_to

            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=True,
            )
            logger.info(f"SMS envoye a {self._sms_to} : {text[:80]}")
        except Exception as e:
            logger.error(f"Erreur envoi SMS a {self._sms_to} : {e}")

    async def notify_company_reply(self, sender: str, subject: str,
                                   preview: str, priority: str = "NORMALE"):
        """SMS clair et complet quand une entreprise répond à une candidature."""
        # Extraire juste l'adresse email de l'expéditeur (enlever le nom)
        import re
        email_match = re.search(r'<([^>]+)>', sender)
        sender_clean = email_match.group(1) if email_match else sender.strip()
        sender_short = sender_clean[:35]

        subject_short = subject.strip()[:50]
        preview_short = preview.strip()[:60]

        if priority == "HAUTE":
            text = (
                f"** REPONSE STAGE CONFIRMEE **\n"
                f"De : {sender_short}\n"
                f"Objet : {subject_short}\n"
                f"Extrait : {preview_short}"
            )
        else:
            text = (
                f"** Reponse possible stage **\n"
                f"De : {sender_short}\n"
                f"Objet : {subject_short}\n"
                f"Extrait : {preview_short}"
            )

        await self.send_sms(text)

    async def send_test_sms(self):
        """Envoie un SMS de test pour vérifier que la passerelle Bell fonctionne."""
        await self.send_sms(
            "TEST Job Bot : SMS recu avec succes! "
            "Vous recevrez une alerte ici si une entreprise repond a votre candidature."
        )
