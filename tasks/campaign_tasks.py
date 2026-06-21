from tasks.celery_app import celery_app
from services.rag_service import HybridRAGService
from database import SessionLocal
import json
import redis
from config import settings
import datetime

# Dummy LLM client for scaffolding
class DummyLLM:
    def chat(self, system, user):
        class Response:
            content = "Subject: We miss you!\nWe noticed you haven't been around lately."
        return Response()

def build_llm_client():
    return DummyLLM()

def get_redis():
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def generate_winback_email(self, merchant_id: int, user_id: str,
                           telemetry: dict, campaign_id: str):
    """
    Generates a hyper-personalised win-back email for one customer.
    Retries up to 3 times on LLM API failure with 30s backoff.
    Writes result to Redis keyed by campaign_id + user_id.
    """
    db = SessionLocal()
    redis_client = get_redis()
    try:
        service = HybridRAGService(db, llm_client=build_llm_client())
        logs = service._fetch_customer_support_logs(merchant_id, user_id)
        summary = service.generate_churn_summary(merchant_id, user_id, telemetry)

        email_prompt = (
            f"Write a personalised win-back email for a customer who "
            f"has shown the following churn signals: {summary.get('summary', '')}. "
            f"Recommended action: {summary.get('next_best_action', '')}. "
            f"Support history context:\n{chr(10).join(logs[:3])}\n\n"
            "The email must feel personal, not templated. "
            "Under 120 words. Subject line included."
        )
        llm = build_llm_client()
        response = llm.chat(system="You are a customer success writer.", user=email_prompt)

        result = {
            "user_id":    user_id,
            "status":     "complete",
            "subject":    response.content.split("\n")[0],
            "body":       "\n".join(response.content.split("\n")[1:]),
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }
        redis_client.hset(f"campaign:{campaign_id}", user_id, json.dumps(result))

    except Exception as exc:
        redis_client.hset(f"campaign:{campaign_id}", user_id, json.dumps({
            "user_id": user_id, "status": "failed", "error": str(exc)
        }))
        raise self.retry(exc=exc)
    finally:
        db.close()
