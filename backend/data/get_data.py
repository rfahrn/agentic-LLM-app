# get data from FDA - https://dps.fda.gov/medguide#csv - oder xlsx 
# to then do RAG - Faiss 
import os
import sys
import requests
import pandas as pd
from datetime import datetime

def sanitize(text):
    """Sanitize strings to make them filesystem-safe."""
    return str(text).replace(" ", "_").replace(";", "_").replace("/", "-")

def main(excel_path):
    df = pd.read_excel(excel_path, header = 1, sheet_name = 0)
    print(df.head(3))
    today_str = datetime.today().strftime("%Y_%m_%d")
    output_dir = f"data/MedicationGuides_{today_str}"
    os.makedirs(output_dir, exist_ok=True)

    for idx, row in df.iterrows():
        try:
            drug_name = sanitize(row['Drug Name'])
            active_ing = sanitize(row['Active Ingredient'])
            form_route = sanitize(row['Form; Route'])
            appl_no = str(row['Appl. No.'])
            company = sanitize(row['Company'])
            date = sanitize(row['Date'])
            url = str(row['URL']).split("#")[0]
            filename = f"{drug_name}_{active_ing}_{form_route}_{appl_no}_{company}_{date}.pdf"
            filepath = os.path.join(output_dir, filename)
            response = requests.get(url)
            response.raise_for_status() 

            with open(filepath, "wb") as f:
                f.write(response.content)

            print(f"[✓] Saved: {filepath}")

        except Exception as e:
            print(f"[✗] Failed row {idx + 1}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_guides.py path_to_file.xlsx")
    else:
        main(sys.argv[1])
