"""
services/emotion_service.py
===========================
Module 3: Emotion-Aware Risk Scoring
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any

import pandas as pd
import numpy as np

from config import settings
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger("retention_core.emotion")

try:
    # PyTorch constraint inherited by Transformers
    import torch
    torch.set_num_threads(1)
    from transformers import pipeline

    logger.info(f"[emotion] Loading DistilRoBERTa emotion pipeline on device {settings.emotion_model_device}...")
    emotion_classifier = pipeline(
        "text-classification", 
        model="bhadresh-savani/distilroberta-base-emotion", 
        return_all_scores=False,
        device=settings.emotion_model_device
    )
except ImportError:
    logger.warning("[emotion] PyTorch or Transformers not installed. Using VADER fallback.")
    emotion_classifier = None
except Exception as e:
    logger.warning(f"[emotion] Failed to load remote model (using VADER fallback): {e}")
    emotion_classifier = None

vader_analyzer = SentimentIntensityAnalyzer()

# Risk score mapping based on user spec
EMOTION_RISK_MAP = {
    "anger": 1.0,
    "sadness": 0.8,
    "fear": 0.4,
    "surprise": 0.4,
    "neutral": 0.0,
    "joy": -0.4,
    "love": -0.5
}

def analyze_ticket_emotion(tenant_id: int, customer_id: str, ticket_id: str, ticket_text: str) -> Dict[str, Any]:
    if not ticket_text:
        return {"error": "Ticket text is empty"}

    if emotion_classifier:
        try:
            res = emotion_classifier(ticket_text[:512])[0]
            detected_emotion = res["label"]
            confidence = res["score"]
        except Exception as e:
            logger.error(f"[emotion] Inference failed: {e}")
            detected_emotion = "neutral"
            confidence = 1.0
    else:
        # VADER Fallback
        score = vader_analyzer.polarity_scores(ticket_text)["compound"]
        if score <= -0.5:
            detected_emotion = "anger"
            confidence = abs(score)
        elif score < -0.1:
            detected_emotion = "sadness"
            confidence = abs(score)
        elif score < 0.1:
            detected_emotion = "neutral"
            confidence = 1.0 - abs(score)
        elif score < 0.5:
            detected_emotion = "joy"
            confidence = score
        else:
            detected_emotion = "love"
            confidence = score

    emotion_risk_score = EMOTION_RISK_MAP.get(detected_emotion, 0.0)
    
    from database import get_analytics_connection
    conn = get_analytics_connection()
    
    alert_triggered = False
    rolling_signal = emotion_risk_score
    analysis_id = str(uuid.uuid4())
    
    try:
        hist_df = conn.execute("""
            SELECT analyzed_at, emotion_risk_score 
            FROM emotion_analysis 
            WHERE tenant_id = ? AND customer_id = ? 
            ORDER BY analyzed_at ASC
        """, [tenant_id, customer_id]).fetchdf()
        
        if not hist_df.empty:
            new_row = pd.DataFrame([{
                "analyzed_at": pd.Timestamp.now(tz='UTC'), 
                "emotion_risk_score": emotion_risk_score
            }])
            df = pd.concat([hist_df, new_row], ignore_index=True)
            
            df['analyzed_at'] = pd.to_datetime(df['analyzed_at'], utc=True)
            df.set_index('analyzed_at', inplace=True)
            
            ewma = df['emotion_risk_score'].ewm(halflife='7 days', times=df.index).mean()
            rolling_signal = ewma.iloc[-1]
            
            seven_days_ago = df.index[-1] - pd.Timedelta(days=7)
            past_ewma = ewma[ewma.index <= seven_days_ago]
            if not past_ewma.empty:
                old_signal = past_ewma.iloc[-1]
                if (rolling_signal - old_signal) > 0.3:
                    alert_triggered = True
                    logger.warning("[emotion] Rapid emotional deterioration detected for %s (delta=%.2f)", customer_id, (rolling_signal - old_signal))

        conn.execute("""
            INSERT INTO emotion_analysis 
            (analysis_id, customer_id, tenant_id, ticket_id, detected_emotion, 
             emotion_confidence, emotion_risk_score, rolling_emotion_signal, alert_triggered, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            analysis_id, customer_id, tenant_id, ticket_id, detected_emotion, 
            float(confidence), float(emotion_risk_score), float(rolling_signal), 
            alert_triggered, datetime.now(timezone.utc).isoformat()
        ])
        
    except Exception as e:
        logger.error("[emotion] DB operation failed: %s", e)
    finally:
        conn.close()

    return {
        "analysis_id": analysis_id,
        "emotion": detected_emotion,
        "confidence": float(confidence),
        "emotion_risk_score": float(emotion_risk_score),
        "rolling_signal": float(rolling_signal),
        "alert_triggered": alert_triggered
    }

def get_emotion_context(tenant_id: int, customer_id: str) -> str:
    from database import get_analytics_connection
    conn = get_analytics_connection()
    try:
        row = conn.execute("""
            SELECT detected_emotion, emotion_confidence
            FROM emotion_analysis
            WHERE tenant_id = ? AND customer_id = ?
            ORDER BY analyzed_at DESC LIMIT 1
        """, [tenant_id, customer_id]).fetchone()
        
        if row:
            return f"Customer's last ticket showed {row[0]} (confidence {row[1]:.2f}). The email must explicitly acknowledge this emotion."
    except Exception as e:
        logger.error("[emotion] Failed to fetch context: %s", e)
    finally:
        conn.close()
    return ""
