import streamlit as st
import requests
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def render(tenant_id: int):
    st.header("Autonomous Auto-Heal (Forensics)")
    st.markdown("This agent constantly monitors the backend stack traces (`uvicorn_error.log`). If a crash is detected, it proposes a self-healing code patch that you can apply with one click.")
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    if st.button("Scan for New Errors", help="Reads the server's uvicorn error logs to find unhandled exceptions and HTTP 500 crashes that just occurred in production."):
        st.rerun()
        
    st.divider()
    
    try:
        resp = requests.get(f"{API_BASE}/api/v1/autoheal/errors", headers=headers)
        if resp.status_code == 200:
            errors = resp.json().get("errors", [])
            
            if not errors:
                st.success("No recent backend errors detected. System is perfectly healthy!")
                return
                
            for err in errors:
                with st.expander(f"Error {err['id']}: {err['exception']} in {err['target_file'] or 'Unknown'}"):
                    st.code(err['traceback'], language="python")
                    
                    if not err['target_file']:
                        st.warning("Could not determine local target file to patch from this stack trace.")
                        continue
                        
                    # Generate Patch Button
                    patch_key = f"patch_{err['id']}"
                    if patch_key not in st.session_state:
                        if st.button("Generate AI Patch", key=f"gen_{err['id']}"):
                            with st.spinner("Analyzing traceback and source code..."):
                                patch_resp = requests.post(
                                    f"{API_BASE}/api/v1/autoheal/generate_patch", 
                                    json={"target_file": err['target_file'], "traceback": err['traceback']},
                                    headers=headers
                                )
                                if patch_resp.status_code == 200:
                                    st.session_state[patch_key] = patch_resp.json()
                                    st.rerun()
                                else:
                                    st.error(f"Failed to generate patch: {patch_resp.text}")
                    
                    if patch_key in st.session_state:
                        patch_data = st.session_state[patch_key]
                        st.subheader("AI Proposed Fix")
                        st.info(f"**Reasoning:** {patch_data['reasoning']}")
                        
                        st.markdown("**New File Contents:**")
                        st.code(patch_data['fixed_code'], language="python")
                        
                        if st.button("Apply Patch & Hot Reload", type="primary", key=f"apply_{err['id']}"):
                            apply_resp = requests.post(
                                f"{API_BASE}/api/v1/autoheal/apply_patch",
                                json={"target_file": patch_data['target_file'], "fixed_code": patch_data['fixed_code']},
                                headers=headers
                            )
                            if apply_resp.status_code == 200:
                                st.success("Patch applied successfully! The backend will automatically reload.")
                                del st.session_state[patch_key]
                            else:
                                st.error(f"Failed to apply patch: {apply_resp.text}")
                                
    except Exception as e:
        st.error(f"Failed to connect to Auto-Heal service: {e}")
