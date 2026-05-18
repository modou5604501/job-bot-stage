"""
Moteur de generation de lettres de motivation
Adapte chaque lettre au poste specifique en matchant les competences du profil
avec les exigences detectees dans l'offre.
"""
from typing import List, Dict
from app.config.user_profile import PROFILE, PROFILE_EN

# Competences du candidat avec descriptions detaillees
CANDIDATE_SKILLS = {
    "qgis":             "QGIS (cartographie, analyse spatiale, production de cartes thematiques)",
    "arcgis":           "ArcGIS Pro et ArcMap (geotraitement, analyse spatiale avancee)",
    "arcmap":           "ArcGIS Pro et ArcMap (geotraitement, analyse spatiale avancee)",
    "arcgis pro":       "ArcGIS Pro (modelisation spatiale, analyse avancee)",
    "fme":              "FME (transformation et integration de donnees geospatiales, connexion BDD)",
    "python":           "Python (automatisation geospatiale, flux de traitement SIG, scripts VSCode)",
    "automatisation":   "Automatisation Python des flux SIG (mise a jour donnees, cartes automatisees)",
    "automation":       "Python geospatial automation (SIG data pipelines, automated mapping)",
    "webmapping":       "Developpement d'applications webmapping interactives (visualisation geospatiale)",
    "web mapping":      "Interactive web mapping application development",
    "sig":              "SIG — conception, gestion, analyse et automatisation de donnees geospatiales",
    "gis":              "GIS — spatial analysis, mapping, automation and geoprocessing",
    "geomatique":       "Geomatique appliquee (SIG, cartographie, teledetection, automatisation Python)",
    "geomatics":        "Geomatics (spatial analysis, cartography, remote sensing, Python automation)",
    "teledetection":    "Teledetection et interpretation d'images satellitaires",
    "remote sensing":   "Remote sensing and satellite image interpretation",
    "cartographie":     "Cartographie et production automatisee de cartes thematiques (QGIS, ArcGIS)",
    "cartography":      "Cartography and automated thematic map production",
    "postgis":          "PostGIS (bases de donnees geospatiales)",
    "autocad":          "AutoCAD (dessin technique et cartographie)",
    "lidar":            "LiDAR (acquisition et traitement de donnees 3D)",
    "drone":            "Drone et photogrammetrie aerienne",
    "stereorestitution":"Stereorestitution et analyse visuelle d'images aeriennes",
    "environnement":    "Gestion environnementale et evaluation d'impact (QSHE, inspections terrain)",
    "environment":      "Environmental management and impact assessment (QSHE)",
    "ecologie":         "Analyse ecologique et gestion des milieux naturels",
    "ecology":          "Ecological analysis and natural environment management",
    "hydrologie":       "Hydrologie et gestion des ressources en eau",
    "inondation":       "Cartographie et analyse spatiale des zones d'inondation (buffers, intersections SIG)",
    "flood":            "Flood zone mapping and spatial risk analysis (GIS buffers, intersections)",
    "infrastructure":   "Cartographie d'infrastructures et analyse de vulnerabilite spatiale",
    "terrain":          "Collecte et validation de donnees sur le terrain",
    "field":            "Field data collection and validation",
    "bases de donnees": "Gestion de bases de donnees geospatiales (Studio3T, BigQuery, PostGIS, PhpPgAdmin)",
    "database":         "Geospatial database management (Studio3T, BigQuery, PostGIS)",
    "analyse spatiale": "Analyse spatiale avancee (intersections, buffers, overlays, geotraitement)",
    "spatial analysis": "Advanced spatial analysis (intersections, buffers, overlays, geoprocessing)",
    "amenagement":      "Amenagement du territoire et planification spatiale (SIG)",
    "urban planning":   "Urban and territorial planning with GIS tools",
    "bigquery":         "Google Cloud BigQuery (traitement et analyse de donnees massives)",
    "cloud":            "Google Cloud BigQuery (traitement de donnees geospatiales a grande echelle)",
    "geoacces":         "GeoAcces et GeoIndex (portails de donnees geospatiales gouvernementaux)",
    "risque":           "Analyse spatiale des risques et vulnerabilite des infrastructures (SIG)",
    "risk":             "Spatial risk analysis and infrastructure vulnerability mapping (GIS)",
    "urbanisme":        "SIG applique a l'urbanisme et a la planification territoriale",
    "foresterie":       "Teledetection et SIG appliques a la gestion forestiere",
    "forestry":         "Remote sensing and GIS for forest management and monitoring",
    "agriculture":      "Teledetection appliquee a l'agriculture de precision (images satellitaires)",
    "mining":           "Cartographie miniere et analyse spatiale des sites industriels",
    "minier":           "Cartographie de sites miniers et integration de donnees multisources",
    "energie":          "Cartographie des infrastructures energetiques et analyse spatiale des risques",
    "energy":           "Energy infrastructure mapping and spatial risk analysis (GIS)",
    "transport":        "SIG applique aux reseaux de transport et a l'analyse de flux",
    "municipal":        "SIG et cartographie pour la gestion municipale et la planification urbaine",
}

