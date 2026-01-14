import sys
import json
import subprocess
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

# ================= CONFIG =================
WEAPON_URL = "https://www.pindad.com/weapon"
SCREENSHOT_PATH = "pindad_weapon.png"
OCR_MODEL = "qwen3-vl:8b"
GEN_MODEL = "qwen2.5:14b-instruct"

# ================= STEP 1 =================
def capture_weapon_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(WEAPON_URL, wait_until="networkidle", timeout=60000)
        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        browser.close()

    return SCREENSHOT_PATH

# ================= STEP 2 =================
def ocr_with_qwen_vl(image_path):
    prompt = (
        "Lakukan OCR lengkap pada gambar ini. "
        "Ekstrak semua teks, nama produk, kategori senjata, "
        "dan deskripsinya secara detail."
    )

    with open(image_path, "rb") as img:
        process = subprocess.Popen(
            ["ollama", "run", "qwen3-vl:8b", prompt],
            stdin=img,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()

    if stderr:
        print("⚠️ Ollama stderr:", stderr.decode())

    return stdout.decode().strip()


# ================= STEP 3 =================
def semantic_filter(ocr_text, user_query):
    # Ambil potongan besar, jangan kalimat per kalimat
    paragraphs = re.split(r'\n{2,}', ocr_text)

    query_terms = [
        w for w in user_query.lower().split()
        if len(w) > 3 and w not in ["apa", "saja", "yang", "dari"]
    ]

    scored = []
    for p in paragraphs:
        score = sum(1 for q in query_terms if q in p.lower())
        scored.append((score, p))

    scored.sort(reverse=True, key=lambda x: x[0])

    # ⚠️ JANGAN KOSONG
    best_chunks = [p for s, p in scored if s >= 1][:3]

    # fallback: ambil awal OCR kalau semua score 0
    if not best_chunks:
        best_chunks = paragraphs[:2]

    return "\n\n".join(best_chunks)


# ================= STEP 4 =================
def generate_answer(context, user_query):
    prompt = f"""
Anda adalah asisten AI yang menjawab berdasarkan DATA.

Jika pertanyaan meminta daftar produk,
dan data berisi nama produk,
MAKA JAWAB DALAM BENTUK DAFTAR.

DATA:
{context}

PERTANYAAN:
{user_query}

JAWABAN:
"""

    process = subprocess.Popen(
        ["ollama", "run", "qwen2.5:14b-instruct"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = process.communicate(prompt)

    if stderr.strip():
        print("⚠️ Ollama info:", stderr.strip())

    return stdout.strip()

# ================= MAIN =================
def main():
    if len(sys.argv) < 2:
        print("❌ Gunakan: python scraping.py \"pertanyaan user\"")
        sys.exit(1)

    user_query = sys.argv[1]

    print("📸 Capture halaman weapon...")
    image = capture_weapon_page()

    print("🔍 OCR dengan Qwen3-VL...")
    ocr_text = ocr_with_qwen_vl(image)

    print("🧠 Semantic filtering...")
    context = semantic_filter(ocr_text, user_query)

    print("🤖 Generate jawaban...\n")
    answer = generate_answer(context, user_query)

    print("===== JAWABAN =====")
    print(answer)

if __name__ == "__main__":
    main()
