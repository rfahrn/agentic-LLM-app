# compendium_api_runner.py (new)

from backend.app.tools.compendium_API import fetch_and_parse, build_markdown
import os

def run_compendium_cache_build(drug_name: str, output_dir: str):
    root, ns = fetch_and_parse(drug_name)
    markdown = build_markdown(root, ns)

    os.makedirs(output_dir, exist_ok=True)
    base_name = drug_name.lower().replace(" ", "_")
    md_path = os.path.join(output_dir, f"{base_name}.md")
    txt_path = os.path.join(output_dir, f"{base_name}.txt")

    with open(md_path, "w", encoding="utf-8") as f_md:
        f_md.write(markdown)
    with open(txt_path, "w", encoding="utf-8") as f_txt:
        f_txt.write(markdown)

    print(f"✅ Compendium-Daten für '{drug_name}' gecached.")
    return md_path