# Projets du candidat
CANDIDATE_PROJECTS = [
    {
        "name": "Stage Senelec — Geomatique et SIG (Fev.-Avr. 2026)",
        "description": (
            "Stage en geomatique chez Senelec (Senegal) : cartographie automatisee des infrastructures "
            "electriques exposees aux zones d'inondation, developpement de flux d'automatisation Python "
            "pour la gestion et la mise a jour des donnees SIG, analyses spatiales (intersections, buffers), "
            "developpement d'une application webmapping interactive pour visualiser les infrastructures "
            "vulnerables, automatisation de la production de cartes thematiques."
        ),
        "keywords": [
            "sig", "gis", "python", "automatisation", "automation", "webmapping", "web mapping",
            "infrastructure", "inondation", "flood", "reseau", "network", "qgis", "cartographie",
            "energie", "energy", "risque", "risk", "spatial", "analyse spatiale"
        ]
    },
    {
        "name": "Cartographie Mine Aldermac (Automne 2024)",
        "description": (
            "Cartographie complete d'un site minier abandonne (cours GMQ157) : integration de releves "
            "topographiques, d'images aeriennes et de donnees historiques pour produire une serie de "
            "cartes thematiques. Maitrise du georeferencement et de l'analyse spatiale avancee."
        ),
        "keywords": [
            "cartographie", "cartography", "topographie", "spatial", "qgis", "arcgis",
            "mining", "minier", "industriel", "multisource", "aerien"
        ]
    },
    {
        "name": "Stage Aeroport Blaise Diagne — Operations (Ete 2025)",
        "description": (
            "Stage en operations aeroportuaires : gestion de bases de donnees geospatiales via FME, "
            "production de cartes sur QGIS, stereorestitution, inspection terrain QSHE, "
            "optimisation des flux de circulation, collecte de donnees pour l'evaluation des infrastructures."
        ),
        "keywords": [
            "fme", "terrain", "field", "donnees", "data", "infrastructure", "inspection",
            "environnement", "qshe", "qgis", "stereorestitution", "transport"
        ]
    },
    {
        "name": "Teledetection appliquee a l'agriculture de precision",
        "description": (
            "Analyse et interpretation d'images satellitaires pour le suivi des cultures agricoles. "
            "Application de la teledetection pour l'agriculture de precision."
        ),
        "keywords": [
            "teledetection", "remote sensing", "satellite", "agriculture", "image", "precision",
            "foresterie", "forestry", "environnement"
        ]
    },
]


def detect_job_skills(job: Dict) -> List[str]:
    """Detecte les competences requises dans l'offre"""
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    matched = []
    for skill_key in CANDIDATE_SKILLS:
        if skill_key in text:
            matched.append(skill_key)
    return list(set(matched))


