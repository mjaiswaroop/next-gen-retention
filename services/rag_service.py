from config import settings

import time

class DataWarehouseConnectionError(Exception):
    """Raised when the analytical matrix is inaccessible."""
    pass

class MockResponse:
    def __init__(self, content: str):
        self.content = content

class MockLLMClient:
    def chat(self, system: str, user: str):
        # Simulate network latency
        time.sleep(1.5)
        
        if "two sentences" in user:
            # Summary request
            summary = "Customer is at critical churn risk due to high frequency of session failures and payment friction. Immediate proactive outreach with a VIP Technical Consultation is highly recommended."
            return MockResponse(summary)
        elif "SUPPORT LOGS" in system:
            # Operator QA request
            if "No support history" in system:
                return MockResponse("The customer has no recorded support history to analyze.")
            return MockResponse("Based on the support logs, the customer has repeatedly experienced payment failures and timeout errors. I suggest escalating their ticket to Level 2 technical support immediately.")
        
        # Generic campaign generation
        return MockResponse(
            "Subject: Special VIP Technical Consultation Just For You!\n\n"
            "Hi there,\n\n"
            "We noticed you've had some trouble with our platform lately. "
            "We apologize for the friction and want to make it right. "
            "Click here to schedule a complimentary VIP Technical Consultation with our engineering team.\n\n"
            "Best,\nThe Customer Success Team"
        )

from sqlalchemy.orm import Session
from models import EventLog
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

# Initialize Presidio
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Custom Recognizer for Internal Customer IDs
internal_id_pattern = Pattern(name="internal_id_pattern", regex=r"CUST-\d{4,}", score=0.85)
internal_id_recognizer = PatternRecognizer(supported_entity="INTERNAL_ID", patterns=[internal_id_pattern])
analyzer.registry.add_recognizer(internal_id_recognizer)

def scrub_pii(text: str) -> str:
    """Scrubs PII and internal IDs from text before chunking or sending to LLMs."""
    if not text:
        return text
    results = analyzer.analyze(text=text, entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "INTERNAL_ID"], language="en")
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized_result.text

