import pandas as pd
import json
from docx import Document
import re
from collections import defaultdict

# -------- Step 1: Load ATC Data --------
def load_atc_excel(file_path):
    xls = pd.ExcelFile(file_path)
    atc_data = {}
    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        if df.shape[1] < 2:
            continue
        try:
            category = df.iloc[2, 0] if len(df) > 2 else "Unknown Category"
        except:
            continue
        entries = []
        last_valid_med = None
        for i in range(3, df.shape[0]):
            if df.shape[1] < 2:
                continue
            med = df.iloc[i, 1]
            if pd.isna(med):
                continue
            if med == '"':
                med = last_valid_med
            else:
                last_valid_med = med
            description = df.iloc[i, 2] if df.shape[1] > 2 else None
            formulation = df.iloc[i, 3] if df.shape[1] > 3 else None
            entries.append({
                "medication": str(med).strip(),
                "description": description,
                "formulated_name": formulation
            })
        if category:
            atc_data[category] = entries
    return atc_data

# -------- Step 2: Load Interaction Data --------
def load_interaction_data(file_path):
    xl = pd.ExcelFile(file_path)
    interaction_sheet = xl.parse(xl.sheet_names[0])
    severity_sheet = xl.parse("Tabelle2")

    interactions = []
    current_ia = None
    for _, row in interaction_sheet.iterrows():
        if pd.notna(row.get("IA-Nr")):
            current_ia = {
                "IA_number": int(row["IA-Nr"]),
                "category": row.get("Interaktion", ""),
                "pairs": []
            }
            interactions.append(current_ia)
        if pd.notna(row.get("Spezialitäten")) and current_ia:
            medications = row["Spezialitäten"].split(" - ")
            description = row.get("Interaktionsbeschreibung", "")
            current_ia["pairs"].append({
                "medications": [med.strip() for med in medications],
                "description": description
            })

    for ia in interactions:
        level_row = severity_sheet[severity_sheet["IA-Nummer"] == ia["IA_number"]]
        if not level_row.empty and pd.notna(level_row["Stufe"].values[0]):
            ia["interaction_level"] = int(level_row["Stufe"].values[0])
        else:
            ia["interaction_level"] = None
    return interactions

# -------- Step 3: Load and Structure Word Document --------
def parse_word_doc(doc_path):
    doc = Document(doc_path)
    text = "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    lines = text.split("\n")
    sections = {
        "no_known_interactions": None,
        "unapproved_note": None,
        "supplements_note": None,
        "consultation_recommendations": {},
        "interaction_levels": {},
        "specific_interactions": [],
        "food_interactions": [],
        "intake_guidance": {"general": None, "exceptions": []},
        "generics": {"available": [], "not_available": [], "epilepsy_caution": False},
        "contact": None,
        "double_medication": None,
        "indications": defaultdict(list)
    }

    current_section = None
    current_indication = None

    for line in lines:
        if "Es liegt keine bekannte Wechselwirkung" in line:
            sections["no_known_interactions"] = line
        elif "nicht um ein in der Schweiz zugelassenes Medikament" in line:
            sections["unapproved_note"] = line
        elif "Nahrungsergänzungsmittel" in line and "nicht berücksichtigt" in line:
            sections["supplements_note"] = line
        elif line.startswith("IA 1 und 2"):
            sections["consultation_recommendations"]["IA_1_2"] = line
        elif line.startswith("IA 3 und 4"):
            sections["consultation_recommendations"]["IA_3_4"] = line
        elif line.startswith("IA 5/6/7"):
            sections["consultation_recommendations"]["IA_5_6_7"] = line
        elif "Wechselwirkung der Klasse" in line:
            match = re.search(r"Wechselwirkung der Klasse (\d) \((.+?)\)", line)
            if match:
                sections["interaction_levels"][match.group(1)] = match.group(2)
        elif "Methotrexat und Folsäure" in line:
            current_section = "specific_interactions"
        elif current_section == "specific_interactions" and "Metoject" in line:
            sections["specific_interactions"].append({
                "medications": ["Metoject", "Acidum folicum"],
                "class": 4,
                "note": line
            })
            current_section = None
        elif "Nahrungsmittel-Interaktionen" in line:
            current_section = "food_interactions"
        elif current_section == "food_interactions":
            if "während Therapie mit" in line:
                substances = re.findall(r"Keine[n]? (.*?) während Therapie", line)
                meds = re.findall(r"mit … ?\((.*?)\)", line)
                if not meds:
                    meds = re.findall(r"mit …(.*)", line)
                if substances and meds:
                    sections["food_interactions"].append({
                        "substances": [s.strip() for s in substances[0].split(",")],
                        "affected_medications": [m.strip() for m in meds[0].split(",")]
                    })
            elif "Einnahmehinweise" in line:
                current_section = "intake_guidance"
        elif current_section == "intake_guidance":
            if "unabhängig vom Essen" in line:
                sections["intake_guidance"]["general"] = line
            elif "Milchprodukten" in line:
                sections["intake_guidance"]["exceptions"].append(line)
        elif "Generika" in line:
            current_section = "generics"
        elif current_section == "generics":
            if "Generika im Handel" in line:
                sections["generics"]["available"].append(line)
            elif "kein Generikum" in line:
                sections["generics"]["not_available"].append(line)
            elif "Epilepsie" in line:
                sections["generics"]["epilepsy_caution"] = True
        elif "Telefonnummer" in line:
            sections["contact"] = line
        elif "Doppelmedikation" in line:
            current_section = "double_medication"
        elif current_section == "double_medication" and "keine" in line.lower():
            sections["double_medication"] = line
        elif line in ["Arthrose", "Asthma", "Augen", "Blutdruck", "Blutverdünner",
                      "Blutzucker / Diabetes", "Cholesterinsenker", "Entzündliche Erkrankungen (Morbus Crohn, Rheumatoide Arthritis etc.)",
                      "Epilepsie", "Hormonersatz Wechseljahre", "Magen (PPI / Antazida)",
                      "Psychische Erkrankungen / Depressionen", "Schlafmittel", "Schmerzmittel"]:
            current_section = "indications"
            current_indication = line
        elif current_section == "indications":
            sections["indications"][current_indication].append(line)

    return sections

# -------- Step 4: Combine All --------
def combine_to_json(atc, interactions, structured_notes, out_path):
    result = {
        "ATC_catalogue": atc,
        "interactions": interactions,
        "structured_guidance": structured_notes
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

# -------- Step 5: Main Execution --------
if __name__ == "__main__":
    atc_data = load_atc_excel("ATC-Code sortierte Textbausteine aktuell.xlsx")
    interaction_data = load_interaction_data("Interaktionen nach IA-Nummern.xlsx")
    structured_notes = parse_word_doc("Textbausteine TOM-App aktuell.docx")
    combine_to_json(atc_data, interaction_data, structured_notes, "databse_new.json")
