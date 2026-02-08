import streamlit as st

def render():
    st.header("🧩 Nesting App")

    if st.button("⬅️ Volver al Hub"):
        st.query_params["page"] = "home"
        st.rerun()

    st.markdown("---")

    # Aquí pegas (o llamas) a la lógica de tu nesting app
    # Por ejemplo:
    # from .nesting_core import run_ui
    # run_ui()

    st.info("Aquí va la UI de NestingAppV5 (pegar tu implementación actual en esta función).")