def find_relevant_projects(job_skills: List[str]) -> List[Dict]:
    """Trouve les projets du candidat les plus pertinents pour l'offre"""
    scored = []
    for project in CANDIDATE_PROJECTS:
        score = sum(1 for kw in project["keywords"] if kw in job_skills)
        if score > 0:
            scored.append((score, project))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:2]]


def detect_country(job: Dict) -> str:
    """Detecte le pays de l'offre pour adapter le style"""
    text = f"{job.get('location', '')} {job.get('region', '')}".lower()
    if any(k in text for k in ["france", "paris", "lyon", "bordeaux", "fr"]):
        return "France"
    if any(k in text for k in ["suisse", "switzerland", "geneve", "zurich", "lausanne", "ch"]):
        return "Suisse"
    if any(k in text for k in ["russia", "russie", "moscow", "moscou"]):
        return "Russie"
    return "Canada"


def generate_cover_letter(job: Dict) -> str:
    """
    Genere une lettre de motivation entierement adaptee a l'offre.
    """
    title = job.get("title", "le poste")
    company = job.get("company", "votre organisation")
    location = job.get("location", "")
    country = detect_country(job)
    job_skills = detect_job_skills(job)
    relevant_projects = find_relevant_projects(job_skills)

    # ---- Paragraphe 1 : accroche adaptee au pays et au poste ----
    if country == "France":
        opening = (
            f"Actuellement etudiant en deuxieme annee de Baccalaureat en Geomatique appliquee "
            f"a l'environnement a l'Universite de Sherbrooke (Canada), dans le cadre d'un programme "
            f"cooperatif, je me permets de soumettre ma candidature pour le poste de {title} "
            f"au sein de {company}."
        )
    elif country == "Suisse":
        opening = (
            f"Etudiant en Geomatique appliquee a l'environnement a l'Universite de Sherbrooke "
            f"(Canada), je suis a la recherche d'un stage international enrichissant. "
            f"C'est avec un vif interet que je postule au poste de {title} propose par {company}."
        )
    else:
        opening = (
            f"Etudiant en deuxieme annee de Baccalaureat en Geomatique appliquee a l'environnement "
            f"a l'Universite de Sherbrooke (programme cooperatif), je souhaite poser ma candidature "
            f"pour le poste de {title} au sein de {company}."
        )

    # ---- Paragraphe 2 : competences specifiques matchees avec l'offre ----
    if job_skills:
        skill_descriptions = [CANDIDATE_SKILLS[s] for s in job_skills if s in CANDIDATE_SKILLS]
        # Limiter a 3 competences pour ne pas surcharger
        skill_list = skill_descriptions[:3]
        skills_para = (
            f"Mon profil correspond directement aux exigences de ce poste. "
            f"Je maitrise notamment : {' ; '.join(skill_list)}. "
            f"Ces competences ont ete developpees dans le cadre de ma formation "
            f"et de mes experiences pratiques."
        )
    else:
        skills_para = (
            f"Ma formation en geomatique m'a permis de developper des competences solides "
            f"en analyse spatiale, cartographie (QGIS, ArcGIS Pro), teledetection, "
            f"et gestion de donnees geospatiales (FME, Python, PostGIS)."
        )

    # ---- Paragraphe 3 : projets pertinents ----
    if relevant_projects:
        proj = relevant_projects[0]
        projects_para = (
            f"En particulier, le projet '{proj['name']}' illustre ma capacite a mener "
            f"des travaux concrets : {proj['description']}"
        )
    else:
        projects_para = (
            f"Lors de mon stage a l'Aeroport International Blaise Diagne (Senegal), "
            f"j'ai realise la cartographie du reseau electrique expose aux inondations via les SIG, "
            f"gere des bases de donnees FME et effectue des inspections terrain QSHE — "
            f"une experience qui m'a prepare a intervenir dans des contextes operationnels exigeants."
        )

    # ---- Paragraphe 4 : motivation specifique a l'entreprise/pays ----
    if country == "France":
        motivation = (
            f"La France, avec son ecosysteme d'excellence en geomatique et environnement, "
            f"represente pour moi une opportunite unique de developper mes competences dans un "
            f"contexte europeen stimulant. Rejoindre {company} me permettrait de contribuer "
            f"concretement a vos projets tout en enrichissant mon parcours."
        )
    elif country == "Suisse":
        motivation = (
            f"La Suisse, reconnue mondialement pour son excellence en ingenierie et innovation "
            f"environnementale, represente un cadre ideal pour un stage international de haut niveau. "
            f"Rejoindre {company} serait une opportunite exceptionnelle de m'immerger dans "
            f"un environnement multiculturel et techniquement exigeant."
        )
    else:
        motivation = (
            f"Vos activites dans ce domaine correspondent parfaitement a mes aspirations "
            f"professionnelles et a ma formation. Je suis convaincu de pouvoir apporter "
            f"une contribution significative a votre equipe."
        )

    # ---- Disponibilite et remuneration ----
    availability = (
        f"Je suis disponible pour un stage de 3 a 4 mois, a partir de septembre 2026 "
        f"jusqu'en decembre 2026, en presentiel ou en format hybride selon vos besoins. "
        f"Je suis ouvert a la remuneration selon les conventions en vigueur dans votre organisation."
    )

    # ---- Composition finale ----
    letter = f"""{opening}

{skills_para}

{projects_para}

{motivation}

{availability}

Disponible pour un entretien a votre convenance, je reste a votre disposition pour tout complement d'information. Vous trouverez mon CV, mon profil LinkedIn ({PROFILE['linkedin']}) et mon portfolio ({PROFILE['portfolio']}) en complement de cette candidature.

Dans l'attente de votre retour, veuillez agreer, Madame, Monsieur, l'expression de mes salutations distinguees.

Modou Khabane Mbaye
{PROFILE['phone']} | {PROFILE['email']}
LinkedIn : {PROFILE['linkedin']}
Portfolio : {PROFILE['portfolio']}"""

    return letter


