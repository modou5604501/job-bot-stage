"""
Surveille la boite Gmail pour detecter UNIQUEMENT les vraies reponses
d'entreprises a des candidatures de stage.
"""
import imaplib
import email
from email.header import decode_header
from typing import List, Dict
from loguru import logger
from app.config.settings import Settings

# Expediteurs automatiques a ignorer absolument
IGNORED_DOMAINS = [
    "gmail.com", "google.com", "googlemail.com",
    "facebook.com", "linkedin.com", "twitter.com",
    "indeed.com", "jobbank.gc.ca", "welcometothejungle.com",
    "paypal.com", "interac.ca", "payments.interac.ca",
    "replit.com", "github.com", "notion.so",
    "mailchimp.com", "constantcontact.com", "sendgrid.net",
    "amazonses.com", "bounce.com", "mailer.com",
    "usherbrooke.ca",  # emails universitaires
]

IGNORED_KEYWORDS_SENDER = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "newsletter", "notification", "bounce", "daemon",
    "association", "asbl", "ong",
    # NB: info@ et contact@ sont intentionnellement gardes : beaucoup de RH ecrivent depuis ces adresses
]

# Le sujet DOIT contenir au moins un de ces mots pour etre une vraie reponse
REQUIRED_SUBJECT_KEYWORDS = [
    "candidature", "application", "stage", "intern", "internship",
    "entretien", "interview", "convocation", "invitation",
    "offre de stage", "job offer", "poste", "position",
    "votre cv", "your cv", "your resume", "votre profil",
    "suite a votre", "following your", "en reponse",
    "we reviewed", "nous avons examine", "retenu",
    "selected", "shortlisted", "interesse",
    # Reponses courantes et generiques
    "merci pour votre", "thank you for your",
    "nous avons bien recu", "we have received",
    "re:", "fwd:", "suite:", "regarding your",
    "votre dossier", "your application", "your profile",
    "opportunite", "opportunity", "recrutement", "recruitment",
    "profil retenu", "not retained", "pas retenu",
]

# Mots dans le corps qui renforcent la detection (1 seul suffit — ou aucun si expediteur connu)
BODY_CONFIRM_KEYWORDS = [
    "geomatique", "geomatics", "gis", "sig", "cartographie",
    "environnement", "stage", "intern", "candidature",
    "cv", "resume", "profil", "entretien", "interview",
    "modou", "mbaye", "khabane",
    "candidat", "candidate", "votre demande", "your request",
    "poste", "position", "emploi", "job",
]


class InboxMonitor:
    def __init__(self, settings: Settings, db=None):
        self.settings = settings
        self.imap_host = "imap.gmail.com"
        self.db = db  # JobDatabase — pour croiser avec les candidatures envoyees

    def check_for_replies(self, check_all: bool = False) -> List[Dict]:
        """
        Verifie la boite Gmail pour les vraies reponses d'entreprises.
        check_all=True : cherche aussi dans les emails deja lus (30 derniers jours).
        """
        replies = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host)
            mail.login(self.settings.smtp_user, self.settings.smtp_password)
            mail.select("inbox")

            if check_all:
                # Cherche dans tous les emails recus depuis 30 jours
                from datetime import date, timedelta
                since_date = (date.today() - timedelta(days=30)).strftime("%d-%b-%Y")
                status, messages = mail.search(None, f'SINCE {since_date}')
            else:
                status, messages = mail.search(None, "UNSEEN")

            if status != "OK":
                return replies

            email_ids = messages[0].split()
            logger.info(f"Emails a analyser : {len(email_ids)} ({'tous 30j' if check_all else 'non lus'})")

            # Charger les entreprises a qui on a postule pour croisement prioritaire
            applied_companies = []
            if self.db:
                try:
                    applied_companies = self.db.get_applied_companies()
                except Exception:
                    pass

            for eid in email_ids[-50:]:
                status, msg_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                parsed = self._parse_email(msg)
                if not parsed:
                    continue

                # Priorite absolue : reponse d'une entreprise a qui on a postule
                is_from_applied = self._matches_applied_company(parsed, applied_companies)
                if is_from_applied:
                    parsed["priority"] = "HAUTE"
                    replies.append(parsed)
                    logger.info(f"REPONSE PRIORITAIRE (entreprise connue) : {parsed['sender']} | {parsed['subject']}")
                elif self._is_genuine_reply(parsed):
                    parsed["priority"] = "NORMALE"
                    replies.append(parsed)
                    logger.info(f"Reponse verifiee : {parsed['sender']} | {parsed['subject']}")

            mail.logout()
        except Exception as e:
            logger.error(f"Erreur surveillance inbox: {e}")

        return replies

    def _parse_email(self, msg) -> Dict:
        try:
            subject = self._decode_str(msg.get("Subject", ""))
            sender = msg.get("From", "")
            date = msg.get("Date", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            return {"sender": sender, "subject": subject, "date": date, "preview": body[:300].strip()}
        except Exception:
            return None

    def _decode_str(self, text: str) -> str:
        try:
            decoded = decode_header(text)
            parts = []
            for part, enc in decoded:
                if isinstance(part, bytes):
                    parts.append(part.decode(enc or "utf-8", errors="ignore"))
                else:
                    parts.append(part)
            return " ".join(parts)
        except Exception:
            return text

    def _matches_applied_company(self, reply: Dict, applied_companies: list) -> bool:
        """Verifie si l'expediteur correspond a une entreprise a qui on a postule"""
        sender = reply.get("sender", "").lower()
        subject = reply.get("subject", "").lower()
        for ac in applied_companies:
            company_name = ac["company"].lower()
            apply_email_domain = ac["apply_email"].split("@")[-1] if "@" in ac["apply_email"] else ""
            # Croisement sur le domaine email ou le nom de l'entreprise
            if apply_email_domain and apply_email_domain in sender:
                return True
            if company_name and len(company_name) > 4 and company_name in sender:
                return True
            if company_name and len(company_name) > 4 and company_name in subject:
                return True
        return False

    def _is_genuine_reply(self, reply: Dict) -> bool:
        sender = reply.get("sender", "").lower()
        subject = reply.get("subject", "").lower()
        body = reply.get("preview", "").lower()

        # 1. Rejeter les domaines connus (newsletters, banques, etc.)
        for domain in IGNORED_DOMAINS:
            if domain in sender:
                return False

        # 2. Rejeter les expediteurs automatiques (no-reply, daemon, etc.)
        for kw in IGNORED_KEYWORDS_SENDER:
            if kw in sender:
                return False

        # 3. Le sujet DOIT contenir un mot-cle de candidature
        subject_ok = any(kw in subject for kw in REQUIRED_SUBJECT_KEYWORDS)
        if not subject_ok:
            return False

        # 4. Le corps doit contenir au moins 1 mot de confirmation
        #    OU le sujet est deja tres specifique (contient "candidature" / "entretien" / "interview")
        body_ok = any(kw in body for kw in BODY_CONFIRM_KEYWORDS)
        strong_subject = any(kw in subject for kw in [
            "candidature", "entretien", "interview", "stage", "intern",
            "retenu", "selected", "shortlisted", "invitation", "convocation",
        ])
        if not body_ok and not strong_subject:
            return False

        return True
