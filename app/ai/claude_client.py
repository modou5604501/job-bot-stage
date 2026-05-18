import json
from typing import Dict
from anthropic import AsyncAnthropic
from loguru import logger
from app.config.settings import Settings
from app.ai.prompt_engine import PromptEngine

class ClaudeClient:
    def __init__(self, settings: Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.prompt_engine = PromptEngine()

    async def analyze_job(self, job: Dict) -> Dict:
        """Analyse une offre avec Claude"""
        try:
            prompt = self.prompt_engine.build_analysis_prompt(job)
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.content[0].text
            # Extraire le JSON de la réponse
            # Claude peut entourer le JSON de texte, on cherche le bloc {}
            start = result.find("{")
            end = result.rfind("}") + 1
            if start != -1 and end > start:
                analysis = json.loads(result[start:end])
            else:
                analysis = json.loads(result)
            return analysis

        except Exception as e:
            logger.error(f"Erreur Claude analysis: {e}")
            return {"relevant": False, "score": 0, "reason": str(e)}

    async def generate_cover_letter(self, job: Dict, user_profile: Dict) -> str:
        """Génère une lettre de motivation"""
        try:
            prompt = self.prompt_engine.build_cover_letter_prompt(job, user_profile)
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Erreur génération lettre: {e}")
            return "Erreur génération lettre"