# ─── Version anglaise ─────────────────────────────────────────────────────────

CANDIDATE_SKILLS_EN = {
    "qgis":             "QGIS (cartography, spatial analysis, thematic map production)",
    "arcgis":           "ArcGIS Pro and ArcMap (geoprocessing, advanced spatial analysis)",
    "arcmap":           "ArcGIS Pro and ArcMap (geoprocessing, advanced spatial analysis)",
    "arcgis pro":       "ArcGIS Pro (spatial modelling, advanced analysis)",
    "fme":              "FME (geospatial data transformation and database integration)",
    "python":           "Python (geospatial automation, GIS data pipelines, scripting)",
    "automatisation":   "Python automation of GIS workflows (data updates, automated maps)",
    "automation":       "Python geospatial automation (GIS data pipelines, automated mapping)",
    "webmapping":       "Interactive webmapping application development",
    "web mapping":      "Interactive web mapping application development",
    "sig":              "GIS — design, management, analysis and automation of geospatial data",
    "gis":              "GIS — spatial analysis, mapping, automation and geoprocessing",
    "geomatique":       "Applied Geomatics (GIS, cartography, remote sensing, Python automation)",
    "geomatics":        "Geomatics (spatial analysis, cartography, remote sensing, Python automation)",
    "teledetection":    "Remote sensing and satellite image interpretation",
    "remote sensing":   "Remote sensing and satellite image interpretation",
    "cartographie":     "Cartography and automated thematic map production (QGIS, ArcGIS)",
    "cartography":      "Cartography and automated thematic map production",
    "postgis":          "PostGIS (geospatial databases)",
    "autocad":          "AutoCAD (technical drawing and cartography)",
    "lidar":            "LiDAR (3D data acquisition and processing)",
    "drone":            "Drone and aerial photogrammetry",
    "stereorestitution":"Stereo-restitution and visual analysis of aerial imagery",
    "environnement":    "Environmental management and impact assessment (QSHE, field inspections)",
    "environment":      "Environmental management and impact assessment (QSHE)",
    "ecologie":         "Ecological analysis and natural environment management",
    "ecology":          "Ecological analysis and natural environment management",
    "hydrologie":       "Hydrology and water resource management",
    "inondation":       "Flood zone mapping and spatial risk analysis (GIS buffers, intersections)",
    "flood":            "Flood zone mapping and spatial risk analysis (GIS buffers, intersections)",
    "infrastructure":   "Infrastructure mapping and spatial vulnerability analysis",
    "terrain":          "Field data collection and validation",
    "field":            "Field data collection and validation",
    "bases de donnees": "Geospatial database management (Studio3T, BigQuery, PostGIS, PhpPgAdmin)",
    "database":         "Geospatial database management (Studio3T, BigQuery, PostGIS)",
    "analyse spatiale": "Advanced spatial analysis (intersections, buffers, overlays, geoprocessing)",
    "spatial analysis": "Advanced spatial analysis (intersections, buffers, overlays, geoprocessing)",
    "amenagement":      "Territorial planning and spatial planning (GIS)",
    "urban planning":   "Urban and territorial planning with GIS tools",
    "bigquery":         "Google Cloud BigQuery (large-scale geospatial data processing)",
    "cloud":            "Google Cloud BigQuery (large-scale geospatial data processing)",
    "risque":           "Spatial risk analysis and infrastructure vulnerability mapping (GIS)",
    "risk":             "Spatial risk analysis and infrastructure vulnerability mapping (GIS)",
    "urbanisme":        "GIS applied to urban planning and territorial management",
    "foresterie":       "Remote sensing and GIS for forest management",
    "forestry":         "Remote sensing and GIS for forest management and monitoring",
    "agriculture":      "Remote sensing applied to precision agriculture (satellite imagery)",
    "energie":          "Energy infrastructure mapping and spatial risk analysis",
    "energy":           "Energy infrastructure mapping and spatial risk analysis (GIS)",
    "transport":        "GIS applied to transport networks and flow analysis",
    "municipal":        "GIS and cartography for municipal management and urban planning",
    "conservation":     "Spatial analysis for environmental conservation and biodiversity monitoring",
    "wildlife":         "Remote sensing and spatial analysis for wildlife habitat monitoring",
    "natural resources":"GIS and remote sensing for natural resource management",
}

