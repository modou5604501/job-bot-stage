"""
Generateur de CV adapte ATS — PDF personnalise par offre en < 5 secondes.
Strategie @melancolie.conseil / cvgood.dev :
  1. Mots-cles ATS detectes dans l'offre -> mis en tete des competences
  2. Experiences reordonnees selon la pertinence pour le poste
  3. Profil professionnel tailore au titre exact et a l'entreprise cible
Format : A4, polices integrees, 100 % lisible par les ATS (pas d'images, pas de tableaux)
"""
from __future__ import annotations
from typing import Dict, List
from loguru import logger

from app.config.user_profile import PROFILE, PROFILE_EN
from app.ai.cover_letter_engine import (
    CANDIDATE_SKILLS,
    detect_job_skills,
    detect_country,
)

try:
    from fpdf import FPDF
    _FPDF_OK = True
except ImportError:
    _FPDF_OK = False


def _safe(text: str) -> str:
    """Remplace les caracteres hors Latin-1 par des equivalents ASCII (requis par fpdf2/Helvetica)."""
    return (text
        .replace("—", " - ")   # em dash
        .replace("–", "-")     # en dash
        .replace("’", "'")     # right single quote
        .replace("‘", "'")     # left single quote
        .replace("“", '"')     # left double quote
        .replace("”", '"')     # right double quote
        .replace("•", "*")     # bullet
        .replace("·", "*")     # middle dot
        .replace("°", " deg")  # degree
        .replace("®", "(R)")   # registered
        .replace(" ", " ")     # non-breaking space
    )

# ─── Competences groupees pour l'affichage ────────────────────────────────────

_SKILLS_GROUPED = [
    ("SIG / GIS", [
        "QGIS", "ArcGIS Pro (ArcMap)", "FME", "PostGIS", "AutoCAD",
        "GeoAcces / GeoIndex", "PhpPgAdmin",
    ]),
    ("Programmation & Data", [
        "Python (automatisation geospatiale)", "Google Cloud BigQuery",
        "Studio3T", "SQL / NoSQL",
    ]),
    ("Teledetection & Cartographie", [
        "Interpretation d'images satellitaires", "Stereorestitution aerienne",
        "Cartographie thematique automatisee", "Webmapping interactif",
    ]),
    ("Analyse spatiale & Terrain", [
        "Intersections / Buffers / Overlays", "Analyse de risque spatial",
        "Geotraitement avance", "Collecte de donnees terrain / QSHE",
    ]),
]

# Mapping mot-cle detecte -> (groupe, item exact) pour remonter en tete
_KW_SKILL_MAP: Dict[str, tuple] = {
    "qgis":           ("SIG / GIS", "QGIS"),
    "arcgis":         ("SIG / GIS", "ArcGIS Pro (ArcMap)"),
    "arcmap":         ("SIG / GIS", "ArcGIS Pro (ArcMap)"),
    "fme":            ("SIG / GIS", "FME"),
    "postgis":        ("SIG / GIS", "PostGIS"),
    "autocad":        ("SIG / GIS", "AutoCAD"),
    "python":         ("Programmation & Data", "Python (automatisation geospatiale)"),
    "automatisation": ("Programmation & Data", "Python (automatisation geospatiale)"),
    "automation":     ("Programmation & Data", "Python (automatisation geospatiale)"),
    "bigquery":       ("Programmation & Data", "Google Cloud BigQuery"),
    "cloud":          ("Programmation & Data", "Google Cloud BigQuery"),
    "teledetection":  ("Teledetection & Cartographie", "Interpretation d'images satellitaires"),
    "remote sensing": ("Teledetection & Cartographie", "Interpretation d'images satellitaires"),
    "stereorestitution": ("Teledetection & Cartographie", "Stereorestitution aerienne"),
    "cartographie":   ("Teledetection & Cartographie", "Cartographie thematique automatisee"),
    "cartography":    ("Teledetection & Cartographie", "Cartographie thematique automatisee"),
    "webmapping":     ("Teledetection & Cartographie", "Webmapping interactif"),
    "web mapping":    ("Teledetection & Cartographie", "Webmapping interactif"),
    "spatial":        ("Analyse spatiale & Terrain", "Intersections / Buffers / Overlays"),
    "analyse spatiale": ("Analyse spatiale & Terrain", "Intersections / Buffers / Overlays"),
    "risque":         ("Analyse spatiale & Terrain", "Analyse de risque spatial"),
    "risk":           ("Analyse spatiale & Terrain", "Analyse de risque spatial"),
    "terrain":        ("Analyse spatiale & Terrain", "Collecte de donnees terrain / QSHE"),
    "field":          ("Analyse spatiale & Terrain", "Collecte de donnees terrain / QSHE"),
    "inondation":     ("Analyse spatiale & Terrain", "Analyse de risque spatial"),
    "flood":          ("Analyse spatiale & Terrain", "Analyse de risque spatial"),
}

