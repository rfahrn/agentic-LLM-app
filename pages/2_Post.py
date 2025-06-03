import streamlit as st
from backend.app.tools.post_sendungen import fetch_sendungen

st.title("📦 Post-Sendungen")
kundennummer = st.text_input("Kundennummer eingeben", placeholder="z.B. 123456")
search = st.button("🔍 Pakete suchen")
if search:
    if not kundennummer:
        st.warning("Bitte gib eine Kundennummer ein.")
    else:
        st.info(f"Suche Pakete für Kundennummer **{kundennummer}**...")
        try:
            df = fetch_sendungen(kundennummer)
            if df.empty:
                st.warning("Keine Pakete in den letzten 30 Tagen gefunden.")
            else:
                st.write(df.to_markdown(index=False), unsafe_allow_html=True)
                st.dataframe(df.drop(columns=["po56paknr"]))
        except Exception as e:
            st.error(f"❌ Fehler: {e}")