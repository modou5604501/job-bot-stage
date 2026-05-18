from typing import Dict

class PromptEngine:
    def build_analysis_prompt(self, job: Dict) -> str:
        """Prompt pour analyser la pertinence d'une offre"""
        return f"""
Analyse cette offre d'emploi pour un étudiant cherchant un stage en géomatique OU en environnement.

Offre :
Titre : {job.get('title', '')}
Entreprise : {job.get('company', '')}
Lieu : {job.get('location', '')}
Description : {job.get('description', '')}

Critères de pertinence :
- Géomatique : GIS, SIG, cartographie, télédétection, QGIS, ArcGIS, données spatiales
- Environnement : écologie, gestion environnementale, impact environnemental, biodiversité, eau, forêt
- Stage ou internship (pas un poste permanent)
- Niveau universitaire (baccalauréat ou maîtrise)

Réponds UNIQUEMENT en JSON valide, sans texte autour :
{{
    "relevant": true,
    "score": 8,
    "domain": "géomatique",
    "reason": "explication courte en français",
    "keywords": ["mot1", "mot2"]
}}

Les valeurs possibles pour "domain" : "géomatique", "environnement", "les deux", "autre".
Si l'offre n'est pas pertinente, mets relevant à false et score à 0.
"""

    def build_cover_letter_prompt(self, job: Dict, user_profile: Dict) -> str:
        """Prompt pour générer une lettre de motivation"""
        return f"""Tu es expert en redaction de lettres de motivation pour des etudiants en geomatique et environnement.

Genere une lettre de motivation professionnelle, en francais, adaptee precisement a cette offre.

PROFIL DU CANDIDAT :
Nom : {user_profile.get('name', '')}
Formation : {user_profile.get('formation', '')}
Experience : {user_profile.get('experience', '')}
Competences : {user_profile.get('skills', '')}
Langues : {user_profile.get('languages', '')}
Email : {user_profile.get('email', '')}
Tel : {user_profile.get('phone', '')}
LinkedIn : {user_profile.get('linkedin', '')}
Portfolio : {user_profile.get('portfolio', '')}

OFFRE DE STAGE :
Titre : {job.get('title', '')}
Entreprise : {job.get('company', '')}
Lieu : {job.get('location', '')}
Description : {job.get('description', '')}

INSTRUCTIONS :
- Lettre en francais, professionnelle, 250-320 mots
- Mentionner specifiquement le titre du poste et le nom de l'entreprise
- Mettre en avant les competences du candidat qui matchent exactement l'offre
- Mentionner au moins un projet concret (Mine Aldermac, Senelec ou stage aeroport) en lien avec l'offre
- Adapter le ton selon le pays (Canada : direct et concis / France : plus formel)
- Mentionner clairement la disponibilite : stage de 3 a 4 mois, session automne 2026 (septembre a decembre 2026)
- Terminer avec les coordonnees completes
- NE PAS inventer de competences qui ne sont pas dans le profil
- Commencer directement par "Madame, Monsieur," sans introduction
"""
