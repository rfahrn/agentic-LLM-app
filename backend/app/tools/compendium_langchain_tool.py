import os
from langchain.tools import Tool
from backend.app.tools.compendium_api_runner import run_compendium_cache_build

#BASE_PATH = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\Compendium_database"
BASE_PATH = os.path.join(os.path.dirname(__file__), "data", "Compendium_database")
BASE_PATH = os.path.abspath(BASE_PATH)
os.makedirs(BASE_PATH, exist_ok=True)

def extract_from_md_cache(drug_name: str, query: str) -> str:
    file_path = os.path.join(BASE_PATH, f"{drug_name.lower().replace(' ', '_')}.md")

    # Auto-fetch if missing
    if not os.path.exists(file_path):
        try:
            run_compendium_cache_build(drug_name, BASE_PATH)
        except Exception as e:
            return f"❌ Fehler beim Nachladen aus Compendium API: {e}"

    # Now load and extract from the file
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
        out.append(f"### {title}\n\n{content}\n\n🔗 [Quelle ansehen]({link})")

    return "\n\n---\n\n".join(out)

def compendium_tool_func(prompt: str) -> str:
    try:
        words = prompt.strip().split()
        if not words:
            return "⚠️ Leere Anfrage."
        drug_name = words[-1].strip(" ?.,;")
        query = " ".join(words[:-1])
        return extract_from_md_cache(drug_name, query)
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
