import logging
import json
from pydantic import BaseModel, Field
from typing import List

from config import settings
from google import genai
from repositories.customer_repo import CustomerRepository

logger = logging.getLogger("retention_core.simulation")

try:
    gemini_client = genai.Client(api_key=settings.anthropic_api_key or "DUMMY")
except Exception as e:
    logger.warning(f"Failed to init Gemini client: {e}")
    gemini_client = None

class AgentReaction(BaseModel):
    opened: bool = Field(description="Did the customer open the email?")
    clicked: bool = Field(description="Did the customer click the offer?")
    anger_level: int = Field(description="Anger level after reading, 1 to 10.")
    reply: str = Field(description="The customer's reply to the email, if any.")
    churned: bool = Field(description="Did this email cause them to ultimately churn or stay?")

class SimulationService:
    def __init__(self, db_session):
        self.db = db_session
        self.repo = CustomerRepository(db_session)

    def run_war_game(self, merchant_id: int, segment: str, email_draft: str, sample_size: int = 5) -> dict:
        """
        Takes a subset of customers, instantiates an LLM agent for each based on their telemetry,
        and simulates their reaction to the email draft.
        """
        # Get a subset of customers
        customers = self.repo.get_high_risk_customers(merchant_id, segment=segment, limit=sample_size)
        if not customers:
            return {"error": "No customers found for this segment."}
            
        results = []
        for cust in customers:
            reaction = self._simulate_individual(cust, email_draft)
            results.append({
                "user_id": cust["user_id"],
                "telemetry": cust,
                "reaction": reaction
            })
            
        # Aggregate stats
        total = len(results)
        opened = sum(1 for r in results if r["reaction"]["opened"])
        clicked = sum(1 for r in results if r["reaction"]["clicked"])
        churned = sum(1 for r in results if r["reaction"]["churned"])
        avg_anger = sum(r["reaction"]["anger_level"] for r in results) / total if total > 0 else 0
        
        return {
            "summary": {
                "sample_size": total,
                "open_rate": opened / total if total > 0 else 0,
                "click_rate": clicked / total if total > 0 else 0,
                "churn_rate": churned / total if total > 0 else 0,
                "avg_anger": avg_anger
            },
            "individual_reactions": results
        }

    def _simulate_individual(self, customer_data: dict, email_draft: str) -> dict:
        if not gemini_client or not settings.anthropic_api_key:
            # Fallback mock if LLM is unavailable
            return {
                "opened": True,
                "clicked": customer_data.get("monetary_value", 0) > 100,
                "anger_level": 5,
                "reply": "I might consider this.",
                "churned": customer_data.get("churn_probability", 0) > 0.8
            }
            
        sys_prompt = f"""You are simulating a real customer. Your goal is to react to an email from a company you use.
Here is your current state (telemetry): {json.dumps(customer_data)}
If your 'session_failures' or 'payment_friction_index' are high, you should be very easily angered by generic marketing.
React to the email draft realistically."""

        try:
            res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[sys_prompt + "\n\nEmail Draft:\n" + email_draft],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AgentReaction,
                    temperature=0.4
                )
            )
            return json.loads(res.text)
        except Exception as e:
            logger.error(f"Simulation failed for customer {customer_data['user_id']}: {e}")
            return {
                "opened": False,
                "clicked": False,
                "anger_level": 5,
                "reply": "Error in simulation",
                "churned": True
            }
