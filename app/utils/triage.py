"""
Systeme de triage intelligent des offres de stage
Adapte au profil de Modou Khabane Mbaye — Geomatique appliquee a l'environnement
"""

# Mots-cles tres pertinents pour le profil (score eleve)
KEYWORDS_HIGH = [
    "geomatique", "geomatics", "gis", "sig", "qgis", "arcgis", "arcmap",
    "teledetection", "remote sensing", "cartographie", "cartography",
    "analyse spatiale", "spatial analysis", "fme", "lidar", "drone",
    "photogrammetrie", "postgis", "geodata", "geospatial",
    "systeme d'information geographique", "geographic information",
]

# Mots-cles pertinents environnement (score moyen-haut)
KEYWORDS_ENV = [
    "environnement", "environment", "ecologie", "ecology",
    "gestion environnementale", "environmental management",
    "impact environnemental", "biodiversite", "biodiversity",
    "milieu naturel", "conservation", "developpement durable",
    "sustainable", "eau", "water", "foret", "forest", "climat", "climate",
    "evaluation environnementale", "environmental assessment",
]

# Mots-cles bonus (profil specifique)
KEYWORDS_BONUS = [
    "stage", "intern", "internship", "cooperatif", "coop",
    "sherbrooke", "quebec", "montreal", "canada",
    "python", "donnees", "data", "analyse", "mapping",
]

# Entreprises/secteurs de qualite (bonus de score)
QUALITY_EMPLOYERS = [
    "gouvernement", "government", "canada", "federal", "provincial",
    "municipal", "ville de", "city of", "ministere", "ministry",
    "universite", "university", "college", "ecole", "cnrc", "nrc",
    "hydro", "hydro-quebec", "bell", "cef", "inrs", "uqam",
    "environnement canada", "environment canada", "ressources naturelles",
    "natural resources", "agriculture", "statcan", "statistics canada",
    "geodata", "esri", "trimble", "hexagon", "terragen",
]

# Mots-cles qui signalent une offre NON pertinente
KEYWORDS_NEGATIVE = [
    # Logistique / manuel
    "warehouse", "entrepot", "chauffeur", "driver", "caissier", "cashier",
    "construction", "electricien", "plombier", "menage", "cleaning",
    # Ventes / marketing / com
    "ventes", "sales", "marketing", "content creator", "community manager",
    "influenceur", "social media", "reseaux sociaux",
    # Restauration / hotellerie
    "cuisine", "cuisinier", "cook", "serveur", "server", "waiter",
    "commis", "receptionniste", "room service", "hotellerie", "hotel",
    "restauration", "barista", "sommelier", "petits-dejeuners", "spa",
    "guest relation", "concierge",
    # Finance / comptabilite / juridique
    "comptabilite", "accounting", "finance", "cfo", "cfa", "contrôleur interne",
    "controleur interne", "moex", "avocat", "lawyer", "juridique", "legal",
    "investissement immobilier", "real estate leasing", "asset management",
    # RH / recrutement
    "recrutement", "recruitment", "consultant en recrutement", "chasseur de tetes",
    # Sport / medias
    "football", "soccer", "sport", "club sportif",
]

# Score minimum pour etre inclus dans l'email
SCORE_MINIMUM = 2

# Periode ciblee
TARGET_START = "septembre 2026"
TARGET_MONTHS = "3 à 4 mois"

# Mots-cles remuneration (bonus de score)
KEYWORDS_PAID = [
    "remunere", "remuneration", "salaire", "paid", "stipend",
    "indemnite", "compensation", "gratification", "wage",
]

# Mots-cles periode compatible
KEYWORDS_PERIOD = [
    "septembre", "october", "octobre", "automne", "fall 2026",
    "autumn 2026", "sept 2026", "sep 2026", "3 mois", "4 mois",
    "3 months", "4 months", "trimestre",
]


