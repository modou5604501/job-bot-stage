"""
Depot automatique de candidature par email.
Envoie une lettre de motivation generee par Claude IA + CV adapte ATS a chaque entreprise,
puis confirme le depot par email au candidat.
Strategie ATS : CV personnalise par offre en < 5s (mots-cles injectes, experiences reordonnees).
"""
import os
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional
from loguru import logger
from app.config.settings import Settings
from app.config.user_profile import PROFILE, PROFILE_EN
from app.ai.cover_letter_engine import generate_cover_letter as generate_template_letter
from app.ai.cover_letter_engine import generate_cover_letter_en
from app.ai.cv_adapter_engine import generate_adapted_cv, _is_english_job


def _build_subject(job: Dict) -> str:
    title = job.get("title", "le poste")
    if _is_english_job(job):
        return f"Application — {title} | Modou Khabane Mbaye, Geomatics Student"
    region = job.get("region", job.get("location", "")).lower()
    if any(k in region for k in ["france", "suisse", "europe"]):
        return f"Candidature au poste de {title} — Modou Khabane Mbaye, etudiant en Geomatique"
    return f"Candidature — {title} | Modou Khabane Mbaye, etudiant en Geomatique"


class AutoApply:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cv_path = settings.cv_path
        self._claude = None
        if settings.claude_api_key:
            try:
                from app.ai.claude_client import ClaudeClient
                self._claude = ClaudeClient(settings)
                logger.info("Lettre de motivation : moteur Claude IA active")
            except Exception as e:
                logger.warning(f"Claude IA indisponible, fallback template : {e}")

    async def _generate_letter(self, job: Dict) -> str:
        """Genere la lettre via Claude IA si disponible, sinon template adaptatif (FR ou EN selon le poste)"""
        en = _is_english_job(job)
        profile = PROFILE_EN if en else PROFILE
        if self._claude:
            try:
                letter = await self._claude.generate_cover_letter(job, profile)
                if letter and "Erreur" not in letter:
                    return letter
            except Exception as e:
                logger.warning(f"Erreur Claude, fallback template : {e}")
        return generate_cover_letter_en(job) if en else generate_template_letter(job)

    async def apply_to_job(self, job: Dict) -> bool:
        """
        Envoie une candidature automatique avec CV adapte ATS.
        Retourne True si envoyee avec succes.
        """
        apply_email = job.get("apply_email")
        if not apply_email:
            logger.info(
                f"Pas d'email direct pour '{job['title']}' @ {job.get('company', '')} "
                f"— candidature manuelle requise"
            )
            return False

        try:
            cover_letter = await self._generate_letter(job)

            # CV adapte ATS genere en < 5s pour ce poste precis
            adapted_cv_bytes = generate_adapted_cv(job)

            msg = self._build_application(job, apply_email, cover_letter, adapted_cv_bytes,
                                      en=_is_english_job(job))
            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=True,
            )
            logger.info(
                f"[AUTO-APPLY] Candidature envoyee : {job['title']} @ {job.get('company', '')} -> {apply_email}"
            )
            return True

        except Exception as e:
            logger.error(f"Erreur envoi candidature ({job['title']}): {e}")
            return False

    def _build_application(self, job: Dict, to_email: str, cover_letter: str,
                           adapted_cv_bytes: bytes = b"", en: bool = False) -> MIMEMultipart:
        """Construit l'email envoye a l'entreprise avec CV adapte ATS"""
        subject = _build_subject(job)
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"Modou Khabane Mbaye <{self.settings.smtp_user}>"
        msg["To"] = to_email
        msg["Reply-To"] = PROFILE_EN["email"] if en else PROFILE["email"]

        html_part = MIMEMultipart("alternative")
        html_part.attach(MIMEText(self._build_html_body(cover_letter, en=en), "html", "utf-8"))
        msg.attach(html_part)

        # Priorite 1 : CV adapte ATS genere dynamiquement pour ce poste
        if adapted_cv_bytes:
            self._attach_cv_bytes(msg, adapted_cv_bytes,
                                  "Modou_Khabane_Mbaye_CV.pdf")
            logger.debug("CV adapte ATS joint a l'email de candidature")
        # Fallback : CV statique si la generation a echoue
        elif self.cv_path and os.path.isfile(self.cv_path):
            self._attach_cv(msg)
            logger.debug("CV statique joint (fallback)")
        else:
            logger.debug("Aucun CV joint")

        return msg


    def _build_html_body(self, cover_letter: str, en: bool = False) -> str:
        p = PROFILE_EN if en else PROFILE
        label_tel = "Phone" if en else "Tel"
        label_prog = (
            "Bachelor's in Applied Geomatics for the Environment — Universite de Sherbrooke | Co-op program"
            if en else
            "Etudiant en Geomatique appliquee a l'environnement — Universite de Sherbrooke | Programme cooperatif"
        )
        return f"""
        <html>
        <body style="font-family:Arial,sans-serif; max-width:650px; margin:auto; padding:24px; color:#333;">
            <div style="white-space:pre-line; line-height:1.85; font-size:14px;">
{cover_letter}
            </div>
            <br>
            <div style="border-top:1px solid #ddd; padding-top:16px; font-size:13px; color:#555;">
                <strong>Modou Khabane Mbaye</strong><br>
                {label_prog}<br>
                <br>
                {label_tel} : {p['phone']}<br>
                Email : <a href="mailto:{p['email']}">{p['email']}</a><br>
                LinkedIn : <a href="{p['linkedin']}">{p['linkedin']}</a><br>
                Portfolio : <a href="{p['portfolio']}">{p['portfolio']}</a>
            </div>
        </body>
        </html>
        """

    def _attach_cv(self, msg: MIMEMultipart):
        try:
            with open(self.cv_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(self.cv_path)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)
            logger.debug(f"CV joint : {filename}")
        except Exception as e:
            logger.warning(f"Impossible de joindre le CV : {e}")

    def _attach_cv_bytes(self, msg: MIMEMultipart, pdf_bytes: bytes, filename: str):
        """Attache un PDF genere dynamiquement (CV adapte ATS) sans ecrire sur disque"""
        try:
            part = MIMEBase("application", "pdf")
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)
        except Exception as e:
            logger.warning(f"Impossible de joindre le CV adapte : {e}")