_EN_PROJECT_DESCRIPTIONS = [
    {
        "name": "Geomatics & GIS Internship — Senelec (Feb.–Apr. 2026)",
        "description": (
            "Automated cartography of electrical infrastructure in flood-prone zones (QGIS, ArcGIS Pro). "
            "Built Python pipelines for GIS data updates and thematic map production. "
            "Developed an interactive webmapping application to visualize risk zones. "
            "Managed geospatial databases (PostGIS, BigQuery, Studio3T)."
        ),
        "keywords": [
            "sig", "gis", "python", "automatisation", "automation", "webmapping", "web mapping",
            "infrastructure", "inondation", "flood", "qgis", "cartographie", "cartography",
            "energie", "energy", "risque", "risk", "spatial", "analyse spatiale", "postgis",
        ],
    },
    {
        "name": "Airport Operations Internship — Blaise Diagne International Airport (Summer 2025)",
        "description": (
            "Managed and integrated geospatial databases using FME and QGIS. "
            "Performed aerial stereo-restitution and high-resolution photointerpretation. "
            "Applied remote sensing to precision agriculture (satellite imagery). "
            "QSHE field inspections and airport infrastructure assessment."
        ),
        "keywords": [
            "fme", "terrain", "field", "infrastructure", "inspection", "environnement",
            "environment", "qshe", "qgis", "stereorestitution", "transport", "teledetection",
            "remote sensing", "agriculture",
        ],
    },
    {
        "name": "Mining Cartography — Aldermac Site (Fall 2024)",
        "description": (
            "Produced complete thematic maps integrating topographic surveys, aerial imagery and "
            "historical datasets. Applied advanced georeferencing and spatial analysis techniques."
        ),
        "keywords": [
            "cartographie", "cartography", "topographie", "spatial", "qgis", "arcgis",
            "mining", "minier",
        ],
    },
]


