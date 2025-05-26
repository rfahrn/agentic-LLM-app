import os
import fitz  # PyMuPDF

SOURCE_DIR = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\MedicationGuides_2025_05_19"
FIXED_DIR = SOURCE_DIR + "_FIXED"
os.makedirs(FIXED_DIR, exist_ok=True)

def fix_pdf(input_path, output_path):
    try:
        doc = fitz.open(input_path)
        doc.save(output_path)
        doc.close()
        print(f"✅ Cleaned: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"❌ Failed: {os.path.basename(input_path)} – {e}")
        return False

def fix_all_pdfs(source_folder, target_folder):
    for filename in os.listdir(source_folder):
        if filename.lower().endswith(".pdf"):
            input_path = os.path.join(source_folder, filename)
            output_path = os.path.join(target_folder, filename)
            fix_pdf(input_path, output_path)

if __name__ == "__main__":
    print(f"🔄 Cleaning PDFs...\nFROM: {SOURCE_DIR}\nTO:   {FIXED_DIR}\n")
    fix_all_pdfs(SOURCE_DIR, FIXED_DIR)