def score_job(job: dict) -> dict:
    """
    Calcule un score de pertinence pour une offre.
    Retourne le job enrichi avec score, niveau et raison.
    """
    text = f"{job.get('title', '')} {job.get('description', '')} {job.get('company', '')} {job.get('search_query', '')}".lower()
    title_text = f"{job.get('title', '')}".lower()

    score = 0
    matched_keywords = []
    reasons = []

    # Elimination immediate si mot-cle negatif dans le titre
    for neg in KEYWORDS_NEGATIVE:
        if neg in title_text:
            return _build_result(job, score=0, level="non pertinent",
                                 reason=f"Hors domaine ({neg})", keywords=[])

    # Mots-cles geomatique/SIG (2 points chacun)
    for kw in KEYWORDS_HIGH:
        if kw in text:
            score += 2
            matched_keywords.append(kw)

    # Mots-cles environnement (1.5 points chacun)
    for kw in KEYWORDS_ENV:
        if kw in text:
            score += 1.5
            matched_keywords.append(kw)

    # Mots-cles bonus (0.5 point chacun)
    for kw in KEYWORDS_BONUS:
        if kw in text:
            score += 0.5
            matched_keywords.append(kw)

    # Bonus employeur de qualite (+2)
    for employer in QUALITY_EMPLOYERS:
        if employer in text:
            score += 2
            reasons.append(f"Employeur reconnu ({employer})")
            break

    # Bonus si le mot "stage" ou "intern" est dans le titre (+1)
    if any(k in title_text for k in ["stage", "intern", "coop", "cooperatif"]):
        score += 1
        reasons.append("Poste de stage confirme")

    # Bonus remuneration (+2)
    for kw in KEYWORDS_PAID:
        if kw in text:
            score += 2
            reasons.append("Stage remunere")
            break

    # Bonus periode compatible septembre-decembre 2026 (+1.5)
    for kw in KEYWORDS_PERIOD:
        if kw in text:
            score += 1.5
            reasons.append("Periode compatible (automne 2026)")
            break

    # Score de base selon la requete de recherche (compense les descriptions vides)
    query = job.get("search_query", "").lower()
    if any(k in query for k in ["geomatique", "geomatics", "gis", "sig", "qgis", "arcgis"]):
        score += 3
        reasons.append("Recherche geomatique directe")
    elif any(k in query for k in ["environnement", "environment", "ecology", "spatial"]):
        score += 2
        reasons.append("Recherche environnement directe")
    elif any(k in query for k in ["topographie", "hydrologie", "amenagement", "territorial",
                                   "remote sensing", "cartograph", "teledetection", "mapping"]):
        score += 2
        reasons.append("Domaine connexe")

    # Bonus source francaise (France Travail = offres verifiees)
    source = job.get("source", "")
    if source == "francetravail.fr":
        score += 1
        reasons.append("Source officielle France Travail")

    # Niveau de pertinence
    if score >= 8:
        level = "Excellent"
    elif score >= 5:
        level = "Tres pertinent"
    elif score >= SCORE_MINIMUM:
        level = "Pertinent"
    else:
        level = "Faible"

    reason = " | ".join(reasons) if reasons else f"Domaine: {job.get('search_query', '')}"

    return _build_result(job, score=round(score, 1), level=level,
                         reason=reason, keywords=list(set(matched_keywords)))


def _build_result(job, score, level, reason, keywords):
    job["analysis"] = {
        "score": score,
        "level": level,
        "reason": reason,
        "keywords": keywords
    }
    return job


def triage_jobs(jobs: list) -> tuple:
    """
    Trie et filtre les offres.
    Retourne (offres_retenues, offres_rejetees)
    """
    scored = [score_job(job) for job in jobs]
    scored.sort(key=lambda j: j["analysis"]["score"], reverse=True)

    retenues = [j for j in scored if j["analysis"]["score"] >= SCORE_MINIMUM]
    rejetees = [j for j in scored if j["analysis"]["score"] < SCORE_MINIMUM]

    return retenues, rejetees
