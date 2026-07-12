# ⚓ Anchor: Next-Gen Customer Retention & Causal AI Platform

Anchor is a production-grade, end-to-end multi-tenant customer retention engine. Built for subscription services, modern B2B SaaS, and high-growth e-commerce platforms, Anchor goes beyond traditional predictive analytics by combining classic Machine Learning, Causal AI, Social Graph Contagion, NLP, and Automated Winback Campaign engines into a single unified workspace.

The entire interface has been styled under a premium **Nordic Editorial** design system—delivering a clean, executive, and highly professional analytics experience inspired by world-class financial publications.

---

## 🏛️ System Architecture & Pillars

Anchor is structured across five core capabilities to provide a complete closed-loop retention solution:

```
                      [ Smart Data Ingestion ] (CSV Uploader / DB Connectors)
                                 │
                                 ▼
                     [ Multi-Tenant Database ] (Row-Level Security / SQLite)
                                 │
         ┌───────────────────────┼────────────────────────┬───────────────────────┐
         ▼                       ▼                        ▼                       ▼
   [ Predictive ML ]       [ Causal AI ]         [ Social Contagion ]    [ Emotion Timeline ]
 (XGBoost Churn & K-Means) (Uplift Intervention)  (Network Centrality)      (NLP Ticket Analysis)
         │                       │                        │                       │
         └───────────────────────┴────────────────────────┼───────────────────────┘
                                                          ▼
                                            [ Automated Winback Engine ]
                                          (SendGrid Outreach / CRM Sync)
```

### 1. Smart Data Ingestion (Fuzzy Schema Alignment)
Sellers can upload event logs or customer sheets in any format. Anchor's data pipeline uses fuzzy synonym mapping to auto-detect core fields (like `customer_id`, `recency`, `monetary_value`, `active_support_tickets`) and matches columns via an interactive dropdown UI, eliminating onboarding friction.

### 2. Multi-Tenant Architecture & RLS
Secure data isolation is built directly into the database engine. Anchor enforces global **Row-Level Security (RLS)** via SQLAlchemy event listeners. Context-scoped tenant IDs ensure that merchants can only query their own data, keeping customer profiles and telemetry isolated in shared database schemas.

### 3. Causal Impact & Uplift Modeling (EconML & DoWhy)
Traditional models predict *who* will leave; Anchor predicts *who can be saved*. By implementing Causal AI models (Uplift modeling), the platform estimates the direct individual uplift of an intervention (like a discount). This allows sellers to avoid wasted budget and target only persuadable customers.

### 4. Contagion Graph Analysis (Domino Churn Modeling)
Customers do not exist in isolation. Anchor maps referral networks and social connections, running network centrality algorithms (PageRank, Degree Centrality) to highlight high-influence users whose departure would trigger a cascade of secondary churn events.

### 5. Emotion Timeline & Ticket Sentiment Trajectory (NLP)
By analyzing customer support interactions using pre-trained NLP models, Anchor tracks the emotional pulse of your customers over time. If a user's ticket sentiment shows rapid emotional deterioration, the system triggers high-alert indicators for the Customer Success team.

### 6. Automated Campaigns & CRM Sync
When a customer is flagged as high-risk, the platform generates a custom win-back email tailored to their specific pain points (e.g., apologizing for check-out errors or session crashes). Insights sync back to CRMs like Salesforce and HubSpot, and campaigns can be sent directly via SendGrid.

---

## ⚡ Tech Stack

- **Frontend & UI**: Streamlit, Styled under the **Nordic Editorial Theme** (Custom CSS, Playfair Display serif headings, Inter typography, warm spruce charcoal backgrounds, alabaster cream accents).
- **Core ML & Causal AI**: XGBoost Classifier, Scikit-Learn (K-Means Clustering), EconML, DoWhy.
- **NLP & Sentiment**: vaderSentiment, HuggingFace Transformers.
- **Backend API**: FastAPI, Uvicorn, Pydantic.
- **Database & Security**: SQLAlchemy, SQLite (with custom ORM event listeners for tenant-level RLS).
- **Task Orchestration**: Celery (Beat & Worker execution), Redis.
- **Unit Testing**: Pytest.

---

## 🚀 Quick Start

### 1. Installation
Ensure Redis is running locally on port `6379`. Then, install the Python package dependencies:
```bash
pip install -r requirements.txt
```

### 2. Seeding & Database Setup
Initialize the database schemas, seed administrative users, and run the multi-tenant data simulator:
```bash
python seed_admin.py
python scripts/data_simulator.py
```

### 3. Launching Services
Run the FastAPI backend server:
```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Start the Celery worker and beat scheduler (in a separate terminal):
```bash
python -m celery -A tasks.celery_app worker --loglevel=info --pool=solo
python -m celery -A tasks.celery_app beat --loglevel=info
```

Launch the Streamlit executive dashboard (in a separate terminal):
```bash
python -m streamlit run dashboard.py --server.port 8501
```

---

## 🧪 Testing

The repository contains a fully automated test suite verifying auth flows, API endpoints, RLS rules, graph models, and ML life cycles. Run the tests using pytest:
```bash
python -m pytest
```
