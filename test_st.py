import streamlit as st
import contextvars
from database import active_tenant_id, SessionLocal
from models import ShapValue

if __name__ == "__main__":
    active_tenant_id.set(1)
    st.write('Set tenant ID to 1')

    db = SessionLocal()
    try:
        results = db.query(ShapValue).filter(ShapValue.tenant_id == 1).all()
        st.write('SUCCESS')
    except Exception as e:
        st.write('ERROR: ' + str(e))