class HybridRAGService:
    def __init__(self, db: Session, llm_client=None):
        self.db = db
        self.llm = llm_client or MockLLMClient()

    def _fetch_customer_support_logs(
        self, merchant_id: int, user_id: str, limit: int = 20
    ) -> list[str]:
        """
        Standard ORM query for support events.
        """
        from models import Customer
        customer = self.db.query(Customer).filter(
            Customer.merchant_id == merchant_id,
            Customer.user_id == user_id
        ).first()
        
        if not customer:
            return []

        rows = self.db.query(EventLog).filter(
            EventLog.merchant_id == merchant_id,
            EventLog.customer_id == customer.id,
            EventLog.event_type == 'support_ticket'
        ).order_by(EventLog.timestamp.desc()).limit(limit).all()
        
        # We assume the 'payload' column contains a JSON string with ticket_text and resolution_status
        import json
        logs = []
        for row in rows:
            try:
                payload = json.loads(row.payload) if row.payload else {}
                ticket_text = payload.get("ticket_text", "Unknown ticket content")
                resolution = payload.get("resolution_status", "open")
                
                safe_ticket_text = scrub_pii(ticket_text)
                logs.append(f"[{row.timestamp}] ({resolution}) {safe_ticket_text}")
            except Exception:
                pass
        return logs

    def answer_operator_question(
        self, merchant_id: int, user_id: str, question: str
    ) -> str:
        """
        Grounded Q&A against the customer's actual support history.
        Context is materialised at runtime — never stored as embeddings.
        """
        if not self.llm:
            return "LLM integration not configured."
            
        logs = self._fetch_customer_support_logs(merchant_id, user_id)
        if not logs:
            context = "No support history on record."
        else:
            context = "\n".join(logs)

        context = "\n".join(logs)
        LIABILITY_GUARDRAIL = (
            "CRITICAL DIRECTIVE: You are strictly prohibited from offering, authorizing, or mentioning "
            "monetary discounts, refunds, or account credits under any circumstances. If a customer is "
            "at risk, offer white-glove technical support or a dedicated success manager call."
        )

        context = "\n".join(logs)
        system_prompt = (
            "You are a customer success analyst. Answer only using the "
            "support log extracts provided. Do not infer beyond the data. "
            "If the answer is not in the logs, say so explicitly.\n\n"
            f"{LIABILITY_GUARDRAIL}\n\n"
            f"SUPPORT LOGS FOR {user_id}:\n{context}"
        )
        response = self.llm.chat(system=system_prompt, user=question)
        return response.content

    def generate_churn_summary(
        self, merchant_id: int, user_id: str, telemetry: dict
    ) -> dict:
        """
        Two-sentence executive summary and next best action.
        Grounded in telemetry + support history for this specific customer.
        """
        if not self.llm:
            return {"summary": "LLM not configured.", "next_best_action": "Configure LLM provider."}
            
        logs = self._fetch_customer_support_logs(merchant_id, user_id, limit=5)
        context = "\n".join(logs) if logs else "No support history on record."

        prompt = (
            f"Customer telemetry: {telemetry}\n\n"
            f"Recent support history:\n{context}\n\n"
            "Write exactly two sentences explaining why this customer is at "
            "churn risk based on the data above, then recommend one specific "
            "next best action. Do not hallucinate data not present above."
        )
        response = self.llm.chat(
            system="You are an enterprise CRM AI. Be concise and data-grounded.",
            user=prompt,
        )
        lines = response.content.strip().split("\n")
        return {
            "summary":         lines[0] if len(lines) > 0 else "",
            "next_best_action": lines[1] if len(lines) > 1 else "",
        }

    def generate_winback_campaign(
        self, merchant_id: int, user_id: str, telemetry: dict,
        group: str = "A"
    ) -> dict:
        """
        Generates a SHAP-grounded win-back campaign email.

        Reads the top-3 SHAP feature drivers for this customer and injects them
        into the campaign prompt so the email directly addresses the exact reasons
        for the customer's churn risk — not generic marketing copy.

        Args:
            merchant_id: Tenant/merchant integer ID
            user_id:     Customer's string user_id
            telemetry:   Dict of current feature values (churn_score, etc.)
            group:       A/B experiment group ('A' = standard RAG, 'B' = VIP)

        Returns:
            dict: { subject, body, shap_context: [top-3 drivers] }
        """
        LIABILITY_GUARDRAIL = (
            "CRITICAL DIRECTIVE: You are strictly prohibited from offering, authorizing, "
            "or mentioning monetary discounts, refunds, or account credits under any "
            "circumstances. If a customer is at risk, offer white-glove technical support "
            "or a dedicated success manager call only."
        )

        # Fetch SHAP top-3 drivers for grounded context
        shap_context = []
        try:
            from services.explainability_service import get_top_shap_drivers
            shap_context = get_top_shap_drivers(merchant_id, user_id, top_n=3)
        except Exception:
            pass

        shap_narrative = ""
        if shap_context:
            driver_lines = [
                f"  - {d['feature'].replace('_', ' ').title()}: SHAP={d['shap_value']:+.3f} "
                f"({d['direction']} churn risk)"
                for d in shap_context
            ]
            shap_narrative = "Top risk drivers identified by the model:\n" + "\n".join(driver_lines)
        else:
            shap_narrative = "Risk driver analysis not yet available for this customer."

        # Fetch support logs for additional context
        logs = self._fetch_customer_support_logs(merchant_id, user_id, limit=3)
        support_context = "\n".join(logs) if logs else "No support history on record."

        if group == "B":
            template_instruction = (
                "Write a VIP win-back email offering this customer an exclusive 1-on-1 "
                "technical consultation with a Senior Customer Success Manager. "
                "Do not mention any discounts or credits."
            )
        else:
            template_instruction = (
                "Write a personalised win-back email addressing the specific risk reasons above. "
                "Offer to resolve the technical issues with dedicated engineering support. "
                "Do not mention any discounts or credits."
            )

        prompt = (
            f"Customer telemetry: {telemetry}\n\n"
            f"{shap_narrative}\n\n"
            f"Recent support history:\n{support_context}\n\n"
            f"{template_instruction}\n"
            "Format your response as:\n"
            "Subject: <email subject line>\n\n"
            "<email body>"
        )

        system_prompt = (
            "You are an enterprise Customer Success AI generating outreach emails. "
            "Be empathetic, specific, and data-grounded. Always reference the actual "
            "technical issues the customer experienced, not generic marketing language.\n\n"
            f"{LIABILITY_GUARDRAIL}"
        )

        response = self.llm.chat(system=system_prompt, user=prompt)
        content = response.content.strip()

        # Parse subject and body
        lines = content.split("\n", 2)
        subject = lines[0].replace("Subject:", "").strip() if lines else "We noticed you've had trouble"
        body = lines[2].strip() if len(lines) > 2 else content

        return {
            "subject": subject,
            "body": body,
            "shap_context": shap_context,
            "group": group,
        }

