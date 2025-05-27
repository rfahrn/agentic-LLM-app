import os
from langchain.tools import Tool
from backend.app.tools.compendium_api_runner import run_compendium_cache_build

from tavily import TavilyClient
import os
import streamlit as st

api_key_tavily = os.getenv("TAVILY_API_KEY")
api_key_tavily = st.secrets.TAVILY.TAVILY_API_KEY
client = TavilyClient(api_key=api_key_tavily)

#BASE_PATH = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\Compendium_database"
from pathlib import Path
BASE_PATH = Path(__file__).resolve().parents[2] / "data" / "Compendium_database"
BASE_PATH.mkdir(parents=True, exist_ok=True)

def search_compendium_url(drug_name: str) -> str:
    """Use Tavily to find the real Compendium.ch product link."""
    query = f"site:compendium.ch {drug_name}"
    results = client.search(query=query, search_depth="basic", include_answer=False)
    urls = [r["url"] for r in results.get("results", [])]
    for url in urls:
        if "compendium.ch/product/" in url:
            return url
    return urls[0] if urls else "https://compendium.ch"


def extract_from_md_cache(drug_name: str, query: str) -> str:
    file_path = os.path.join(BASE_PATH, f"{drug_name.lower().replace(' ', '_')}.md")

    if not os.path.exists(file_path):
        try:
            markdown = run_compendium_cache_build(drug_name, str(BASE_PATH))
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown)
        except Exception as e:
            return f"❌ Fehler beim Nachladen aus Compendium API: {e}"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_section = None
    matching_blocks = []
    buffer = []

    for line in lines:
        if line.startswith("## "):
            if buffer and current_section and query.lower() in current_section.lower():
                matching_blocks.append((current_section, "".join(buffer).strip()))
            current_section = line.strip().lstrip("# ").strip()
            buffer = []
        elif current_section:
            buffer.append(line)

    if buffer and current_section and query.lower() in current_section.lower():
        matching_blocks.append((current_section, "".join(buffer).strip()))

    if not matching_blocks:
        return f"⚠️ Keine relevanten Abschnitte zu **{query}** gefunden für **{drug_name}**."

    out = []
    for title, content in matching_blocks:
        anchor = title.lower().replace(" ", "-").replace("/", "-")
        link = f"https://compendium.ch/product/{drug_name.replace(' ', '%20')}#{anchor}"
        out.append(f"### {title}\n\n{content}\n\n🔗 [Lokaler Link]({link})")

    external_url = search_compendium_url(drug_name)
    out.append(f"\n\n🔎 [Offizielle Seite auf Compendium.ch]({external_url})")

    return "\n\n---\n\n".join(out)

def compendium_tool_func(prompt: str) -> str:
    try:
        words = prompt.strip().split()
        if not words:
            return "⚠️ Leere Anfrage."
        drug_name = words[-1].strip(" ?.,;")
        query = " ".join(words[:-1])
        result = extract_from_md_cache(drug_name, query)
        if "Keine relevanten Abschnitte" in result:
            result += "\n\n⚠️ Hinweis: Daten wurden geladen, aber enthielten keine passenden Abschnitte."
        return result
    except Exception as e:
        return f"❌ Fehler beim Compendium-Zugriff: {str(e)}"



CompendiumTool = Tool(
    name="Compendium.ch",
    func=compendium_tool_func,
    description=(
        "Sucht medizinische Informationen zu einem Medikament aus der Compendium.ch API "
        "und speichert sie beim ersten Aufruf lokal. Beantwortet strukturierte pharmazeutische Fragen."
    ),
)
