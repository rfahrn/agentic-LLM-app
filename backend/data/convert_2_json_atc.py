
import pandas as pd
import json
import re

MAIN_CATEGORY_MAP = {
    "A": "A Alimentäres System und Stoffwechsel",
    "B": "B Blut und Blut bildende Organe",
    "C": "C Kardiovaskuläres System",
    "D": "D Dermatika",
    "G": "G Urogenitalsystem und Sexualhormone",
    "H": "H Systemische Hormonpräparate, exkl. Sexualhormone und Insuline",
    "J": "J Antiinfektiva zur systemischen Anwendung",
    "L": "L Antineoplastische und immunmodulierende Mittel",
    "M": "M Muskel- und Skelettsystem",
    "N": "N Nervensystem",
    "P": "P Antiparasitäre Mittel, Insektizide und Repellenzien",
    "R": "R Respirationstrakt",
    "S": "S Sinnesorgane",
    "V": "V Varia"
}

def load_atc_excel(file_path):
    xls = pd.ExcelFile(file_path)
    atc_data = {cat: {} for cat in MAIN_CATEGORY_MAP.values()}

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)

        if df.shape[1] < 1 or df.empty:
            continue

        category_key = sheet_name.strip()[0]
        main_category = MAIN_CATEGORY_MAP.get(category_key, f"{category_key} (Unmapped)")
        current_subcat = None
        last_valid_subcat = None
        last_valid_med = None
        last_valid_description = None

        for i in range(df.shape[0]):
            row = df.iloc[i]
            if row.isnull().all():
                continue
            # --- Detect Subcategory ---
            raw_subcat = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if re.match(r"^[A-Z]\d{2}\s", raw_subcat):
                current_subcat = raw_subcat
                last_valid_subcat = current_subcat
                if current_subcat not in atc_data[main_category]:
                    atc_data[main_category][current_subcat] = []
            elif raw_subcat == '"' and last_valid_subcat:
                current_subcat = last_valid_subcat

            if not current_subcat:
                continue

            if current_subcat not in atc_data[main_category]:
                atc_data[main_category][current_subcat] = []
            if (
                main_category == "N Nervensystem"
                and current_subcat == "N02 Analgetika"
                and len(row) > 4
            ):
                group_val = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None
                product_str = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else None
                description = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None
                usage = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else None

                if group_val in ("A", "B", "C") and product_str:
                    entry = {
                        "Gruppe": group_val,
                        "Product-Medikament": [x.strip() for x in product_str.split("/") if x.strip()],
                        "Beschreibung": description,
                        "Anwendung": usage
                    }
                    atc_data[main_category][current_subcat].append(entry)
                continue

            if main_category == "N Nervensystem" and current_subcat != "N02 Analgetika":
                med = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else None
                if med:
                    last_valid_med = med
                else:
                    med = last_valid_med

                description = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else None
                usage = str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else None
            else:
                if len(row) > 1 and pd.notna(row.iloc[1]):
                    raw_med = str(row.iloc[1]).strip()
                    if raw_med and raw_med != '"':
                        med = raw_med
                        last_valid_med = med
                    elif raw_med == '"' and last_valid_med:
                        med = last_valid_med
                    else:
                        med = None
                else:
                    med = last_valid_med
                
                if len(row) > 2 and pd.notna(row.iloc[2]):
                    raw_desc = str(row.iloc[2]).strip()
                    if raw_desc and raw_desc != '"':
                        description = raw_desc
                        last_valid_description = description
                    elif raw_desc == '"' and last_valid_description:
                        description = last_valid_description
                    else:
                        description = None
                else:
                    description = last_valid_description
                
                usage = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else None


            entry = {
                "Product-Medikament": med,
                "Beschreibung": description,
                "Anwendung": usage
            }
            atc_data[main_category][current_subcat].append(entry)
    return atc_data

if __name__ == "__main__":
    atc_data = load_atc_excel("ATC-Code sortierte Textbausteine aktuell.xlsx")

    flat_list = []
    for main_cat, subcats in atc_data.items():
        for subcat, entries in subcats.items():
            for entry in entries:
                flat_entry = {
                    "ATC Oberkategorie": main_cat,
                    "ATC Unterkategorie": subcat,
                    "Gruppe": entry.get("group"),  # May be None
                    "Product-Medikament": entry.get("Product-Medikament"),
                    "Beschreibung": entry.get("Beschreibung"),
                    "Anwendung": entry.get("Anwendung")
                }
                flat_list.append(flat_entry)

    final_output = {
        "ATC_Codes": flat_list
    }

    with open("atc2.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)

    print("ATC data has been converted to JSON format and saved to 'atc2.json'.")
