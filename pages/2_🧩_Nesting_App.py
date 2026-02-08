import streamlit as st

# -------------------------------------------------
# Configuración de página
# -------------------------------------------------
st.set_page_config(
    page_title="Nesting App",
    layout="wide"
)

# -------------------------------------------------
# Header
# -------------------------------------------------
st.title("🧩 Nesting App")
st.caption("Herramienta de nesting y preparación de layouts para producción")

st.markdown("---")

# -------------------------------------------------
# Navegación
# -------------------------------------------------
col_back, col_spacer = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.markdown("---")

# =================================================
# 👇👇👇 AQUÍ EMPIEZA TU NESTING APP REAL 👇👇👇
# =================================================

# 🔴 IMPORTANTE:
# Pega aquí el contenido de tu antigua NestingAppV5
# (lo que antes tenías en app.py de nesting)
#
# Ejemplo:
#
# st.subheader("Configuración de nesting")
# uploaded_csv = st.file_uploader(...)
# ...
#
# No necesitas render(), main(), ni imports especiales.
# Streamlit ejecuta este archivo como una app completa.

st.info(
    "⚠️ Aquí debes pegar el código completo de tu NestingAppV5.\n\n"
    "Este archivo es ahora TU app de nesting."
)

# =================================================
# 👆👆👆 AQUÍ TERMINA TU NESTING APP REAL 👆👆👆
# =================================================
