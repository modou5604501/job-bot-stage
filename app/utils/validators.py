from typing import Dict

def validate_job_data(job: Dict) -> bool:
    """Valide les données d'une offre"""
    required_fields = ["title", "company", "description", "url"]
    for field in required_fields:
        if not job.get(field):
            return False
    return True

def validate_analysis_result(result: Dict) -> bool:
    """Valide le résultat d'analyse Claude"""
    if not isinstance(result, dict):
        return False
    required_keys = ["relevant", "score", "reason"]
    for key in required_keys:
        if key not in result:
            return False
    return True