# 🔮 E-Commerce Customer Churn Prediction & Personalization System

A production-grade, end-to-end ML pipeline for predicting customer churn, segmenting users into marketing personas, and exposing insights via a real-time dashboard.

## Architecture

```
raw event logs → data_pipeline.py → customer_features.csv
                                         ↓
                                    train_models.py
                                    ├── XGBoost Churn Classifier
                                    └── K-Means Segmentation
                                         ↓
                                    app.py (FastAPI)
                                         ↓
                                    dashboard.py (Streamlit)
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate data & train models
```bash
python data_pipeline.py
python train_models.py
```

### 3. Launch the API
```bash
uvicorn app:app --reload --port 8000
```

### 4. Launch the dashboard (in a separate terminal)
```bash
streamlit run dashboard.py
```

## Project Structure

| File | Description |
|---|---|
| `data_pipeline.py` | Synthetic data generation + RFM feature engineering |
| `train_models.py` | XGBoost churn model + K-Means segmentation training |
| `app.py` | FastAPI inference backend with `/predict` endpoint |
| `dashboard.py` | Streamlit executive dashboard |
| `data/` | Generated datasets (raw logs, features, scored) |
| `models/` | Serialised model artefacts |
| `plots/` | Training visualisations |

## Tech Stack

- **Data**: Pandas, NumPy
- **ML**: XGBoost, Scikit-Learn, K-Means
- **API**: FastAPI, Uvicorn, Pydantic
- **Dashboard**: Streamlit, Plotly

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/predict` | Predict churn + segment for arbitrary features |
| GET | `/users/{user_id}` | Look up a known user's full profile |
| GET | `/dashboard/summary` | Aggregate KPIs for dashboard |
