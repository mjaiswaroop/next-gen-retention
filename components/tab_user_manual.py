"""
components/tab_user_manual.py
"""

import streamlit as st

def render():
    st.markdown("<style>h1, h2, h3, .centered-subheading { text-align: left !important; }</style>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 2rem; font-weight: 600; text-align: left; text-transform: uppercase; color: #EDEDED; padding-bottom: 8px;'>Platform User Guide</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#A1A1AA; text-align: left; margin-bottom: 20px;'>A step-by-step masterclass on operating the machine learning suite and understanding the AI terminology.</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Glossary Section
    st.markdown("### 📚 Glossary: Understanding the AI Jargon")
    with st.expander("Click here to reveal definitions for complex terms used in this platform", expanded=True):
        st.markdown("""
        *   **Ensemble Model:** A "super-model" created by combining multiple different AI algorithms (like XGBoost and LSTMs). By making them vote together, we get a much more accurate churn prediction than using one model alone.
        *   **Batch Inference:** The process of running the AI model across your *entire* customer database all at once to refresh everyone's churn probability scores.
        *   **SHAP (Shapley Additive exPlanations):** A Nobel-prize winning game-theory algorithm. It breaks down exactly *why* the AI made a prediction by showing you exactly how much weight it gave to specific traits (e.g., "This user is 20% more likely to churn specifically because they opened 3 support tickets").
        *   **RAG (Retrieval-Augmented Generation):** An AI technique where we feed thousands of your raw, messy support tickets to a Large Language Model (Gemini). It reads them all instantly to find hidden themes and summarize exactly what your customers are complaining about.
        *   **Causal Inference & ATE:** Standard AI predicts *if* someone will churn. Causal AI predicts if your intervention (like a discount) will actually *cause* them to stay. **ATE** (Average Treatment Effect) tells you the exact percentage boost in retention you'll get from spending that money.
        *   **Counterfactuals:** Simulating parallel universes. "What would have happened if we sent an email yesterday instead of doing nothing?"
        *   **A/B Testing:** Pitting two different retention strategies against each other in the real world (e.g., Email vs Push Notification) to mathematically prove which one saves more customers.
        """)

    st.markdown("---")
    
    st.markdown("### 1. Data Ingestion")
    st.markdown("""
    **Goal:** Feed the model with your raw telemetry and customer data.
    - Navigate to the **Data Ingestion** tab.
    - Ensure your data is in a clean CSV format. You only strictly need a `user_id` column.
    - Drag and drop your file. The platform's dynamic mapping engine will automatically detect any supplementary columns (e.g., `total_purchases`, `days_since_active`) and inject them into the training pipeline.
    """)
    
    st.markdown("---")

    st.markdown("### 2. Predictive Modeling (Predict Tab)")
    st.markdown("""
    **Goal:** Identify high-risk customers before they leave.
    - **Model Health:** At the top of the Predict tab, you'll see your accuracy scores. If these dip too low, it's time to click **Trigger Live Retrain** to rebuild the Ensemble Model on fresh data.
    - **Batch Inference:** Click the Batch Inference button to instantly run the active model across your entire customer database. This will update the "Churn Probability" score for every single user.
    - **High-Risk Table:** The data grid below shows your most critical users. You can sort by risk score or export the list for your retention team.
    """)
    
    st.markdown("---")

    st.markdown("### 3. Deep Dive Analysis (Explain & Forensics)")
    st.markdown("""
    **Goal:** Understand the *why* behind the algorithms.
    - **Explain Tab (SHAP):** Enter a specific `user_id` to generate a SHAP Waterfall chart. This visually proves exactly which factors are pushing a user toward churn, and which factors are keeping them loyal.
    - **Forensics Tab:** This is a post-mortem tool for users who have *already* churned. It uses the Gemini RAG engine to read through their past support tickets and uncovers hidden thematic reasons why they left (e.g., "Frustration with UI", "Pricing too high").
    """)
    
    st.markdown("---")

    st.markdown("### 4. Strategy Testing (Simulators)")
    st.markdown("""
    **Goal:** Test interventions safely before spending money.
    - **Causal Simulator:** What happens if you give a 20% discount to users with high usage drops? This simulator estimates the ATE (Average Treatment Effect) to prove if an intervention will actually work, or if it's just a waste of budget.
    - **Twin Simulator:** Select an individual user and run them through a Counterfactual Timeline. The AI will simulate parallel universes to find the exact sequence of actions that would have saved them.
    """)

    st.markdown("---")

    st.markdown("### 5. Deployment (Automations)")
    st.markdown("""
    **Goal:** Put your insights on autopilot.
    - **A/B Factory:** Use this to pit two different retention strategies against each other. Set up an experiment, and the platform will automatically route your high-risk users to the winning variant, ensuring you always use the most effective strategy.
    """)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.success("You are now fully equipped to prevent churn. Head over to Data Ingestion to begin!")
