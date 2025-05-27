# compendium_api_runner.py (new)
# compendium_api_runner.py

from backend.app.tools.compendium_API import fetch_and_parse, build_markdown
from pathlib import Path
import os

def run_compendium_cache_build(drug_name: str, output_dir: str) -> str:
    """
    Fetches data from Compendium.ch API, builds markdown, and saves both .md and .txt files.
    Returns the markdown string.
    """
    try:
        root, ns = fetch_and_parse(drug_name)
        markdown, product_name, section_links = build_markdown(root, ns)

        # Ensure output dir exists
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)

        base_name = drug_name.lower().replace(" ", "_")
        md_path = output_path / f"{base_name}.md"
        txt_path = output_path / f"{base_name}.txt"

        # Write both markdown and txt
        md_path.write_text(markdown, encoding="utf-8")
        txt_path.write_text(markdown, encoding="utf-8")

        # Debug logs
        print(f"✅ Compendium-Daten für '{drug_name}' gecached.")
        print(f"📄 Wrote: {md_path} (Size: {md_path.stat().st_size} bytes)")
        return markdown

    except Exception as e:
        print(f"❌ Fehler beim Schreiben von Compendium-Daten: {e}")
        raise
