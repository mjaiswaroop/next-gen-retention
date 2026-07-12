import logging
import json
import random
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from config import settings
from google import genai
from services.causal_service import estimate_uplift

logger = logging.getLogger("retention_core.ab_factory")

try:
    gemini_client = genai.Client(api_key=settings.gemini_api_key or "DUMMY")
except Exception as e:
    logger.warning(f"Failed to init Gemini client: {e}")
    gemini_client = None

class CampaignVariant(BaseModel):
    subject: str = Field(description="The email subject line.")
    body: str = Field(description="The body of the email.")
    tone: str = Field(description="The tone of this variant (e.g. Data-driven, Emotional, Direct).")

class CampaignVariantsResponse(BaseModel):
    variants: List[CampaignVariant]

class CampaignOptimizerService:
    def __init__(self, db_session):
        self.db = db_session

    def generate_variants(self, base_prompt: str, target_audience: str) -> List[Dict[str, str]]:
        """Uses LLM to automatically generate 3 distinct A/B testing variants."""
        if not gemini_client or not settings.gemini_api_key:
            # Mock fallback
            return [
                {"subject": "We miss you!", "body": "Come back for 10% off.", "tone": "Direct"},
                {"subject": "Is everything ok?", "body": "We noticed you haven't logged in.", "tone": "Emotional"},
                {"subject": "Unlock new features", "body": "See what you missed.", "tone": "Data-driven"},
            ]

        sys_prompt = f"""You are an elite marketing AI. Your goal is to generate exactly 3 distinct email variants for an A/B test.
The target audience is: {target_audience}
The base idea/offer is: {base_prompt}

Generate 3 variants with entirely different psychological angles (e.g., Loss Aversion, Value-Add, Emotional Connection)."""

        try:
            res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[sys_prompt],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CampaignVariantsResponse,
                    temperature=0.7
                )
            )
            data = json.loads(res.text)
            return data.get("variants", [])
        except Exception as e:
            logger.error(f"Variant generation failed: {e}")
            return []

    def simulate_live_test(self, variants: List[Dict[str, str]], sample_size_per_variant: int = 100) -> Dict[str, Any]:
        """
        Simulates deploying the variants to a small cohort and measuring causal uplift.
        In reality, this would wait days for actual metrics. We simulate the metric collection here.
        """
        results = []
        for i, variant in enumerate(variants):
            # Mocking the causal uplift measurement for each variant
            # In a real system, we would assign users, wait, and calculate uplift using CausalML
            base_uplift = random.uniform(0.02, 0.15)
            
            # Add some logic based on tone
            if "Emotional" in str(variant.get("tone", "")):
                base_uplift += 0.05
                
            results.append({
                "variant_id": i + 1,
                "variant": variant,
                "sample_size": sample_size_per_variant,
                "measured_uplift": round(base_uplift, 4),
                "confidence_interval": [round(base_uplift - 0.02, 4), round(base_uplift + 0.02, 4)]
            })
            
        # Determine winner
        if not results:
            return {"error": "No valid variants provided for simulation"}
            
        best_variant = max(results, key=lambda x: x["measured_uplift"])
        
        return {
            "status": "Test Completed",
            "winner_id": best_variant["variant_id"],
            "winner_uplift": best_variant["measured_uplift"],
            "results": results
        }