# ─── Experiences professionnelles ─────────────────────────────────────────────

_EXPERIENCES = [
    {
        "title": "Stagiaire en Geomatique et SIG",
        "company": "Senelec - Societe Nationale d'Electricite",
        "period": "Fev. 2026 - Avr. 2026  |  Dakar, Senegal",
        "bullets": [
            "Cartographie automatisee des infrastructures electriques exposees aux zones d'inondation",
            "Automatisation Python des flux de traitement SIG (mise a jour donnees, cartes thematiques)",
            "Analyses spatiales avancees : intersections, buffers, overlays (QGIS, ArcGIS Pro)",
            "Developpement d'une application webmapping interactive pour visualiser les zones a risque",
            "Gestion de bases de donnees geospatiales (PostGIS, BigQuery, Studio3T)",
        ],
        "keywords": {
            "sig", "gis", "python", "automatisation", "automation", "webmapping",
            "infrastructure", "inondation", "flood", "energie", "energy", "risque",
            "risk", "spatial", "qgis", "cartographie", "cartography", "postgis",
            "bigquery", "cloud", "analyse spatiale",
        },
    },
    {
        "title": "Stagiaire en Operations Aeroportuaires",
        "company": "Aeroport International Blaise Diagne (AIBD)",
        "period": "Ete 2025  |  Dakar, Senegal",
        "bullets": [
            "Gestion et integration de bases de donnees geospatiales via FME et QGIS",
            "Stereorestitution aerienne et photointerpretation d'images de haute resolution",
            "Inspection terrain QSHE et evaluation des infrastructures aeroportuaires",
            "Teledetection appliquee a l'agriculture de precision (images satellitaires)",
            "Collecte et validation de donnees geospatiales sur le terrain",
        ],
        "keywords": {
            "fme", "terrain", "field", "infrastructure", "inspection", "environnement",
            "environment", "qshe", "qgis", "stereorestitution", "transport",
            "teledetection", "remote sensing", "agriculture",
        },
    },
]


# ─── Classe PDF ATS-optimise ──────────────────────────────────────────────────

