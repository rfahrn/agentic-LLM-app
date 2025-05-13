# -*- coding: utf-8 -*-
import os
import json
import requests
import streamlit as st
import os
import json
import requests
import streamlit as st

LOCAL_DATA_PATH = "data/dataset.json"
OPENFDA_API_URL = "https://api.fda.gov/drug/label.json"

def load_local_fda_data():
    if not os.path.exists(LOCAL_DATA_PATH):
        print("⚠️ Lokale FDA-Daten nicht gefunden.")
        return []

    try:
        with open(LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("results", [])
        elif isinstance(data, list):
            return data
        else:
            print("⚠️ Unerwartetes Format in der lokalen FDA-Datei.")
            return []
    except Exception as e:
        print(f"❗ Fehler beim Laden der lokalen FDA-Daten: {e}")
        return []
    
def format_full_fda_entry(entry):
    """Format all important fields nicely together."""
    sections = []

    FIELD_MAPPING = {
        "indications_and_usage": "📖 Indikationen und Anwendungsgebiete",
        "dosage_and_administration": "💉 Dosierung und Anwendung",
        "warnings": "⚠️ Warnhinweise",
        "pregnancy_or_breast_feeding": "🤰 Schwangerschaft / Stillzeit",
        "storage_and_handling": "📦 Lagerung und Handhabung",
        "adverse_reactions": "⚡ Nebenwirkungen",
        "stop_use": "🛑 Anwendung stoppen wenn...",
        "do_not_use": "🚫 Nicht verwenden wenn...",
        "purpose": "🎯 Zweck der Behandlung",
        "active_ingredient": "🧪 Aktive Inhaltsstoffe",
        "inactive_ingredient": "🧪 Inaktive Inhaltsstoffe",
        "questions": "❓ Fragen oder Kommentare",
        "clinical_pharmacology": "🧬 Klinische Pharmakologie",
        "contraindications": "❌ Kontraindikationen",
        "how_supplied": "📦 Verpackung und Lieferung"
    }

    for key, title in FIELD_MAPPING.items():
        if key in entry and isinstance(entry[key], list):
            content = entry[key][0]  # Only the first item
            sections.append(f"### {title}\n{content}")

    if sections:
        return "\n\n".join(sections)
    else:
        return "❗ Keine relevanten Informationen gefunden."

def search_openfda_local(query):
    """Search locally stored OpenFDA data and format full document."""
    results = load_local_fda_data()
    if not results:
        return None

    query = query.lower()
    matches = []

    for entry in results:
        openfda = entry.get("openfda", {})
        searchable_fields = (
            openfda.get("brand_name", []) +
            openfda.get("generic_name", []) +
            openfda.get("substance_name", [])
        )
        searchable_text = " ".join(searchable_fields).lower()

        if query in searchable_text:
            formatted = format_full_fda_entry(entry)
            matches.append(formatted)

    if matches:
        return "\n\n---\n\n".join(matches)
    return None

# === Live OpenFDA API Search ===
def search_openfda_api(query, limit=3):
    print("🌐 Anfrage an OpenFDA API wird gestartet...")

    params = {
        "search": f'indications_and_usage:"{query}"',
        "limit": limit
    }
    api_key = st.secrets["openfda"]["OPENFDA_API_KEY"]
    if api_key:
        params["api_key"] = api_key

    try:
        response = requests.get(OPENFDA_API_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❗ Fehler bei der OpenFDA API-Anfrage: {e}")
        return None

    data = response.json()
    results = data.get("results", [])
    if not results:
        return None

    api_matches = []
    for entry in results:
        formatted = format_full_fda_entry(entry)
        api_matches.append(formatted)

    if api_matches:
        return "\n\n---\n\n".join(api_matches)
    return None

# === Unified Search ===
def search_openfda(query, limit=3):
    """First search local data, then fallback to live OpenFDA API. Return full document formatted."""
    print(f"🧠 Suche nach '{query}' gestartet...")
    print("📦 Suche zuerst in lokalen FDA-Daten...")

    local_result = search_openfda_local(query)
    if local_result:
        print("✅ Treffer in lokalen FDA-Daten gefunden!")
        return local_result

    print("❌ Keine lokalen Treffer. Wechsle zur Online-Suche...")
    online_result = search_openfda_api(query, limit=limit)
    if online_result:
        print("✅ Treffer in OpenFDA API erhalten!")
        return online_result

    print("❗ Keine Informationen gefunden.")
    return None
