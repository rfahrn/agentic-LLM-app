import os
import re
import streamlit as st
from dotenv import load_dotenv
import nest_asyncio
import asyncio
nest_asyncio.apply()
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.callbacks.streamlit import StreamlitCallbackHandler
import os
os.system("playwright install")
from backend.app.tools.pinecone_tool import search_medguides_with_rag, get_pdf_page_as_base64_image
from backend.app.tools.post_sendungen import fetch_sendungen
from agents import Runner
#from backend.app.tools.compendium_langchain_tool  import CompendiumTool
#from backend.app.tools.compendium_ch_search import CompendiumTavilyTool
#use openai tool for compendium instead of langchain tool

# === compendium web agent ===
from backend.app.tools.compendium_web_tool_openai import compendium_web_agent, extract_compendium_links

async def run_compendium_query(prompt):
    result = await Runner.run(compendium_web_agent, input=prompt)
    output = result.final_output
    links = extract_compendium_links(output)
    return output, links



# === STREAMLIT UI ===
load_dotenv()
st.set_page_config(page_title="KING – Streamed Multi-Tool Agent", layout="wide")
page = st.sidebar.selectbox("Seite wählen:", ["Apotheker Assistent", "Post-Sendungen"])
if page == "Apotheker Assistent":
    st.sidebar.markdown("---")
    openai_api_key = st.secrets.OPENAI.OPENAI_API_KEY
    st.sidebar.markdown("**Agenten Tools aktivieren:**")
    st.sidebar.caption(
        "Welche Tools möchtest du für den LLM Agenten aktivieren? ")
    st.sidebar.markdown("### Tools", help="Aktiviere hier die Tools, die der LLM Agent nutzen soll. ")
    with st.sidebar.expander("Agenten-Tools aktivieren"):
        use_compendium = st.checkbox("Compendium via HCI Websearch", value=True, on_change=lambda: st.session_state.update({"use_compendium": use_compendium}), help="Nutze Compendium.ch für strukturierte Antworten.")
        use_ema = st.checkbox("EMA", value=False, on_change=lambda: st.session_state.update({"use_ema": use_ema}), help="Nutze die EMA-Datenbank für europäische Arzneimittelinformationen.")
        use_openfda = st.checkbox("OpenFDA API", value=False, on_change=lambda: st.session_state.update({"use_openfda": use_openfda}), help="Nutze die OpenFDA API für Arzneimittelinformationen.")
        st.markdown("---")
        
        st.markdown("**Für Kinder-Dosierung**")
        use_pedeus = st.checkbox("Pedeus", value=False, on_change=lambda: st.session_state.update({"use_pedeus": use_pedeus}), help="Nutze Pedeus für Fragen zu Dosierungen bei Kindern.")
        st.markdown("---")
        st.markdown("**Für Interaktionen**")
        use_mediq = st.checkbox("MediQ", value=False, on_change=lambda: st.session_state.update({"use_mediq": use_mediq}), help= "Nutze speizielle Interaktionsdatenbank für Schweizer Medikamente.")

        st.markdown("**Weitere Tools**")
        use_pinecone = st.checkbox("Pinecone RAG", value=False, help="Aktiviert die lokale Medikamenten-Datenbank.", on_change=lambda: st.session_state.update({"use_pinecone": use_pinecone}))
        use_medguides = st.checkbox("Local PDFs Database", value=False, help="Durchsucht lokale Medikamenten-Guides der OpenFDA - PDFs.", on_change=lambda: st.session_state.update({"use_medguides": use_medguides}))
        use_medalerts = st.checkbox("Medication Alerts", value=False, help="sucht lokale Medikamenten-Warnungen und -Alerts im ganzen Web.", on_change=lambda: st.session_state.update({"use_medalerts": use_medalerts}))
        
        use_pubmed = st.checkbox("PubMed", value=False, help="Durchsucht PubMed nach Studien und Artikeln zu Medikamenten und Wirkstoffen (englisch).", on_change=lambda: st.session_state.update({"use_pubmed": use_pubmed}))
        
    st.title(" KING – Apotheker Assistent")
    st.write("Nutze eine Auswahl an Agenten-Tools und gestreamte Antworten für schnelle, interaktive Q&A.")
    mode = st.radio("Fragemodus wählen:", ("Strukturierte Frage", "Freie Frage / offene Fragen"))

    prompt = ""
    if mode == "Strukturierte Frage":
        question_types = {
        # Effects & Side Effects
        "💊 Wirkung": "Was ist die Wirkung von",
        "🩺 Nebenwirkungen": "Welche Nebenwirkungen hat",
        "🧬 Typische Symptome": "Was sind typische Symptome der Nebenwirkung von",

        # Warnings & Risks
        "⚠️ Warnungen": "Welche Warnungen gibt es für",
        "⚠️ Kontraindikationen": "Welche Kontraindikationen bestehen für",
        "❗ Risiken & Beratung": "Welche Risiken bestehen bei der Einnahme von ... und welche Beratungstipps sind wichtig?",
        "🧠 Anticholinerg/Serotonerg/QT": "Hat das Medikament anticholinerge, serotonerge Wirkung oder QT-Zeit-Verlängerungspotential?",

        # Application & Use
        "💉 Anwendung": "Wie sollte man bei der Anwendung von ... beachten?",
        "🧃 Sondengängigkeit": "Ist das Medikament sondengängig?",
        "🧳 Reisehinweise": "Was ist bei Reisen mit diesem Medikament ins Ausland zu beachten?",
        "📘 Handhabungsfehler": "Was sind häufige Handhabungsfehler bei",

        # Composition
        "🌾 Gluten": "Enthält das Medikament Gluten?",
        "💎 Titandioxid": "Ist Titandioxid enthalten?",
        "🔪 Teilbarkeit": "Ist die Tablette teilbar?",

        # Dosage & Strength
        "📏 Dosierung": "Wie lautet die empfohlene Dosierung von",
        "🔢 Welche Stärken verfügbar": "Welche Stärken oder Präparate mit diesem Wirkstoff sind erhältlich?",
        "📐 Off-Label Dosierung": "Welche Dosierungen werden bei Off-Label-Indikationen verwendet?",

        # Interactions
        "🧪 Wechselwirkungen": "Welche Wechselwirkungen hat",
        "☕ IA mit Lebensmitteln": "Gibt es Wechselwirkungen mit Nahrung, Genuss- oder Nahrungsergänzungsmitteln?",
        "🧮 Relevanz IA": "Wie relevant ist eine bestimmte Interaktion und was sind Risikofaktoren?",
        "⚖️ 3er Interaktionen": "Gibt es eine klinisch relevante Dreifach-Wechselwirkung mit",

        # Alternatives & Availability
        "🔄 Alternative im Ausland": "Das Medikament fehlt in der Schweiz – gibt es Alternativen im Ausland?",
        "🅰️ Ähnliche Medi in SL": "Gibt es ein vergleichbares Medikament mit gleichem Wirkstoff in der Spezialitätenliste?",
        "⚙️ Alternative bei Interaktion": "Welche Alternativen gibt es, wenn XY nicht verordnet werden kann wegen Wechselwirkungen?",
        "⛔ Verfügbarkeit WS": "Wie ist die allgemeine Verfügbarkeit des Wirkstoffs aktuell?",

        # Special populations
        "👶 Schwangerschaft": "Ist die Einnahme von ... in der Schwangerschaft sicher?",
        "🍼 Stillzeit": "Ist die Einnahme von ... in der Stillzeit sicher?",
        "💧 NI/LI/HI": "Gibt es Einschränkungen bei Nieren-/Leber-/Herzinsuffizienz?",

        # Special use cases
        "🧪 Off-Label-Use": "Für welche Indikationen wird dieser Wirkstoff Off-Label eingesetzt?",
        "🏷️ Nahrungsergänzung / Homöopathie": "Wofür wird dieses Nahrungsergänzungsmittel oder homöopathische Arzneimittel eingesetzt?",

        # Regulatory
        "🛑 FORTA/PRISCUS": "Ist das Medikament auf der FORTA- oder PRISCUS-Liste?",

        # Translation & Comorbidity
        "🌍 Dosierungsübersetzung": "Wie lautet die äquivalente Dosierung in Frankreich/Italien/USA?",
        "🤝 Komorbidität": "Ist dieses Medikament geeignet bei bestimmten Komorbiditäten?",

        # Problem solving
        "❓ Arzneimittelbezogene Probleme": "Welche arzneimittelbezogenen Probleme können bei XY auftreten?",
        "🕵️‍♂️ Nebenwirkung-Ursache": "Welche Medikamente könnten die beobachtete Nebenwirkung verursachen?",

        # Explanations
        "📚 Erklärung & Beispiel": "Erkläre den Sachverhalt mit einem einfachen Beispiel oder einer Analogie.",
        "🔬 Unterschied A vs. B": "Was sind die Unterschiede zwischen Medikament A und B?",

        # Formulation / preparation
        "🧪 Magistralrezeptur": "Welche Magistralrezepturen gibt es mit diesem Wirkstoff? Welche Konzentrationen und Indikationen sind bekannt?",
        "💉 Nadel in Packung": "Welche Spritze oder Nadel liegt der Packung des Medikaments XY bei?",

        # General
        "📚 Studien": "Welche Studien gibt es zu",
        "📖 Zusammenfassung": "Gib eine kurze Zusammenfassung zu",
    }

        input_type_options = {
            "💊 Medikament": "**Medikament**",
            "🧪 Wirkstoff": "**Wirkstoff**",
        }

        col1, col2 = st.columns(2)
        with col1:
            question_label = st.selectbox("Fragetyp", list(question_types.keys()))
        with col2:
            input_label = st.selectbox("Eingabetyp", list(input_type_options.keys()))

    
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Altersgruppe**", )
        
            is_child = st.checkbox("Kind", key="child")
            is_teen = st.checkbox("Jugendlich", key="teen")
            is_adult = st.checkbox("Erwachsen", key="adult")
            is_senior = st.checkbox("Senior", key="senior")

        with col2:
            st.markdown("**Spezielle Faktoren**")
            is_pregnant = st.checkbox("Schwanger", key="pregnant")
            is_breastfeeding = st.checkbox("Stillend", key="breastfeeding")
            has_liver_issues = st.checkbox("Leberinsuffizienz", key="liver")
            has_kidney_issues = st.checkbox(" Niereninsuffizienz", key="kidney")

        # med_name = st.text_input("Name des Medikaments / Wirkstoffs", placeholder="z.B. Dafalgan")

        med_name = st.text_input(
            label="",
            placeholder="z. B. Dafalgan, Paracetamol", 
            label_visibility="collapsed"
        )
        st.markdown("<hr style='margin-top: -5px;'>", unsafe_allow_html=True)

        extra_context = []
        if is_child: extra_context.append("Kind")
        if is_teen: extra_context.append("Jugendlicher")
        if is_adult: extra_context.append("Erwachsener")
        if is_senior: extra_context.append("Senior")
        if is_pregnant: extra_context.append("schwangere Person")
        if is_breastfeeding: extra_context.append("stillende Person")
        if has_liver_issues: extra_context.append("Leberinsuffizienz")
        if has_kidney_issues: extra_context.append("Niereninsuffizienz")

        context_str = f" [**Patient:** {', '.join(extra_context)}]" if extra_context else ""
        #st.markdown('''#:red[Streamlit] :orange[can] :green[write] :blue[text] :violet[in]  #:gray[pretty] :rainbow[colors] and :blue-background[highlight] text.''')
        prompt = f"{question_types[question_label]} {med_name}? ({input_type_options[input_label]}){context_str}"
        st.markdown(f":blue-background[**Frage:** {prompt}]")
    else:
        prompt = st.text_area("Freie Frage an das LLM:", placeholder="Stelle hier deine beliebige Frage…", height=150)

    run = st.button("🚀 Anfrage starten")
    if run:
        if not use_compendium:
            st.warning("Bitte aktiviere Compendium.")
            st.stop()

        if not prompt.strip():
            st.warning("Bitte formuliere eine Frage.")
            st.stop()
   
        if mode == "Strukturierte Frage":
            if not med_name.strip():
                st.warning("Bitte gib ein Medikament oder einen Wirkstoff ein.")
                st.stop()

        st.subheader("🔍 Compendium-Agent läuft...")
        try:
            output_text, links = asyncio.run(run_compendium_query(prompt))
            st.success("✅ Antwort abgeschlossen.")
            st.subheader("📋 Antwort")
            st.markdown(output_text, unsafe_allow_html=True)

            if links:
                st.markdown("### 🔗 Quellen:")
                for url in links:
                    st.markdown(f"- [compendium.ch]({url})")
            else:
                st.markdown("⚠️ *Keine direkten Links von [compendium.ch](https://compendium.ch) gefunden.*")
        except Exception as e:
            st.error(f"❌ Fehler bei der Compendium-Abfrage: {e}")

        # Placeholder for future tools
        else:
            st.info("Andere Tools (EMA, OpenFDA etc.) werden bald unterstützt.")



elif page == "Post-Sendungen":
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
