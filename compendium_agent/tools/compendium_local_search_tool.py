import os
import re
from langchain.tools import Tool

COM_DATABASE = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\Compendium_database"
RELEVANT_HEADERS = [
    "Schwangerschaft", "Stillzeit", "Interaktionen", "Kontraindikationen", "Dosierung"
]

def extract_sections_from_txt(drug_name: str) -> str:
    # Find the file
    filename = os.path.join(COM_DATABASE, f"{drug_name.lower()}.txt")
    if not os.path.exists(filename):
        return f"❌ Kein lokaler Compendium-Eintrag für '{drug_name}' gefunden."

    # Read file
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    sections = []
    for header in RELEVANT_HEADERS:
        pattern = rf"## {header}\s+(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            sections.append(f"## {header}\n{match.group(1).strip()}\n")

    if sections:
        return f"📘 Gefundene Abschnitte für **{drug_name.capitalize()}**:\n\n" + "\n".join(sections)
    return "⚠️ Keine relevanten Abschnitte gefunden."
def get_structured_sections(drug_name: str) -> list[dict]:
    path = os.path.join(COM_DATABASE, f"{drug_name.lower()}.txt")
    if not os.path.exists(path):
        return []

    sections = []
    current_section = {"title": "", "text": ""}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                if current_section["title"]:
                    sections.append(current_section)
                current_section = {"title": line.strip(), "text": ""}
            else:
                current_section["text"] += line.strip() + " "

        if current_section["title"]:
            sections.append(current_section)

    return sections

# LangChain Tool
compendium_local_tool = Tool(
    name="compendium_local_lookup",
    func=extract_sections_from_txt,
    description="Sucht strukturierte medizinische Informationen (z.B. Schwangerschaft, Dosierung) aus lokal gespeicherten Compendium-Textdateien."
)