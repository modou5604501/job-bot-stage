import re

def clean_text(text: str) -> str:
    """Nettoie le texte des offres"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def extract_keywords(text: str) -> list:
    """Détecte si l'offre est pertinente (géomatique ou environnement)"""
    keywords_geomatique = [
        "gis", "géomatique", "geomatique", "cartographie", "sig", "qgis",
        "arcgis", "télédétection", "teledetection", "données spatiales",
        "systèmes d'information géographique", "remote sensing", "lidar",
        "drone", "photogrammétrie", "postgis", "mapinfo"
    ]
    keywords_environnement = [
        "environnement", "écologie", "ecologie", "biodiversité", "biodiversite",
        "gestion environnementale", "impact environnemental", "eau", "forêt",
        "foret", "milieu naturel", "faune", "flore", "climat", "développement durable",
        "developpement durable", "conservation", "évaluation environnementale"
    ]

    found = []
    text_lower = text.lower()
    for kw in keywords_geomatique + keywords_environnement:
        if kw in text_lower:
            found.append(kw)
    return found
