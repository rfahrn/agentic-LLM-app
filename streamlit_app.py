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

# --- SIDEBAR: API Key & Global Options ---
with st.sidebar:
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.markdown("---")
    st.markdown("**Select which tools to enable:**")
    use_compendium = st.checkbox("Compendium.ch", value=True)
    use_faiss      = st.checkbox("Local FAISS DB", value=True)
    use_openfda    = st.checkbox("OpenFDA", value=True)
    use_web        = st.checkbox("Web Search (Tavily)", value=True)
    use_alerts     = st.checkbox("Medication Alerts", value=True)

# --- MAIN HEADER ---
st.title("💊 KING – Medizinischer Assistent")
st.write("Nutze eine Auswahl an Tools und gestreamte Antworten für schnelle, interaktive Q&A.")

# --- QUESTION TYPE & INPUT TYPE DROPDOWNS ---
question_types = {
    "💊 Wirkung":             "Was ist die Wirkung von",
    "🩺 Nebenwirkungen":      "Welche Nebenwirkungen hat",
    "⚠️ Warnungen":           "Welche Warnungen gibt es für",
    "💉 Anwendung":           "Wie wird",
    "📏 Dosierung":           "Wie lautet die empfohlene Dosierung von",
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

med_name = st.text_input("Name des Medikaments / Wirkstoffs", placeholder="z.B. Dafalgan")

# --- RUN BUTTON ---
run = st.button("🚀 Anfrage starten")

# Validate
if run and not openai_api_key.startswith("sk-"):
    st.warning("Bitte gib deinen OpenAI API-Key ein (muss mit sk- beginnen).")
elif run and not med_name:
    st.warning("Bitte gib einen Medikamenten- oder Wirkstoffnamen ein.")
elif run:
    # Build prompt
    prompt = f"{question_types[question_label]} {med_name}? ({input_type_options[input_label]})"
    st.subheader("🧠 Deine Frage")
    st.info(prompt)

    # Assemble selected tools
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