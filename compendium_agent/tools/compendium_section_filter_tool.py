import json
from pathlib import Path
from typing import List

from langchain_core.tools import Tool
from pydantic import BaseModel, Field  
from rapidfuzz import fuzz
from model import llm  
# Adjust to your actual JSON folder
COMPENDIUM_DB_DIR = Path(r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\Compendium_database")

class CompendiumSectionFilterInput(BaseModel):
    query: str = Field(..., description="Search string like 'Co-Dafalgan pregnancy' or 'aspirin Stillzeit'")
# 🧠 Tool input schema
class CompendiumSectionFilterInput(BaseModel):
    query: str = Field(..., description="Search string like 'Co-Dafalgan pregnancy' or 'aspirin Stillzeit'")

# 🔍 Helper: Decide if content is contextually relevant
def is_contextually_relevant(query: str, title: str, content: str) -> bool:
    query_words = query.lower().split()
    title_lower = title.lower()
    content_lower = content.lower()
    return any(word in title_lower or word in content_lower for word in query_words)

# 📝 Helper: Summarize with LLM (used only if content is long/relevant)
def summarize_with_llm(text: str) -> str:
    prompt = f"Fasse den folgenden medizinischen Abschnitt für Laien zusammen, so dass er kurz und verständlich ist:\n\n{text}"
    try:
        result = llm.invoke(prompt)
        return result.content.strip()
    except Exception as e:
        return f"(⚠️ Zusammenfassung fehlgeschlagen: {e})"

# 🛠️ Main tool function
def compendium_section_filter_func(query: str) -> str:
    query_lower = query.strip().lower()
    if not query_lower:
        return "❌ Leere Anfrage."

    matches = []
    MAX_MATCHES = 5  # Limit to avoid token overload

    for file_path in COMPENDIUM_DB_DIR.glob("*.json"):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        for product_name, product_data in data.items():
            product_lower = product_name.lower()
            # Fuzzy match product name against query
            if fuzz.partial_ratio(product_lower, query_lower) > 70 or any(word in product_lower for word in query_lower.split()):
                sections = product_data.get("sections", {})
                for title, content in sections.items():
                    if is_contextually_relevant(query, title, content):
                        # Prefer summarizing longer content blocks
                        if len(content) > 300:
                            snippet = summarize_with_llm(content)
                        else:
                            snippet = content.strip().replace("\n", " ")

                        matches.append(f"🔹 **{product_name}** → _{title}_\n{snippet}")
                        if len(matches) >= MAX_MATCHES:
                            break
            if len(matches) >= MAX_MATCHES:
                break

    if not matches:
        return f"❌ Keine relevanten Abschnitte gefunden für: '{query}'"

    return f"✅ Gefundene Informationen für: '{query}'\n\n" + "\n\n".join(matches)

# 🧰 Final tool
compendium_section_filter_tool = Tool(
    name="compendium_section_filter",
    description="Durchsucht das Swissmedic Compendium nach relevanten Produktinformationen (z.B. 'aspirin Schwangerschaft', 'Co-Dafalgan Stillzeit') und liefert eine kurze Zusammenfassung relevanter Abschnitte.",
    func=compendium_section_filter_func,
    args_schema=CompendiumSectionFilterInput,
)