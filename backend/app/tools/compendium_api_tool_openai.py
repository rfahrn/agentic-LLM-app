import os
import json
from agents import function_tool
import os
import json
from agents import function_tool

@function_tool
def compendium_api_tool(query: str) -> str:
    """
    Antworten basierend auf lokal gespeicherten Compendium.ch API-Daten (als JSON).
    
    Args:
        query: Die Frage zur Arzneimittelinformation.
    """
    try:
        path = ".data/Compendium_database"
        context = ""
        for fname in os.listdir(path):
            if fname.endswith(".json"):
                with open(os.path.join(path, fname), "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    for name, content in doc.items():
                        context += f"# {name}\n"
                        for section, body in content.get("sections", {}).items():
                            context += f"## {section}\n{body}\n\n"
        if not context:
            return "❌ Keine Compendium-API-Daten gefunden."

        return (
            f"Beantworte die folgende Frage basierend auf den Daten von Compendium.ch:\n\n"
            f"Frage: {query}\n\n"
            f"Daten:\n{context[:5000]}"  # Optional truncate for model input safety
        )
    except Exception as e:
        return f"❌ Fehler beim Laden der Compendium-Daten: {e}"
