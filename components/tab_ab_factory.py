import streamlit as st
import requests
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Autonomous A/B Testing Factory")
    st.markdown("Let the AI generate 3 unique variants of your campaign, automatically run a micro-test on a small cohort, measure causal uplift, and deploy the winner.")
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    with st.form("ab_factory_form"):
        col1, col2 = st.columns([1, 2])
        with col1:
            target_audience = st.text_input("Target Audience", placeholder="e.g. Customers who haven't logged in for 30 days")
        with col2:
            base_prompt = st.text_area("Base Offer / Idea", height=100, placeholder="We are offering a free month upgrade if they come back.")
            
        submitted = st.form_submit_button("Generate Variants", type="primary", help="Uses an LLM agent to automatically spawn multiple variations of your base campaign (e.g., Aggressive, Empathetic, Value-Driven) tailored to this specific audience.")
        
    if submitted:
        if not target_audience or not base_prompt:
            st.error("Please provide both an audience and a base idea.")
            return
            
        with st.spinner("Gemini is generating distinct psychological variants..."):
            resp = requests.post(
                f"{API_BASE}/api/v1/ab_factory/generate",
                json={"base_prompt": base_prompt, "target_audience": target_audience},
                headers=headers
            )
            
            if resp.status_code == 200:
                variants = resp.json().get("variants", [])
                st.session_state["ab_variants"] = variants
            else:
                st.error("Failed to generate variants.")
                
    if "ab_variants" in st.session_state:
        st.divider()
        st.subheader("Generated Variants")
        variants = st.session_state["ab_variants"]
        
        cols = st.columns(len(variants))
        for i, (col, variant) in enumerate(zip(cols, variants)):
            with col:
                st.info(f"**Variant {i+1}: {variant['tone']}**")
                st.markdown(f"**Subject:** {variant['subject']}")
                st.text_area("Body", variant['body'], height=150, key=f"var_{i}", disabled=True)
                
        if st.button("🚀 Deploy Micro-Test & Auto-Scale Winner", type="secondary"):
            with st.spinner("Deploying to cohort and measuring real-time causal uplift..."):
                test_resp = requests.post(
                    f"{API_BASE}/api/v1/ab_factory/simulate_test",
                    json={"variants": variants},
                    headers=headers
                )
                
                if test_resp.status_code == 200:
                    results = test_resp.json()
                    st.success(f"Test Complete! Variant {results['winner_id']} is the winner.")
                    
                    for r in results['results']:
                        is_winner = r['variant_id'] == results['winner_id']
                        if is_winner:
                            st.success(f"**Variant {r['variant_id']} (Winner)** | Uplift: {r['measured_uplift']*100:.1f}%")
                        else:
                            st.warning(f"Variant {r['variant_id']} | Uplift: {r['measured_uplift']*100:.1f}%")
                            
                    st.info(f"The system has automatically routed 100% of remaining traffic to Variant {results['winner_id']}.")
                else:
                    st.error("Simulation failed.")
