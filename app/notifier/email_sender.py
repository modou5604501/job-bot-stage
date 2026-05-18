import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict
from loguru import logger
from app.config.settings import Settings
from app.config.user_profile import PROFILE
from app.ai.cover_letter_engine import generate_cover_letter


class EmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_digest(self, jobs: List[Dict]):
        """Envoie un email recapitulatif avec lettres de motivation personnalisees"""
        try:
            msg = self._build_digest(jobs)
            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=True,
            )
            logger.info(f"Email envoye avec {len(jobs)} offres")
        except Exception as e:
            logger.error(f"Erreur envoi email: {e}")

    def _build_digest(self, jobs: List[Dict]) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Job Bot] {len(jobs)} nouvelle(s) offre(s) de stage"
        msg["From"] = self.settings.smtp_user
        msg["To"] = self.settings.notification_email

        cards = ""
        for i, job in enumerate(jobs, 1):
            cover_letter = generate_cover_letter(job)
            cards += self._job_card_html(i, job, cover_letter)

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif; max-width:700px; margin:auto; padding:20px; color:#333;">

            <div style="background:#2c3e50; color:white; padding:20px; border-radius:8px; margin-bottom:24px;">
                <h2 style="margin:0;">Job Bot — Nouvelles offres de stage</h2>
                <p style="margin:6px 0 0 0; opacity:0.8;">
                    {len(jobs)} offre(s) trouvee(s) | Geomatique &amp; Environnement | Canada
                </p>
            </div>

            <div style="background:#f0f4f8; padding:14px; border-radius:6px; margin-bottom:24px;">
                <strong>Votre profil joint a chaque candidature :</strong><br>
                <a href="{PROFILE['linkedin']}" style="color:#2980b9;">LinkedIn</a> &nbsp;|&nbsp;
                <a href="{PROFILE['portfolio']}" style="color:#2980b9;">Portfolio / Blog</a> &nbsp;|&nbsp;
                {PROFILE['email']} &nbsp;|&nbsp; {PROFILE['phone']}
            </div>

            {cards}

            <p style="font-size:11px; color:#aaa; margin-top:30px; text-align:center;">
                Job Bot — recherche automatique sur Job Bank Canada
            </p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html", "utf-8"))
        return msg

    def _job_card_html(self, index: int, job: Dict, cover_letter: str) -> str:
        """Genere la carte HTML d'une offre avec lettre de motivation"""
        keywords = job.get("analysis", {}).get("keywords", [])
        kw_str = ", ".join(keywords) if keywords else job.get("search_query", "")

        return f"""
        <div style="border:1px solid #ddd; border-radius:8px; margin-bottom:28px; overflow:hidden;">

            <!-- En-tete offre -->
            <div style="background:#2980b9; color:white; padding:14px 18px;">
                <h3 style="margin:0; font-size:16px;">#{index} — {job['title']}</h3>
                <p style="margin:4px 0 0 0; opacity:0.9; font-size:13px;">
                    {job['company']} &nbsp;|&nbsp; {job['location']}
                </p>
            </div>

            <div style="padding:16px 18px;">

                <!-- Score et niveau -->
                <p style="font-size:12px; color:#777; margin:0 0 12px 0;">
                    Pertinence : <b>{job.get('analysis',{}).get('level','')}</b>
                    &nbsp;|&nbsp; Score : <b>{job.get('analysis',{}).get('score',0)}/10</b>
                    &nbsp;|&nbsp; Mots-cles : <b>{kw_str}</b>
                </p>

                <!-- Statut de candidature -->
                {self._status_badge(job)}


                <!-- Lettre de motivation -->
                <div style="background:#f9f9f9; border-left:4px solid #2980b9;
                            padding:14px 16px; border-radius:0 6px 6px 0;">
                    <p style="margin:0 0 8px 0; font-size:12px; color:#888; font-weight:bold;">
                        LETTRE DE MOTIVATION PERSONNALISEE (a copier-coller)
                    </p>
                    <div style="font-size:13px; line-height:1.7; white-space:pre-line;">{cover_letter}</div>
                </div>

                <!-- Liens profil -->
                <div style="margin-top:14px; font-size:12px; color:#555;">
                    <b>Vos liens a joindre :</b>
                    <a href="{PROFILE['linkedin']}" style="color:#2980b9; margin-left:8px;">LinkedIn</a> &nbsp;|&nbsp;
                    <a href="{PROFILE['portfolio']}" style="color:#2980b9;">Portfolio</a>
                </div>

            </div>
        </div>
        """

    def _status_badge(self, job: Dict) -> str:
        if job.get("applied"):
            return '<div style="display:inline-block;padding:8px 16px;background:#27ae60;color:white;border-radius:5px;font-weight:bold;font-size:13px;margin-bottom:14px;">Candidature envoyee automatiquement</div>'
        else:
            url = job.get("url", "#")
            return f'<a href="{url}" style="display:inline-block;padding:10px 22px;background:#e67e22;color:white;text-decoration:none;border-radius:5px;font-weight:bold;font-size:14px;margin-bottom:14px;">A postuler manuellement</a>'

    def _generate_cover_letter(self, job: Dict) -> str:
        """Genere une lettre de motivation adaptee a l'offre"""
        title = job.get("title", "ce poste")
        company = job.get("company", "votre entreprise")
        query = job.get("search_query", "")

        # Adapter le paragraphe selon le domaine
        if any(k in query.lower() for k in ["environnement", "environment"]):
            expertise_para = (
                "Ma formation en geomatique appliquee a l'environnement, combinee a mon "
                "experience en collecte et analyse de donnees environnementales sur le terrain, "
                "m'a permis de developper une approche rigoureuse de la gestion environnementale. "
                "Lors de mon stage a l'Aeroport International Blaise Diagne, j'ai notamment realise "
                "des inspections environnementales et participe a des projets QSHE."
            )
        else:
            expertise_para = (
                "Ma formation en geomatique m'a permis de maitriser les outils essentiels "
                "tels que QGIS, ArcGIS Pro, FME et Python pour l'analyse spatiale et la cartographie. "
                "J'ai notamment realise la cartographie du reseau electrique de Senelec expose aux "
                "inondations a l'aide des SIG, ainsi qu'un projet complet de cartographie du site "
                "minier Aldermac integrant des donnees multisources."
            )

        return f"""Madame, Monsieur,

Je me permets de vous adresser ma candidature pour le poste de {title} au sein de {company}. Actuellement etudiant en deuxieme annee de Baccalaureat en Geomatique appliquee a l'environnement a l'Universite de Sherbrooke (programme cooperatif), je suis activement a la recherche d'un stage qui me permettrait de mettre en pratique mes competences acquises.

{expertise_para}

Mon profil allie competences techniques solides (QGIS, ArcGIS Pro, FME, Python, teledetection) et aptitudes professionnelles (rigueur, autonomie, travail d'equipe interculturel). Je suis disponible pour un stage et tres motive a contribuer aux projets de {company}.

Je serais ravi de discuter de ma candidature lors d'un entretien. Vous trouverez mon CV, mon profil LinkedIn ({PROFILE['linkedin']}) et mon portfolio ({PROFILE['portfolio']}) ci-joints.

Dans l'attente de votre retour, veuillez agreer, Madame, Monsieur, l'expression de mes salutations distinguees.

Modou Khabane Mbaye
{PROFILE['phone']} | {PROFILE['email']}"""
