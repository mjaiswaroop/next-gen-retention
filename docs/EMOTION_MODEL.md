# Emotion Model

Retention Core v3.0 introduces a local HuggingFace transformers pipeline to detect customer emotion from support tickets, eliminating external API dependencies.

## Model Details
- **Model**: `bhadresh-savani/distilroberta-base-emotion`
- **Classes**: sadness, joy, love, anger, fear, surprise
- **Device Support**: Set via `EMOTION_MODEL_DEVICE` in your `.env` file (-1 for CPU, 0 for GPU).

## Architecture & Fallback
The `services/emotion_service.py` automatically initializes the `pipeline` using the local device configuration.
If the transformers pipeline fails to load (e.g. out of memory, missing weights), the system seamlessly falls back to a **VADER lexicon-based sentiment analyzer** (`vaderSentiment`), mapping compound scores to our emotion classes.

## Risk Scoring
The extracted emotion is mapped to a continuous risk score ranging from -0.5 (Love/Praise) to +1.0 (Anger). This risk score is integrated into the EWMA rolling signal to trigger rapid deterioration alerts if the customer's sentiment suddenly turns hostile.
