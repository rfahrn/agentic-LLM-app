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
from backend.app.tools.compendium_langchain_tool  import CompendiumTool
from backend.app.tools.compendium_ch_search import CompendiumTavilyTool

# === Helper Tool Class with Priority ===
class PriorityTool:
    def __init__(self, tool: Tool, priority: int):
        self.tool = tool
        self.priority = priority

    def __getattr__(self, attr):
        return getattr(self.tool, attr)

def pinecone_wrapper(prompt: str) -> str:
    answer, sources, avg_score = search_medguides_with_rag(prompt)
    return f"{answer}\n\n\n---\n📈 *Durchschnittlicher Score: {avg_score}*"

# === STREAMLIT UI ===
load_dotenv()
st.set_page_config(page_title="KING – Streamed Multi-Tool Agent", layout="wide")
page = st.sidebar.selectbox("Seite wählen:", ["Apotheker Assistent", "Post-Sendungen"])
if page == "Apotheker Assistent":
    st.sidebar.markdown("---")
    openai_api_key = st.secrets.OPENAI.OPENAI_API_KEY
    st.sidebar.markdown("**Tools aktivieren:**")
    st.sidebar.caption(
        "Aktiviere externe Tools, welche der LLM Agent durchforsten soll – "
        "z. B. aus Compendium.ch, einer lokalen medizinischen Datenbank (pdf), EMA oder dem Web."
    )
    st.sidebar.markdown("### Tools")
    with st.sidebar.expander("Agenten-Tools aktivieren"):
        use_compendium = st.checkbox("Compendium", value=False)
        use_ema = st.checkbox("EMA", value=False)
        use_openfda = st.checkbox("OpenFDA", value=False)
        use_medguides = st.checkbox("Local PDFs Database", value=True)
        use_compendium_tavily = st.checkbox("Compendium (Tavily)", value=False)

        # The rest are not integrated yet
        st.checkbox("Open Web Search", value=False)
        st.checkbox("Medication Alerts", value=False)
        st.checkbox("MediQ", value=False)
        st.checkbox("PharmGKB", value=False)
        st.checkbox("Pedeus", value=False)
        st.checkbox("PubMed", value=False)

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
            "💊 Medikament": "Medikament",
            "🧪 Wirkstoff": "Wirkstoff",
        }

        col1, col2 = st.columns(2)
        with col1:
            question_label = st.selectbox("Fragetyp", list(question_types.keys()))
        with col2:
            input_label = st.selectbox("Eingabetyp", list(input_type_options.keys()))

        med_name = st.text_input("Name des Medikaments / Wirkstoffs", placeholder="z.B. Dafalgan")
        prompt = f"{question_types[question_label]} {med_name}? ({input_type_options[input_label]})"
        st.write(f"**Frage:** {prompt}")
    else:
        prompt = st.text_area("Freie Frage an das LLM:", placeholder="Stelle hier deine beliebige Frage…", height=150)

    run = st.button("🚀 Anfrage starten")
    st.sidebar.markdown("---")

    if run:
        if not openai_api_key.startswith("sk-"):
            st.warning("Bitte gib deinen OpenAI API-Key ein (muss mit sk- beginnen).")
        elif not prompt or prompt.strip() == "":
            st.warning("Bitte formuliere eine Frage.")
        else:
            llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4o-mini", temperature=0, streaming=True)

            tools = []
            if use_compendium_tavily and not any([use_medguides, use_compendium, use_ema, use_openfda]):
                from backend.app.tools.compendium_playwrite_scraper import scrape_compendium_pages
                from backend.app.tools.compendium_ch_search import get_product_url_only

                base_url = get_product_url_only(prompt)

                if not base_url:
                    st.warning("⚠️ Kein passender Compendium-Link gefunden.")
                else:
                    st.info(f"📦 Lade Informationen von: {base_url}")
                    result = scrape_compendium_pages(base_url)

                    if not result.strip():
                        st.warning("⚠️ Kein Inhalt extrahierbar.")
                    else:
                        st.success("✅ Informationen extrahiert.")
                        st.markdown(result, unsafe_allow_html=False)

                # ✅ Skip all other tools and the agent!
                st.stop()

            if use_compendium:
                tools.append(PriorityTool(CompendiumTool, priority=2))
            if use_ema:
                tools.append(PriorityTool(
                    Tool(name="EMA", func=lambda x: "📄 EMA-Tool: Noch nicht implementiert.", description="..."),
                    priority=2))
            if use_openfda:
                tools.append(PriorityTool(
                    Tool(name="OpenFDA", func=lambda x: "📄 OpenFDA-Tool: Noch nicht implementiert.", description="..."),
                    priority=3))
            if use_medguides:
                medguide_tool = Tool(
                    name="Medikamenten-PDF-RAG",
                    func=search_medguides_with_rag,
                    description="Durchsucht lokale Medikamenten-Guides via Pinecone und gibt GPT-Antworten zurück.",
                )
                tools.append(PriorityTool(medguide_tool, priority=10))

            sorted_tools = [pt.tool for pt in sorted(tools, key=lambda x: x.priority)]

            st.subheader("🔍 Agent läuft...")
            placeholder = st.empty()
            callback = StreamlitCallbackHandler(placeholder)

            if sorted_tools and use_medguides and len(sorted_tools) == 1:
                try:
                    answer, sources = search_medguides_with_rag(prompt)
                    st.success("✅ Antwort abgeschlossen.")
                    st.subheader("📋 Antwort")
                    with st.expander(" Vollständige Antwort", expanded=True):
                        st.markdown(answer, unsafe_allow_html=False)

                    with st.expander("📸 Wichtigste Seitenvorschauen", expanded=False):
                        cols = st.columns(3)
                        for i, s in enumerate(sources[:3]):
                            filename = s["filename"]
                            page = s["page"]
                            score = s["score"]
                            img_html = get_pdf_page_as_base64_image(filename, page)
                            with cols[i % 3]:
                                st.markdown(img_html, unsafe_allow_html=True)
                                st.caption(f"{filename} – Seite {page} (Score: {score})")
                except Exception as e:
                    st.error(f"❌ Fehler bei Pinecone-RAG: {e}")
            # ✅ Run Tavily directly if it's the only tool
            if use_compendium_tavily and not (use_medguides or use_compendium or use_ema or use_openfda):
                from backend.app.tools.compendium_ch_search import get_compendium_info
                result = get_compendium_info(prompt)

                if not result.strip():
                    st.warning("⚠️ Keine passende Information auf Compendium.ch gefunden.")
                else:
                    st.success("✅ Antwort von Compendium.ch (Tavily):")
                    st.markdown(result, unsafe_allow_html=True)
            else:
                agent = initialize_agent(
                    tools=sorted_tools,
                    llm=llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    handle_parsing_errors=True,
                    verbose=False,
                    agent_kwargs={
                        "system_message": (
                            "Du bist ein pharmazeutischer Assistent. "
                            "Nutze vertrauenswürdige Tools in dieser Reihenfolge: Compendium, EMA, OpenFDA. "
                            "Antworte ausschließlich auf Deutsch."),
                        "max_iterations": 5,
                        "return_intermediate_steps": True,
                    },
                )
                result = agent.invoke({"input": prompt}, callbacks=[callback], return_only_outputs=False)
                final = result["output"]
                steps = result.get("intermediate_steps", [])

                st.success("✅ Antwort abgeschlossen.")
                st.subheader("📋 Antwort")
                st.markdown(final, unsafe_allow_html=False)

                if steps:
                    st.subheader("🔎 Zwischenschritte")
                    for i, (thought, action) in enumerate(steps):
                        st.markdown(f"**Gedanke {i+1}:** {thought.log}")
                        st.markdown(f"- Tool: `{action.tool}`")
                        st.markdown(f"- Input: `{action.tool_input}`")


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
