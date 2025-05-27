import os
import re
import streamlit as st
from dotenv import load_dotenv

from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.callbacks.streamlit import StreamlitCallbackHandler

from backend.app.tools.pinecone_tool import search_medguides_with_rag, get_pdf_page_as_base64_image
from backend.app.tools.post_sendungen import fetch_sendungen

def pinecone_wrapper(prompt: str) -> str:
    answer, sources, avg_score = search_medguides_with_rag(prompt)
    return f"{answer}\n\n\n---\n📈 *Durchschnittlicher Score: {avg_score}*"

load_dotenv()
st.set_page_config(page_title="KING – Streamed Multi-Tool Agent", layout="wide")
page = st.sidebar.selectbox("Seite wählen:", ["Apotheker Assistent", "Post-Sendungen"])

if page == "Apotheker Assistent":
    # --- API Key & Tool Toggles ---
    st.sidebar.markdown("---")
    #openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    openai_api_key = st.secrets.OPENAI.OPENAI_API_KEY
    st.sidebar.markdown("**Tools aktivieren:**")
    st.sidebar.caption(
        "Aktiviere externe Tools, welche der LLM Agent durchforsten soll – "
        "z. B. aus Compendium.ch, einer lokalen medizinischen Datenbank (pdf), EMAoder dem Web.\n\n"
    )
    st.sidebar.markdown("###  Tools")
    with st.sidebar.expander("Agenten-Tools aktivieren"):
        st.checkbox("Compendium", value=False)
        st.checkbox("EMA", value=False)
        st.checkbox("OpenFDA", value=False)
        use_medguides = st.checkbox("Local PDFs Database", value=True)
        st.checkbox("Open Web Search", value=False)
        st.checkbox("Medication Alerts", value=False)
        st.checkbox("MediQ", value=False)
        st.checkbox("PharmGKB", value=False)
        st.checkbox("Pedeus", value=False)
        st.checkbox("PubMed", value=False)
        
    #use_compendium = st.sidebar.checkbox("Compendium.ch", value=False)
    #use_internDB  = st.sidebar.checkbox("Local FAISS DB", value=False)
    #use_openfda   = st.sidebar.checkbox("OpenFDA", value=False)
    #use_web       = st.sidebar.checkbox("Web Search (Tavily)", value=True)
    #use_alerts    = st.sidebar.checkbox("Medication Alerts", value=False)
    #use_ema       = st.sidebar.checkbox("EMA", value=False)

    # --- MAIN HEADER ---
    st.title(" KING – Apotheker Assistent")
    st.write("Nutze eine Auswahl an Agenten-Tools und gestreamte Antworten für schnelle, interaktive Q&A.")
    mode = st.radio(
        "Fragemodus wählen:",
        ("Strukturierte Frage", "Freie Frage / offene Fragen")
    )

    # build `prompt` based on selection
    prompt = ""
    if mode == "Strukturierte Frage":
        question_types = {
            "💊 Wirkung":        "Was ist die Wirkung von",
            "🩺 Nebenwirkungen": "Welche Nebenwirkungen hat",
            "⚠️ Warnungen":      "Welche Warnungen gibt es für",
            "💉 Anwendung":      "Wie sollte man bei der Anwendung von ... beachten; ",
            "📏 Dosierung":      "Wie lautet die empfohlene standard Dosierung von",
            "🧪 Wechselwirkungen": "Welche Wechselwirkungen hat",
            "📦 Lagerung":       "Wie ist die Lagerung von" ,
            "🧪 Wirkstoff":      "Was ist der Wirkstoff von",
            "💊 Interaktionen":  "Welche Interaktionen hat", 
            "📦 Haltbarkeit":  "Was weiss man bezüglich der Haltbarkeit von",

            
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
        prompt = f"{question_types[question_label]} {med_name}? ({input_type_options[input_label]})"
        st.write(f"**Frage:** {prompt}")
        
    else:  # Freie Frage
        prompt = st.text_area(
            "Freie Frage an das LLM:",
            placeholder="Stelle hier deine beliebige Frage…",
            height=150
        )

    run = st.button("🚀 Anfrage starten")
    st.sidebar.markdown("---")
    if run:
        # validation
        if not openai_api_key.startswith("sk-"):
            st.warning("Bitte gib deinen OpenAI API-Key ein (muss mit sk- beginnen).")
        elif not prompt or prompt.strip() == "":
            st.warning("Bitte formuliere eine Frage.")
        else:
            # show prompt back
            st.subheader("Frage")
            st.info(prompt, icon="💬")
            llm = ChatOpenAI(
                api_key=openai_api_key,
                model="gpt-4o-mini",
                temperature=0,
                streaming=True, )
            # Collect activated tools
            tools = []
            if use_medguides:
                tools.append(Tool(
                    name="Medikamenten-PDF-RAG",
                    func=search_medguides_with_rag,
                    description="Durchsucht lokale Medikamenten-Guides via Pinecone und gibt GPT-Antworten zurück.",
                ))
            st.subheader("🔍 Agent läuft...")
            placeholder = st.empty()
            callback = StreamlitCallbackHandler(placeholder)

            if tools:
                if use_medguides and len(tools) == 1:
                    try:
                        answer, sources = search_medguides_with_rag(prompt)
                        st.success("✅ Antwort abgeschlossen.")
                        #with st.expander("📋 Antwort anzeigen", expanded=True):
                            #st.markdown(answer, unsafe_allow_html=True)
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
                else:
                    agent = initialize_agent(
                        tools=tools,
                        llm=llm,
                        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                        handle_parsing_errors=True,
                        verbose=False,
                        agent_kwargs={
                            "system_message": (
                                "Du bist ein pharmazeutischer Assistent. "
                                "Beantworte Fragen nur auf Basis vertrauenswürdiger Quellen wie PDFs oder Datenbanken. "
                                "Antworte ausschließlich auf Deutsch."
                            ),
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
                            if "pinecone" in action.tool.lower():  # or better filtering logic
                                st.markdown(f"**Gedanke {i+1}:** {thought.log}")
                                st.markdown(f"- Tool: `{action.tool}`")
                                st.markdown(f"- Input: `{action.tool_input}`")

                

            # --- Future Tool-based Setup (commented for now) ---
            # tools = []
            # if use_compendium:
            #     tools.append(Tool(
            #         name="CompendiumTool",
            #         func=get_compendium_info,
            #         description="Hole offizielle Medikamenteninfos von Compendium.ch"
            #     ))
            # if use_internDB:
            #     tools.append(Tool(
            #         name="FAISSRetrieverTool",
            #         func=search_faiss,
            #         description="Durchsuche lokale medizinische FAISS-Datenbank"
            #     ))
            # if use_openfda:
            #     tools.append(Tool(
            #         name="OpenFDATool",
            #         func=search_openfda,
            #         description="Hole Infos aus OpenFDA"
            #     ))
            # if use_web:
            #     tools.append(Tool(
            #         name="TavilySearchTool",
            #         func=smart_tavily_answer,
            #         description="Websuche für aktuelle Forschungsergebnisse"
            #     ))

            # agent = initialize_agent(
            #     tools=tools,
            #     llm=llm,
            #     agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            #     verbose=False,
            #     handle_parsing_errors=True,
            #     agent_kwargs={
            #         "system_message": (
            #             "Du bist ein klinischer Assistent. "
            #             "Antworte auf Deutsch, benutze nur relevante Infos."
            #         ),
            #         "return_intermediate_steps": True,
            #         "max_iterations": 5,
            #     }
            # )

            # result = agent.invoke(
            #     {"input": prompt},
            #     callbacks=[callback],
            #     return_only_outputs=False
            # )
            # final = result["output"]
            # steps = result.get("intermediate_steps", [])
            # st.success("✅ Fertig!")
            # st.subheader("📋 Endgültige Antwort")
            # st.markdown(final)
            # if steps:
            #     st.subheader("🧰 Zwischenschritte")
            #     for i, (thought, action) in enumerate(steps):
            #         st.markdown(f"**Gedanke {i+1}:** {thought.log}")
            #         st.markdown(f"- Tool: `{action.tool}`")
            #         st.markdown(f"- Input: `{action.tool_input}`")


elif page == "Post-Sendungen":
    st.title("📦 Post-Sendungen")
    st.write("Suche Post-Sendungen (Pakete) für eine gegebene Kundennummer im ERP.")
    kundennummer = st.text_input("Kundennummer eingeben", placeholder="z.B. 123456")
    search = st.button("🔍 Pakete suchen")
    if search:
        if not kundennummer:
            st.warning("Bitte gib eine Kundennummer ein.")
        else:
            st.info(f"Suche Post-Sendungen für Kundennummer **{kundennummer}**…")
            try:
                df = fetch_sendungen(kundennummer)
                if df.empty:
                    st.warning("Keine Pakete in den letzten 30 Tagen gefunden.")
                else:
                    st.subheader("📦 Gefundene Pakete")
                    st.write(df.to_markdown(index=False), unsafe_allow_html=True)
                    st.dataframe(df.drop(columns=["po56paknr"]))  

            except Exception as e:
                st.error(f"❌ Fehler: {e}")