import logging
import json
from typing import List, Dict
from pydantic import BaseModel, Field

from config import settings
from google import genai

logger = logging.getLogger('retention_core.rag')

try:
    gemini_client = genai.Client(api_key=settings.gemini_api_key or 'DUMMY')
except Exception as e:
    logger.warning(f'Failed to init Gemini client: {e}')
    gemini_client = None

class Insight(BaseModel):
    theme: str = Field(description='The core theme or topic of the complaint.')
    percentage: str = Field(description='Estimated percentage of churned users mentioning this.')
    severity: str = Field(description='Severity of the issue: Low, Medium, High, or Critical.')
    description: str = Field(description='Detailed explanation of the insight.')

class RAGAnalysisResponse(BaseModel):
    insights: List[Insight]

def analyze_churn_logs() -> List[Dict]:
    mock_tickets = [
        'The new dashboard update is incredibly slow. I have to wait 10 seconds for it to load.',
        'I keep getting billed on the 1st of the month when I asked to be billed on the 15th.',
        'Dashboard is lagging again. Unusable.',
        'Customer service took 3 days to reply to my email about the billing date issue.',
        'Why is the site so slow since the v2.0 release? I am cancelling.',
        'I cannot figure out how to export my data. The UI is confusing.',
        'Slow loading times.',
        'Billing date is wrong again. I cannot manage my cash flow like this.'
    ]
    if not gemini_client or not settings.gemini_api_key:
        return [
            {'theme': 'Performance', 'percentage': '50%', 'severity': 'Critical', 'description': 'Users complain about dashboard lag since v2.0.'},
            {'theme': 'Billing', 'percentage': '37%', 'severity': 'High', 'description': 'Frustration that billing date preferences are ignored.'}
        ]
    
    scrubbed_tickets = [scrub_pii(t) for t in mock_tickets]
    retrieved_context = '\n'.join([f'- {t}' for t in scrubbed_tickets])
    sys_prompt = 'You are an advanced Customer Success AI. Analyze the following retrieved support tickets from recently churned users. Group the complaints into major themes, estimate the percentage of tickets representing that theme, and assign a severity level. Output the results as JSON.'
    user_prompt = f'Retrieved Support Tickets:\n{retrieved_context}'
    try:
        res = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[sys_prompt + '\n\n' + user_prompt],
            config=genai.types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=RAGAnalysisResponse,
                temperature=0.2
            )
        )
        data = json.loads(res.text)
        return data.get('insights', [])
    except Exception as e:
        logger.error(f'RAG Analysis failed: {e}')
        return []

def analyze_churn_logs_stream():
    mock_tickets = [
        'The new dashboard update is incredibly slow. I have to wait 10 seconds for it to load.',
        'I keep getting billed on the 1st of the month when I asked to be billed on the 15th.',
        'Dashboard is lagging again. Unusable.',
        'Customer service took 3 days to reply to my email about the billing date issue.',
        'Why is the site so slow since the v2.0 release? I am cancelling.',
        'I cannot figure out how to export my data. The UI is confusing.',
        'Slow loading times.',
        'Billing date is wrong again. I cannot manage my cash flow like this.'
    ]
    if not gemini_client or not settings.gemini_api_key:
        yield "LLM not configured. Mock Insights:\n\n"
        yield "**CRITICAL | Performance (50%)**\nUsers complain about dashboard lag since v2.0.\n\n"
        yield "**HIGH | Billing (37%)**\nFrustration that billing date preferences are ignored."
        return

    scrubbed_tickets = [scrub_pii(t) for t in mock_tickets]
    retrieved_context = '\n'.join([f'- {t}' for t in scrubbed_tickets])
    sys_prompt = 'You are an advanced Customer Success AI. Analyze the following retrieved support tickets from recently churned users. Group the complaints into major themes, estimate the percentage of tickets representing that theme, and assign a severity level. Output the results in beautifully formatted Markdown (use bullet points and bolding).'
    user_prompt = f'Retrieved Support Tickets:\n{retrieved_context}'
    try:
        res = gemini_client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=[sys_prompt + '\n\n' + user_prompt],
            config=genai.types.GenerateContentConfig(temperature=0.4)
        )
        for chunk in res:
            yield chunk.text
    except Exception as e:
        logger.error(f'RAG Streaming failed: {e}')
        yield f"Error streaming RAG insights: {e}"

