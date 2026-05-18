"""
Historique persistant des candidatures envoyees.
Stocke les emails deja contactes dans APPLIED_HISTORY.txt (commite dans le repo).
Ce fichier survit a l'expiration du cache GitHub Actions (contrairement a jobs.db).
"""
import os

HISTORY_FILE = "APPLIED_HISTORY.txt"


def load_applied_emails() -> set:
    """Retourne l'ensemble des emails deja contactes (depuis la premiere candidature)."""
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return {line.strip().lower() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def load_applied_domains() -> set:
    """Retourne les domaines email deja contactes (deduplication au niveau domaine)."""
    emails = load_applied_emails()
    return {e.split("@")[-1] for e in emails if "@" in e}


def save_applied_email(email: str):
    """Ajoute un email a l'historique (append-only, une ligne par email)."""
    if not email or "@" not in email:
        return
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(email.strip().lower() + "\n")