class _AtsCV(FPDF):
    PRI  = (26,  60, 122)   # Bleu marine
    DARK = (33,  33,  33)
    MED  = (90,  90,  90)
    LITE = (150, 150, 150)
    BG   = (235, 243, 255)  # Fond header bleu clair
    MAR  = 18               # marge mm

    def setup(self):
        self.set_margins(self.MAR, 15, self.MAR)
        self.set_auto_page_break(auto=True, margin=14)

    # helpers
    def _c(self, col):
        return col[0], col[1], col[2]

    def section_title(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self._c(self.PRI))
        self.cell(0, 6, text.upper(), ln=True)
        self.set_draw_color(*self._c(self.PRI))
        self.set_line_width(0.4)
        self.line(self.MAR, self.get_y(), 210 - self.MAR, self.get_y())
        self.ln(2)
        self.set_text_color(*self._c(self.DARK))

    def exp_header(self, title: str, period: str):
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*self._c(self.DARK))
        self.cell(0, 5, title, ln=True)

        self.set_font("Helvetica", "I", 8.5)
        self.set_text_color(*self._c(self.MED))
        self.cell(0, 4, period, ln=True)
        self.set_text_color(*self._c(self.DARK))

    def bullet_line(self, text: str):
        self.set_font("Helvetica", "", 8.8)
        self.set_text_color(*self._c(self.DARK))
        w = 210 - 2 * self.MAR
        self.multi_cell(w, 5, "- " + text, align="L")

    def italic_small(self, text: str):
        self.set_font("Helvetica", "I", 8.5)
        self.set_text_color(*self._c(self.MED))
        self.cell(0, 4, text, ln=True)
        self.set_text_color(*self._c(self.DARK))


# ─── Helpers de contenu ───────────────────────────────────────────────────────

def _profile_summary(job_skills: List[str], job_title: str, company: str, country: str) -> str:
    skill_phrases: List[str] = []
    for sk in job_skills[:4]:
        if sk in CANDIDATE_SKILLS:
            # Prend la partie avant la parenthese et retire les tirets em
            phrase = _safe(CANDIDATE_SKILLS[sk].split("(")[0].strip())
            if phrase not in skill_phrases:
                skill_phrases.append(phrase)
    skills_str = ", ".join(skill_phrases) if skill_phrases else "QGIS, ArcGIS Pro, Python geospatial"

    if country == "France":
        return _safe(
            f"Etudiant en 2e annee de Baccalaureat en Geomatique appliquee a l'environnement "
            f"(Universite de Sherbrooke, programme cooperatif), je candidate au poste de "
            f"{job_title}. Competences cles : {skills_str}. "
            f"Deux stages operationnels en geomatique SIG dans des contextes techniques exigeants."
        )
    if country == "Suisse":
        return _safe(
            f"Etudiant en Geomatique appliquee a l'environnement (Universite de Sherbrooke, "
            f"Canada, programme cooperatif), je candidate au poste de {job_title} chez {company}. "
            f"Expertise operationnelle : {skills_str}. "
            f"Deux stages geospatiaux reussis en milieu professionnel international."
        )
    return _safe(
        f"Etudiant en 2e annee de Baccalaureat en Geomatique appliquee a l'environnement, "
        f"Universite de Sherbrooke (programme cooperatif - session automne 2026). "
        f"Competences cles pour ce poste : {skills_str}. "
        f"Experience terrain confirmee lors de deux stages en geomatique/SIG."
    )


def _ordered_skills(job_skills: List[str]) -> List[tuple]:
    # Identifie les items matches
    matched: set = set()
    for sk in job_skills:
        if sk in _KW_SKILL_MAP:
            matched.add(_KW_SKILL_MAP[sk][1])

    # Score par groupe : nb d'items matches
    group_scores = {name: sum(1 for it in items if it in matched)
                    for name, items in _SKILLS_GROUPED}
    ordered = sorted(_SKILLS_GROUPED, key=lambda g: group_scores.get(g[0], 0), reverse=True)

    result = []
    for name, items in ordered:
        matched_first = [it for it in items if it in matched]
        rest = [it for it in items if it not in matched]
        result.append((name, matched_first + rest))
    return result


def _en_ordered_skills(job_skills: List[str]) -> List[tuple]:
    matched: set = set()
    for sk in job_skills:
        if sk in _EN_KW_SKILL_MAP:
            matched.add(_EN_KW_SKILL_MAP[sk][1])
    group_scores = {name: sum(1 for it in items if it in matched)
                    for name, items in _EN_SKILLS_GROUPED}
    ordered = sorted(_EN_SKILLS_GROUPED, key=lambda g: group_scores.get(g[0], 0), reverse=True)
    result = []
    for name, items in ordered:
        matched_first = [it for it in items if it in matched]
        rest = [it for it in items if it not in matched]
        result.append((name, matched_first + rest))
    return result


