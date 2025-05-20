import os
import re
import streamlit as st
from dotenv import load_dotenv

from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.callbacks.streamlit import StreamlitCallbackHandler

# your tool imports
#from Tools_agent.compendium_tool import get_compendium_info
#from Tools_agent.faiss_tool import search_faiss
#from Tools_agent.openfda_tool import search_openfda
#from Tools_agent.tavily_tool import smart_tavily_answer
#from Tools_agent.alerts_tool import search_medication_alerts

load_dotenv()
st.set_page_config(page_title="KING – Streamed Multi-Tool Agent", layout="wide")
# --- SIDEBAR NAVIGATION ---
page = st.sidebar.selectbox("Seite wählen:", ["Apotheker Assistent", " Post-Sendungen"])
if page == "Apotheker Assistent":
    # --- API Key & Tool Toggles ---
    st.sidebar.markdown("---")
    openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    st.sidebar.markdown("**Tools aktivieren:**")
    use_compendium = st.sidebar.checkbox("Compendium.ch", value=True)
    use_internDB  = st.sidebar.checkbox("Local FAISS DB", value=True)
    use_openfda   = st.sidebar.checkbox("OpenFDA", value=True)
    use_web       = st.sidebar.checkbox("Web Search (Tavily)", value=True)
    use_alerts    = st.sidebar.checkbox("Medication Alerts", value=True)
    use_ema       = st.sidebar.checkbox("EMA", value=True)

    # --- MAIN HEADER ---
    st.title(" KING – Apotheker Assistent")
    st.write("Nutze eine Auswahl an Tools und gestreamte Antworten für schnelle, interaktive Q&A.")

    # --- CHOICE: Strukturierte Frage vs. Freie Frage ---
    mode = st.radio(
        "Fragemodus wählen:",
        ("Strukturierte Frage", "✏️ Freie Frage / offene Fragen")
    )

    if mode == "🔧 Strukturierte Frage":
        # structured: dropdowns + med name
        question_types = {
            "💊 Wirkung":        "Was ist die Wirkung von",
            "🩺 Nebenwirkungen": "Welche Nebenwirkungen hat",
            "⚠️ Warnungen":      "Welche Warnungen gibt es für",
            "💉 Anwendung":      "Wie wird",
            "📏 Dosierung":      "Wie lautet die empfohlene Dosierung von",
        }
        input_type_options = {
            "💊 Medikament": "Medikament",
            "🧪 Wirkstoff":   "Wirkstoff",
        }

        col1, col2 = st.columns(2)
        with col1:
            question_label = st.selectbox("Fragetyp", list(question_types.keys()))
        with col2:
            input_label = st.selectbox("Eingabetyp", list(input_type_options.keys()))

        med_name = st.text_input(
            "Name des Medikaments / Wirkstoffs",
            placeholder="z.B. Dafalgan"
        )
        prompt = (
            f"{question_types[question_label]} {med_name}? "
            f"({input_type_options[input_label]})"
        )

    else:
        # free-form question
        prompt = st.text_area(
            "Freie Frage an das LLM:",
            placeholder="Stelle hier deine beliebige Frage…",
            height=150
        )

    run = st.button("🚀 Anfrage starten")
    if run:
        # validation
        if not openai_api_key.startswith("sk-"):
            st.warning("Bitte gib deinen OpenAI API-Key ein (muss mit sk- beginnen).")
        elif not prompt or prompt.strip() == "":
            st.warning("Bitte formuliere eine Frage.")
        else:
            # show prompt back
            st.subheader("🧠 Deine Frage")
            st.info(prompt)

            # assemble tools (as before)…
            tools = []
        #if use_compendium:
        #    tools.append(Tool(
        #        name="CompendiumTool",
        #        func=get_compendium_info,
        #        description="Hole offizielle Medikamenteninfos von Compendium.ch"
        #    ))
        #if use_faiss:
        #    tools.append(Tool(
        #        name="FAISSRetrieverTool",
        #        func=search_faiss,
        #        description="Durchsuche lokale medizinische FAISS-Datenbank"
        #    ))
    # if use_openfda:
    #     tools.append(Tool(
    #         name="OpenFDATool",
    #         func=search_openfda,
    #         description="Hole Infos aus OpenFDA"
        #    ))
        #if use_web:
        #    tools.append(Tool(
        #        name="TavilySearchTool",
        #        func=smart_tavily_answer,
        #        description="Websuche für aktuelle Forschungsergebnisse"
        #   ))

            # Initialize LLM & Agent
            llm = ChatOpenAI(
                api_key=openai_api_key,
                model="gpt-4o",
                temperature=0.2,
                streaming=True,
            )
            agent = initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=False,
                handle_parsing_errors=True,
                agent_kwargs={
                    "system_message": (
                        "Du bist ein klinischer Assistent. "
                        "Antworte auf Deutsch, benutze nur relevante Infos."
                    ),
                    "return_intermediate_steps": True,
                    "max_iterations": 5,
                }
            )

            st.subheader("🔍 Agent läuft…")
            placeholder = st.empty()
            callback = StreamlitCallbackHandler(placeholder)

            try:
                result = agent.invoke(
                    {"input": prompt},
                    callbacks=[callback],
                    return_only_outputs=False
                )
                final = result["output"]
                steps = result.get("intermediate_steps", [])

                st.success("✅ Fertig!")
                st.subheader("📋 Endgültige Antwort")
                st.markdown(final)

                if steps:
                    st.subheader("🧰 Zwischenschritte")
                    for i, (thought, action) in enumerate(steps):
                        st.markdown(f"**Gedanke {i+1}:** {thought.log}")
                        st.markdown(f"- Tool: `{action.tool}`")
                        st.markdown(f"- Input: `{action.tool_input}`")

            except Exception as e:
                st.error(f"❌ Ein Fehler ist aufgetreten: {e}")

elif page == "Post-Sendungen":
    # --- POST-SENDUNGEN PAGE ---
    st.title("📦 Post-Sendungen für Kundennummer")
    st.write("Suche alle Post-Sendungen (Pakete) für eine gegebene Kundennummer im ERP.")

    # Input field for customer number
    kundennummer = st.text_input("Kundennummer eingeben", placeholder="z.B. 123456")
    search = st.button("🔍 Pakete suchen")

    if search:
        if not kundennummer:
            st.warning("Bitte gib eine Kundennummer ein.")
        else:
            st.info(f"Suche Post-Sendungen für Kundennummer **{kundennummer}**…")
            #try:
                # Example: connect via python-oracledb in thin mode
                #pw = getpass.getpass("Oracle Passwort eingeben: ")
                #conn = oracledb.connect(
                    #user="YOUR_ERP_USER",
                    #password=pw,
                    #dsn="erp.host:1521/servicename"
                #)
                #cur = conn.cursor()
                # Replace with your actual ERP table/query
                #cur.execute("""
                    #SELECT paket_id, versanddatum, status
                    #FROM post_sendungen
                    #WHERE kundennummer = :1
                    #ORDER BY versanddatum DESC
                #""", [kundennummer])
                #rows = cur.fetchall()
                #cur.close()
                #conn.close()

                #if not rows:
                #    st.warning("Keine Post-Sendungen gefunden.")
                #else:
                #    st.subheader("Gefundene Pakete:")
                #    for paket_id, versanddatum, status in rows:
                #        st.write(f"- **Paket {paket_id}** | Datum: {versanddatum} | Status: {status}")
            #except Exception as e:
            #    st.error(f"Fehler bei der ERP-Abfrage: {e}")