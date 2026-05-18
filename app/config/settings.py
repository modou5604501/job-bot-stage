from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Base de données
    database_url: str = "sqlite:///jobs.db"

    # Logs
    log_level: str = "INFO"

    # Recherche — domaines séparés par des virgules
    indeed_search_queries: str = (
        # Geomatique / SIG
        "geomatique stage,geomatics intern,SIG stage,GIS intern,cartographie stage,"
        "teledetection stage,remote sensing intern,webmapping stage,"
        # Environnement
        "stage environnement,environmental intern,ecologie stage,hydrologie stage,"
        # Domaines ou la geomatique intervient
        "geospatial intern,spatial analysis intern,urban planning GIS stage,"
        "foresterie SIG stage,gestion risques SIG,infrastructure geospatiale stage,"
        "amenagement territoire stage,municipal GIS intern"
    )
    indeed_location: str = "Canada"

    # Email — notifications
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    notification_email: str

    # SMS via passerelle Bell (email-to-SMS, gratuit)
    sms_email: Optional[str] = None

    # Chemin vers le CV PDF à joindre aux candidatures automatiques
    cv_path: Optional[str] = None

    # Claude AI — generation de lettres de motivation intelligentes
    claude_api_key: Optional[str] = None

    # France Travail API officielle (gratuit sur francetravail.io)
    france_travail_client_id: Optional[str] = None
    france_travail_client_secret: Optional[str] = None

    # Adzuna API — couverture FR + CH + CA (gratuit sur developer.adzuna.com)
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None

    # Hunter.io — trouve les emails RH manquants (25 req/mois gratuit sur hunter.io)
    hunter_io_api_key: Optional[str] = None

    model_config = {"env_file": ".env", "case_sensitive": False}
