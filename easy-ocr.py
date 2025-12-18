import fitz
import base64
import requests
from pathlib import Path
from PIL import Image
import io
import time

# ==============================
# KONFIGURASI
# ==============================
PDF_DIR = Path("ocr_file")
OUTPUT_DIR = Path("output_text")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3-vl:8b"

OUTPUT_DIR.mkdir(exist_ok=True)

PROMPT = (
    "You are an OCR engine.\n"
    "Extract ALL readable text from this document image.\n"
    "Preserve paragraphs and line breaks.\n"
    "Do NOT summarize.\n"
    "Do NOT explain.\n"
    "Return only the extracted text."
)

# ==============================
# UTIL
# ==============================
def image_to_base64(img: Image.Image) -> str:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def call_qwen_vl(image_b64: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": PROMPT,
        "stream": False,
        "images": [image_b64],
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=600)
    response.raise_for_status()
    return response.json().get("response", "")


# ==============================
# CORE
# ==============================
def extract_pdf(pdf_path: Path) -> str:
    print(f"\n📄 Processing: {pdf_path.name}")
    doc = fitz.open(pdf_path)

    collected_text = []

    for idx in range(doc.page_count):
        page = doc.load_page(idx)

        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        print(f"   🖼️ Page {idx + 1}/{doc.page_count} → Qwen3-VL")

        start = time.time()
        text = call_qwen_vl(image_to_base64(img))
        elapsed = time.time() - start

        print(f"      ✓ Done ({elapsed:.1f}s)")

        collected_text.append(f"\n===== PAGE {idx + 1} =====\n")
        collected_text.append(text.strip())

    doc.close()
    return "\n".join(collected_text)


# ==============================
# FILE PICKER
# ==============================
def choose_files():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print("❌ Tidak ada file PDF di folder ocr_file/")
        return []

    print("\n📂 Daftar file PDF di ocr_file/\n")
    for i, f in enumerate(pdf_files, 1):
        print(f"[{i}] {f.name}")

    print("\nPilih file:")
    print(" - satu file  : 1")
    print(" - banyak     : 1,3,5")
    print(" - semua file : all")

    choice = input("\n> ").strip().lower()

    if choice == "all":
        return pdf_files

    selected = []
    indexes = []

    try:
        indexes = [int(x) for x in choice.split(",")]
    except ValueError:
        print("❌ Input tidak valid")
        return []

    for i in indexes:
        if 1 <= i <= len(pdf_files):
            selected.append(pdf_files[i - 1])

    return selected


# ==============================
# MAIN
# ==============================
def main():
    files = choose_files()

    if not files:
        print("❌ Tidak ada file dipilih")
        return

    for pdf in files:
        try:
            text = extract_pdf(pdf)

            output_file = OUTPUT_DIR / f"{pdf.stem}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)

            print(f"\n✅ Saved: {output_file}\n")

        except Exception as e:
            print(f"❌ Gagal memproses {pdf.name}: {e}")


if __name__ == "__main__":
    main()
