import sys
import pandas as pd
from unittest.mock import MagicMock
import streamlit as st

# Mock streamlit
st.markdown = MagicMock()
def mock_columns(spec, **kwargs):
    if isinstance(spec, int):
        return [MagicMock() for _ in range(spec)]
    return [MagicMock() for _ in range(len(spec))]
st.columns = MagicMock(side_effect=mock_columns)
st.metric = MagicMock()
st.plotly_chart = MagicMock()
st.success = MagicMock()
st.warning = MagicMock()
st.error = MagicMock()

import dashboard
from components import tab_overview, tab_analytics, tab_forensics, tab_customer360

def test():
    merchant = list(dashboard.API_KEYS.keys())[0]
    token = dashboard.get_token(dashboard.API_KEYS[merchant])
    
    users = dashboard.fetch_users(token)
    summary = dashboard.fetch_summary(token)
    df = pd.DataFrame(users)
    
    print("Testing tab_overview...")
    try:
        tab_overview.render(df, summary, merchant)
    except Exception as e:
        print(f"Error in tab_overview: {e}")
        import traceback
        traceback.print_exc()

    print("Testing tab_analytics...")
    try:
        tab_analytics.render(df)
    except Exception as e:
        print(f"Error in tab_analytics: {e}")
        import traceback
        traceback.print_exc()

    print("Testing tab_forensics...")
    try:
        tab_forensics.render(df, merchant, 75)
    except Exception as e:
        print(f"Error in tab_forensics: {e}")
        import traceback
        traceback.print_exc()

    print("Testing tab_customer360...")
    try:
        # We need to mock selectbox to return a valid uid
        st.selectbox = MagicMock(return_value=df["user_id"].iloc[0])
        st.slider = MagicMock(side_effect=[0, 0, 0.0, 0, 0.0, 0]) # Mock sliders
        tab_customer360.render(df, token)
    except Exception as e:
        print(f"Error in tab_customer360: {e}")
        import traceback
        traceback.print_exc()
        
    print("Test complete.")

if __name__ == '__main__':
    test()