def _find_relevant_projects_en(job_skills: List[str]) -> List[Dict]:
    scored = []
    for proj in _EN_PROJECT_DESCRIPTIONS:
        score = sum(1 for kw in proj["keywords"] if kw in job_skills)
        if score > 0:
            scored.append((score, proj))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:1]]


def generate_cover_letter_en(job: Dict) -> str:
    """English cover letter — used for English-language job postings."""
    title = job.get("title", "the position")
    company = job.get("company", "your organization")
    job_skills = detect_job_skills(job)
    relevant_projects = _find_relevant_projects_en(job_skills)

    # Opening
    opening = (
        f"I am a 2nd-year student in Applied Geomatics for the Environment at "
        f"Universite de Sherbrooke (Canada), co-operative program, "
        f"and I am writing to apply for the {title} position at {company}."
    )

    # Skills paragraph
    if job_skills:
        en_skill_descs = [CANDIDATE_SKILLS_EN.get(s, "") for s in job_skills if s in CANDIDATE_SKILLS_EN]
        en_skill_descs = [d for d in en_skill_descs if d][:3]
        skills_para = (
            f"My profile directly matches the requirements of this position. "
            f"Key competencies I bring: {' ; '.join(en_skill_descs)}. "
            f"These skills were built through my academic training and two hands-on geomatics internships."
        )
    else:
        skills_para = (
            f"My geomatics training has given me solid skills in spatial analysis, "
            f"cartography (QGIS, ArcGIS Pro), remote sensing, "
            f"and geospatial data management (FME, Python, PostGIS)."
        )

    # Project paragraph
    if relevant_projects:
        proj = relevant_projects[0]
        projects_para = (
            f"In particular, my {proj['name']} demonstrates my ability to deliver concrete results: "
            f"{proj['description']}"
        )
    else:
        projects_para = (
            f"During my internship at Senelec (Senegal, Feb.-Apr. 2026), I automated the cartography "
            f"of electrical infrastructure exposed to flooding, built Python GIS pipelines, "
            f"and developed an interactive webmapping application — preparing me for "
            f"technically demanding environments."
        )

    # Motivation
    motivation = (
        f"Your work in this field aligns closely with my professional goals and academic background. "
        f"I am confident I can make a meaningful contribution to your team "
        f"while further developing my expertise."
    )

    # Availability
    availability = (
        f"I am available for a 3-4 month internship from September to December 2026, "
        f"on-site or hybrid as required. I am open to compensation as per your organization's guidelines."
    )

    letter = (
        f"{opening}\n\n"
        f"{skills_para}\n\n"
        f"{projects_para}\n\n"
        f"{motivation}\n\n"
        f"{availability}\n\n"
        f"I would welcome the opportunity to discuss my application further. "
        f"Please find my resume, LinkedIn profile ({PROFILE_EN['linkedin']}) "
        f"and portfolio ({PROFILE_EN['portfolio']}) attached.\n\n"
        f"Yours sincerely,\n\n"
        f"Modou Khabane Mbaye\n"
        f"{PROFILE_EN['phone']} | {PROFILE_EN['email']}\n"
        f"LinkedIn: {PROFILE_EN['linkedin']}\n"
        f"Portfolio: {PROFILE_EN['portfolio']}"
    )
    return letter