def _en_ordered_experiences(job_skills: List[str]) -> List[Dict]:
    exps = [dict(e) for e in _EN_EXPERIENCES]
    for exp in exps:
        exp["_score"] = sum(1 for sk in job_skills if sk in exp["keywords"])
    exps.sort(key=lambda e: e["_score"], reverse=True)
    return exps


def _ordered_experiences(job_skills: List[str]) -> List[Dict]:
    exps = [dict(e) for e in _EXPERIENCES]
    for exp in exps:
        exp["_score"] = sum(1 for sk in job_skills if sk in exp["keywords"])
    exps.sort(key=lambda e: e["_score"], reverse=True)
    return exps


_EN_SKILLS_GROUPED = [
    ("GIS / Geomatics", [
        "QGIS", "ArcGIS Pro (ArcMap)", "FME", "PostGIS", "AutoCAD",
        "GeoAcces / GeoIndex", "PhpPgAdmin",
    ]),
    ("Programming & Data", [
        "Python (geospatial automation)", "Google Cloud BigQuery",
        "Studio3T", "SQL / NoSQL",
    ]),
    ("Remote Sensing & Cartography", [
        "Satellite image interpretation", "Aerial stereo-restitution",
        "Automated thematic mapping", "Interactive webmapping",
    ]),
    ("Spatial Analysis & Field", [
        "Intersections / Buffers / Overlays", "Spatial risk analysis",
        "Advanced geoprocessing", "Field data collection / QSHE",
    ]),
]

_EN_KW_SKILL_MAP = {
    "qgis":           ("GIS / Geomatics", "QGIS"),
    "arcgis":         ("GIS / Geomatics", "ArcGIS Pro (ArcMap)"),
    "fme":            ("GIS / Geomatics", "FME"),
    "postgis":        ("GIS / Geomatics", "PostGIS"),
    "python":         ("Programming & Data", "Python (geospatial automation)"),
    "automation":     ("Programming & Data", "Python (geospatial automation)"),
    "bigquery":       ("Programming & Data", "Google Cloud BigQuery"),
    "remote sensing": ("Remote Sensing & Cartography", "Satellite image interpretation"),
    "cartography":    ("Remote Sensing & Cartography", "Automated thematic mapping"),
    "webmapping":     ("Remote Sensing & Cartography", "Interactive webmapping"),
    "spatial":        ("Spatial Analysis & Field", "Intersections / Buffers / Overlays"),
    "risk":           ("Spatial Analysis & Field", "Spatial risk analysis"),
    "field":          ("Spatial Analysis & Field", "Field data collection / QSHE"),
    "flood":          ("Spatial Analysis & Field", "Spatial risk analysis"),
}

_EN_EXPERIENCES = [
    {
        "title": "Geomatics & GIS Intern",
        "company": "Senelec - National Electricity Company",
        "period": "Feb. 2026 - Apr. 2026  |  Dakar, Senegal",
        "bullets": [
            "Automated cartography of electrical infrastructure in flood-prone zones",
            "Python automation of GIS data pipelines (updates, thematic maps)",
            "Advanced spatial analysis: intersections, buffers, overlays (QGIS, ArcGIS Pro)",
            "Built interactive webmapping application to visualize risk zones",
            "Managed geospatial databases (PostGIS, BigQuery, Studio3T)",
        ],
        "keywords": {
            "gis", "python", "automation", "webmapping", "infrastructure",
            "flood", "energy", "risk", "spatial", "qgis", "cartography",
            "postgis", "bigquery", "cloud",
        },
    },
    {
        "title": "Airport Operations Intern",
        "company": "Blaise Diagne International Airport (AIBD)",
        "period": "Summer 2025  |  Dakar, Senegal",
        "bullets": [
            "Managed and integrated geospatial databases via FME and QGIS",
            "Performed aerial stereo-restitution and high-resolution photointerpretation",
            "QSHE field inspections and airport infrastructure assessment",
            "Applied remote sensing to precision agriculture (satellite imagery)",
            "Collected and validated geospatial field data",
        ],
        "keywords": {
            "fme", "field", "infrastructure", "inspection", "environment",
            "qshe", "qgis", "remote sensing", "agriculture", "transport",
        },
    },
]


