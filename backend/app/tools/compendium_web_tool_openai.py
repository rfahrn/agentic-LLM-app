from agents import function_tool
from agents import Agent, WebSearchTool


#compendium_web_agent = Agent(name="CompendiumWebAgent",instructions=("Beantworte Fragen ausschließlich mit Informationen von https://compendium.ch/""Wenn du keine passenden Informationen findest, sage das bitte deutlich."),model="gpt-4o",tools=[WebSearchTool()],)
import re
import asyncio
from agents import Runner

from agents import Agent, WebSearchTool
import streamlit as st

    
openai_api_key = st.secrets.OPENAI.OPENAI_API_KEY
# set enviroment variable
OPEN_API_KEY = openai_api_key
import os
os.environ["OPENAI_API_KEY"] = openai_api_key
import os
import streamlit as st
from agents import Agent, WebSearchTool, AgentOutputSchemaBase
from agents.run_context import RunContextWrapper
from dataclasses import dataclass
from typing import Callable, Awaitable, Any, TypedDict, cast

# Ensure the API key is set for tracing
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI"]["OPENAI_API_KEY"]

# --- Step 1: Structured Output Type ---
class CompendiumResponse(TypedDict):
    answer: str
    sources: list[str]

class CompendiumOutputSchema(AgentOutputSchemaBase):
    def get_output_type(self) -> type:
        return CompendiumResponse

# --- Step 2: Dynamic Instruction Generator ---
async def compendium_instructions(
    context: RunContextWrapper[Any],
    agent: Agent[Any]
) -> str:
    # Optionally read something from context/contextual memory if needed
    return (
        "Du bist ein medizinischer Assistenzagent und beantwortest pharmazeutische Fachfragen "
        "**ausschließlich** auf Basis der Webseite https://compendium.ch/. "
        "**Keine anderen Domains oder externen Quellen sind erlaubt.**\n\n"

        "Dein Ziel ist es, Informationen **nur** von folgenden strukturierten Unterseiten zu extrahieren:\n"
        "- Produktseite: URLs mit `/product/.../product`\n"
        "- Fachinformation: URLs mit `/product/.../mpro`\n"
        "- Patienteninformation: URLs mit `/product/.../mpub`\n\n"

        "Du musst die Frage sehr sorgfältig analysieren und den relevanten Abschnitt auf diesen Seiten identifizieren. "
        "Relevante Abschnitte können beispielsweise sein:\n"
        "- 'Präklinische Daten'\n"
        "- 'Dosierung/Anwendung'\n"
        "- 'Kontraindikationen'\n"
        "- 'Warnhinweise und Vorsichtsmassnahmen'\n"
        "- 'Nebenwirkungen'\n"
        "- 'Zusammensetzung'\n\n"

        "Extrahiere die relevanten Textstellen **vollständig und wörtlich** – mit den zugehörigen Links. "
        "Beziehe dich dabei **so präzise wie möglich auf den Originaltext**, ohne jegliche Interpretation oder Paraphrasierung.\n\n"

        "Wenn du auf zusätzliche Informationen gestoßen bist, die **nicht** auf Compendium.ch liegen, "
        "darfst du dies erwähnen – aber **du musst klar sagen**, dass sie **nicht verwendet werden dürfen**.\n\n"
        
        "**Wenn sich Inhalte in Listen- oder Tabellenform besser darstellen lassen, dann verwende Markdown-Tabellen.**\n"

        "Am Ende jeder Antwort gib bitte **alle Compendium.ch-Links an**, die du verwendet hast. Beispielhafte Links:\n"
        "- https://compendium.ch/product/17776-dafalgan-tabl-500-mg/mpro\n"
        "- https://compendium.ch/product/17776-dafalgan-tabl-500-mg/product\n"
    )
from agents.model_settings import ModelSettings
model_settings = ModelSettings(
    temperature=0,
    top_p=0.7,
    frequency_penalty=0.5,
    presence_penalty=0.5
)

# --- Step 3: Final Agent Setup ---
compendium_web_agent = Agent(
    name="CompendiumWebAgent",
    model="gpt-4.1",
    instructions=compendium_instructions,  # now a callable
    tools=[WebSearchTool(search_context_size="high")],
    output_type=CompendiumOutputSchema()
)


import re

def extract_compendium_links(text: str) -> list[str]:
    """
    Extrahiert alle gültigen Compendium.ch-Links, die /mpro, /mpub oder /product enthalten.
    """
    pattern = r"https?://(?:www\.)?compendium\.ch/product/\d+-[\w-]+/(mpro|mpub|product)\b[^\s\)\]]*"
    return sorted(set(re.findall(pattern, text)))