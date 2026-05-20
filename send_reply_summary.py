"""
Envoie un email récapitulatif de toutes les réponses d'entreprises
trouvées dans les 30 derniers jours de la boîte Gmail.
"""
import asyncio
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import date, timedelta
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger
from app.config.settings import Settings
from app.config.logging import setup_logging
from app.notifier.inbox_monitor import (
    InboxMonitor, IGNORED_DOMAINS, IGNORED_KEYWORDS_SENDER,
    REQUIRED_SUBJECT_KEYWORDS, BODY_CONFIRM_KEYWORDS,
)


def _decode_str(text: str) -> str:
    try:
        parts = []
        for part, enc in decode_header(text):
            if isinstance(part, bytes):
                parts.append(part.decode(enc or "utf-8", errors="ignore"))
            else:
                parts.append(str(part))
        return " ".join(parts)
    except Exception:
        return text


def _get_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
                except Exception:
                    pass
            elif ct == "text/html" and not body:
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return body.strip()


def fetch_company_replies(settings: Settings):
    """Récupère les réponses d'entreprises depuis IMAP (30 derniers jours)."""
    monitor = InboxMonitor(settings)
    replies = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(settings.smtp_user, settings.smtp_password)
        mail.select("inbox")
        since_date = (date.today() - timedelta(days=30)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f"SINCE {since_date}")
        if status != "OK":
            return replies
        email_ids = messages[0].split()
        logger.info(f"{len(email_ids)} emails analysés (30 derniers jours)")
        for eid in email_ids:
            status2, msg_data = mail.fetch(eid, "(RFC822)")
            if status2 != "OK":
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            subject = _decode_str(msg.get("Subject", ""))
            sender = msg.get("From", "")
            date_str = msg.get("Date", "")
            body = _get_body(msg)

            parsed = {
                "sender": sender,
                "subject": subject,
                "date": date_str,
                "preview": body[:500],
                "full_body": body[:3000],
            }
            if monitor._is_genuine_reply(parsed):
                replies.append(parsed)
                logger.info(f"Reponse trouvee : {sender} | {subject}")
        mail.logout()
    except Exception as e:
        logger.error(f"Erreur IMAP : {e}")
    return replies


async def send_email_summary(settings: Settings, replies: list):
    """Envoie un email HTML avec le contenu complet de chaque réponse."""
    if not replies:
        logger.info("Aucune reponse a envoyer.")
        return

    cards = ""
    for i, r in enumerate(replies, 1):
        body_html = r["full_body"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        cards += f"""
        <div style="border:1px solid #27ae60;border-radius:8px;margin-bottom:24px;overflow:hidden;">
          <div style="background:#27ae60;color:white;padding:12px 18px;">
            <b>#{i} — {r['subject']}</b>
          </div>
          <div style="padding:14px 18px;font-size:13px;">
            <p><b>De :</b> {r['sender']}<br>
            <b>Date :</b> {r['date']}</p>
            <hr style="border:none;border-top:1px solid #eee;margin:10px 0;">
            <div style="white-space:pre-wrap;line-height:1.7;">{body_html}</div>
          </div>
        </div>"""

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:20px;color:#333;">
    <div style="background:#27ae60;color:white;padding:16px 20px;border-radius:8px;margin-bottom:20px;">
      <h2 style="margin:0;">Job Bot — {len(replies)} réponse(s) d'entreprise(s) détectée(s)</h2>
      <p style="margin:6px 0 0 0;opacity:0.9;">30 derniers jours — à traiter en priorité</p>
    </div>
    {cards}
    <p style="font-size:11px;color:#aaa;text-align:center;">Job Bot automatique</p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[URGENT] {len(replies)} reponse(s) entreprise(s) — Job Bot"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.notification_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )
    logger.info(f"Email recapitulatif envoye : {len(replies)} reponse(s)")


async def main():
    settings = Settings()
    setup_logging(settings.log_level)
    logger.info("Recherche reponses entreprises (30 jours) pour envoi email complet...")
    replies = fetch_company_replies(settings)
    logger.info(f"{len(replies)} reponse(s) trouvee(s)")
    await send_email_summary(settings, replies)


if __name__ == "__main__":
    asyncio.run(main())
