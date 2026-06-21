import logging
import json
from typing import List, Dict
from pydantic import BaseModel, Field

from config import settings
from google import genai

logger = logging.getLogger("retention_core.radar")

try:
    gemini_client = genai.Client(api_key=settings.anthropic_api_key or "DUMMY")
except Exception as e:
    logger.warning(f"Failed to init Gemini client: {e}")
    gemini_client = None

class CompetitorAlert(BaseModel):
    competitor_name: str = Field(description="The name of the competitor.")
    threat_level: str = Field(description="Threat level: Low, Medium, High, or Critical.")
    event_description: str = Field(description="What the competitor just did (e.g. launched a feature, dropped price).")
    impact_analysis: str = Field(description="How this impacts our specific customer base and churn risk.")
    recommended_action: str = Field(description="Action to take to mitigate the churn risk.")

class RadarResponse(BaseModel):
    alerts: List[CompetitorAlert]

class RadarService:
    def scan_market(self) -> List[Dict]:
        """
        Simulates an autonomous agent scraping the web for competitor news,
        cross-referencing it with our internal churn reasons, and generating alerts.
        """
        if not gemini_client or not settings.anthropic_api_key:
            return [{
                "competitor_name": "RivalCorp",
                "threat_level": "High",
                "event_description": "RivalCorp just launched an AI-powered automated reporting feature.",
                "impact_analysis": "30% of our recent churns cited 'lack of reporting automation' as a reason for leaving. This launch directly targets our vulnerable segment.",
                "recommended_action": "Immediately launch a win-back campaign to the 'Reporting Heavy' segment offering early access to our upcoming beta feature."
            }]

        sys_prompt = """You are an Autonomous Competitor Intelligence Agent.
Your job is to scan the market (simulated) and cross-reference competitor actions with our internal churn data.
Generate 1 or 2 critical competitor defection alerts.
Make the events sound highly realistic for a B2B SaaS company.
Output as JSON."""

        try:
            res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[sys_prompt],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RadarResponse,
                    temperature=0.8
                )
            )
            data = json.loads(res.text)
            return data.get("alerts", [])
        except Exception as e:
            logger.error(f"Radar scan failed: {e}")
            return []
