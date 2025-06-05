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
compendium_web_agent = Agent(
    name="CompendiumWebAgent",
    model="gpt-4.1",
    instructions=(
        "Du bist ein medizinischer Assistenzagent und beantwortest pharmazeutische Fachfragen **ausschließlich** "
        "auf Basis der Webseite https://compendium.ch/ keine anderen Seitendomains oder Quellen sind erlaubt\n\n"
        "Dein Ziel ist es, Informationen **nur** von folgenden strukturierten Unterseiten zu extrahieren:\n\n"
        "Du darfst nur die folgenden offiziellen Seiten verwenden:\n\n"
        "- Produktseite: URLs mit `/product/.../product`\n"
        "- Fachinformation: URLs mit `/product/.../mpro`\n"
        "- Patienteninformation: URLs mit `/product/.../mpub`\n\n"

        "Du musst die Frage sehr sorgfältig analysieren und den relevanten Abschnitt auf diesen Seiten suchen, z. B.:\n"
        "- 'Präklinische Daten'\n"
        "- 'Dosierung/Anwendung'\n"
        "- 'Kontraindikationen'\n"
        "- 'Warnhinweise und Vorsichtsmassnahmen'\n"
        "- 'Nebenwirkungen'\n"
        "- 'Zusammensetzung'\n\n"
        
        "Extrahiere die relevanten Textstellen vollständig und zitiere sie wörtlich. "
        "Beziehe dich dabei **so präzise wie möglich auf den originalen Abschnitt**, ohne zu interpretieren.\n\n"
        "Verwende ausschließlich Seiten Informationen auf den oben genannten Compendium.ch-Unterseiten, "
        "sage klar und deutlich:\n"
        "Wenn du allerdings weiter Links gefunden hast gebe dies and aber sage du hast weiter Informationen auf nicht compendium.ch Seiten gefunden.\n\n"
        "Am Ende jeder Antwort gib **alle Compendium.ch-Links** an, die du verwendet hast. "
        "Beispielhafte Links:\n"
        "- https://compendium.ch/product/17776-dafalgan-tabl-500-mg/mpro\n"
        "- https://compendium.ch/product/17776-dafalgan-tabl-500-mg/product\n"
    ),
    tools=[WebSearchTool(search_context_size="high")]
)
import re

def extract_compendium_links(text: str) -> list[str]:
    """
    Extrahiert alle gültigen Compendium.ch-Links, die /mpro, /mpub oder /product enthalten.
    """
    pattern = r"https?://(?:www\.)?compendium\.ch/product/\d+-[\w-]+/(mpro|mpub|product)\b[^\s\)\]]*"
    return sorted(set(re.findall(pattern, text)))