def _is_english_job(job: Dict) -> bool:
    """Detecte si l'offre est principalement en anglais."""
    text = f"{job.get('title','')} {job.get('description','')[:500]}".lower()
    en_kw = ["intern", "internship", "co-op", "coop", "geomatics", "gis technician",
             "gis analyst", "remote sensing", "spatial analyst", "mapping technician",
             "environmental technician", "natural resources"]
    fr_kw = ["stage", "stagiaire", "alternance", "geomatique", "environnement",
             "teledetection", "cartographie", "amenagement"]
    en_score = sum(1 for k in en_kw if k in text)
    fr_score = sum(1 for k in fr_kw if k in text)
    # Anglais si le titre est en anglais OU si score anglais > français
    title = job.get("title", "").lower()
    title_is_en = any(k in title for k in ["intern", "technician", "analyst", "specialist", "officer"])
    title_is_fr = any(k in title for k in ["stage", "stagiaire", "charg", "geomati"])
    if title_is_en and not title_is_fr:
        return True
    return en_score > fr_score


# ─── Point d'entree public ────────────────────────────────────────────────────

def generate_adapted_cv(job: Dict) -> bytes:
    """
    Genere un CV PDF adapte ATS en < 5 secondes pour une offre donnee.
    Retourne les bytes PDF a attacher directement a l'email de candidature.
    Retourne b"" si fpdf2 n'est pas installe.
    """
    if not _FPDF_OK:
        logger.warning("fpdf2 non installe — CV adapte indisponible (pip install fpdf2)")
        return b""

    job_skills = detect_job_skills(job)
    country    = detect_country(job)
    job_title  = job.get("title", "poste en geomatique")
    company    = job.get("company", "")
    en         = _is_english_job(job)  # True = CV en anglais

    pdf = _AtsCV()
    pdf.setup()
    pdf.add_page()

    # ── En-tete ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(*pdf._c(pdf.BG))
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_y(7)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*pdf._c(pdf.PRI))
    pdf.cell(0, 9, "MODOU KHABANE MBAYE", ln=True, align="C")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*pdf._c(pdf.MED))
    p = PROFILE_EN if en else PROFILE
    pdf.cell(0, 5,
        _safe(f"{p['email']}  |  {p['phone']}  |  Sherbrooke, QC, Canada"),
        ln=True, align="C")
    pdf.cell(0, 5,
        _safe(f"LinkedIn : {p['linkedin']}   Portfolio : {p['portfolio']}"),
        ln=True, align="C")
    pdf.set_y(34)

    # ── Profil professionnel (tailore ATS) ───────────────────────────────────
    pdf.section_title("Professional Profile" if en else "Profil professionnel")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*pdf._c(pdf.DARK))
    if en:
        skills_str = ", ".join(job_skills[:4]) if job_skills else "GIS, remote sensing, Python, spatial analysis"
        summary_en = _safe(
            f"2nd-year student in Applied Geomatics for the Environment "
            f"(Universite de Sherbrooke, co-op program), applying for the position of "
            f"{job_title}. Key skills: {skills_str}. "
            f"Two hands-on GIS/geomatics internships in demanding international environments."
        )
        pdf.multi_cell(0, 5, summary_en)
    else:
        pdf.multi_cell(0, 5, _profile_summary(job_skills, job_title, company, country))

    # ── Competences (reordonnees par pertinence) ─────────────────────────────
    CONTENT_W = 210 - 2 * pdf.MAR
    LABEL_W   = 58
    ITEMS_W   = CONTENT_W - LABEL_W

    skills_groups = _en_ordered_skills(job_skills) if en else _ordered_skills(job_skills)
    pdf.section_title("Technical Skills" if en else "Competences techniques")
    for grp_name, items in skills_groups:
        y0 = pdf.get_y()
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*pdf._c(pdf.PRI))
        pdf.cell(LABEL_W, 5, _safe(grp_name + ":"), ln=False)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*pdf._c(pdf.DARK))
        pdf.multi_cell(ITEMS_W, 5, _safe("  |  ".join(items)))
        if pdf.get_y() - y0 < 5:
            pdf.ln(1)

    # ── Formation ────────────────────────────────────────────────────────────
    pdf.section_title("Education" if en else "Formation")
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*pdf._c(pdf.DARK))
    if en:
        pdf.cell(0, 5, "B.Sc. Applied Geomatics for the Environment", ln=True)
        pdf.italic_small("Universite de Sherbrooke - Co-operative program | Environmental Management  (2024 - 2027)")
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(0, 5, "DEC in Natural Sciences", ln=True)
        pdf.italic_small("Cegep de Sherbrooke  (2022 - 2024)")
    else:
        pdf.cell(0, 5, "Baccalaureat en Geomatique appliquee a l'environnement", ln=True)
        pdf.italic_small("Universite de Sherbrooke - Programme cooperatif | Concentration : Gestion environnementale  (2024 - 2027)")
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(0, 5, "DEC en Sciences de la Nature", ln=True)
        pdf.italic_small("Cegep de Sherbrooke  (2022 - 2024)")

    # ── Experiences (experience la plus pertinente en premier) ────────────────
    experiences = _en_ordered_experiences(job_skills) if en else _ordered_experiences(job_skills)
    pdf.section_title("Professional Experience" if en else "Experiences professionnelles")
    for exp in experiences:
        pdf.exp_header(_safe(exp["title"]), _safe(exp["period"]))
        pdf.italic_small(_safe(exp["company"]))
        for b in exp["bullets"]:
            pdf.bullet_line(_safe(b))
        pdf.ln(2)

    # ── Projet academique ─────────────────────────────────────────────────────
    pdf.section_title("Academic Project" if en else "Projet academique notable")
    if en:
        pdf.exp_header("Mining Cartography - Aldermac Site", "Fall 2024")
        pdf.italic_small("GMQ157 Course - Universite de Sherbrooke")
        for b in [
            "Integration of topographic surveys, aerial imagery and historical datasets",
            "Production of complete thematic maps (georeferencing, advanced spatial analysis)",
        ]:
            pdf.bullet_line(b)
    else:
        pdf.exp_header("Cartographie miniere - Site Aldermac", "Automne 2024")
        pdf.italic_small("Cours GMQ157 - Universite de Sherbrooke")
        for b in [
            "Integration de releves topographiques, images aeriennes et donnees historiques",
            "Production de cartes thematiques completes (georeferencement, analyse spatiale avancee)",
        ]:
            pdf.bullet_line(b)

    # ── Langues ───────────────────────────────────────────────────────────────
    pdf.section_title("Languages" if en else "Langues")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*pdf._c(pdf.DARK))
    if en:
        pdf.cell(0, 5,
            "French: native (5/5)   |   English: intermediate (3/5)   |   Wolof: native (5/5)",
            ln=True)
    else:
        pdf.cell(0, 5,
            "Francais : natif (5/5)   |   Anglais : intermediaire (3/5)   |   Wolof : natif (5/5)",
            ln=True)

    result = bytes(pdf.output())
    logger.info(f"CV adapte ATS genere : {len(result)//1024} Ko  ['{job_title}' @ {company}]")
    return result
