# extract_weapon_full.py
import asyncio
from playwright.async_api import async_playwright

async def extract_pindad_page_text(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Hanya blokir gambar & CSS (jangan JS!)
        await page.route("**/*.{png,jpg,jpeg,svg}", lambda route: route.abort())

        print(f"🔍 Mengakses {url}...")
        await page.goto(url, wait_until="networkidle", timeout=30000)  # tunggu hingga benar-benar selesai

        # Ekstrak teks tanpa menghancurkan struktur penting
        content = await page.evaluate("""() => {
            // Hapus hanya elemen yang benar-benar tidak perlu
            const toRemove = [
                'script', 'style', 'header', 'footer', 
                '.topbar', '.copyright', '.back-to-top',
                '.social-icons', '.share-buttons'
            ];
            toRemove.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });

            // Ambil SEMUA teks dari body, termasuk sidebar & konten samping
            let fullText = '';
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let node;
            while (node = walker.nextNode()) {
                const text = node.textContent.trim();
                if (text && text.length > 1) {
                    fullText += text + '\\n';
                }
            }

            return fullText.trim();
        }""")

        await browser.close()
        return content

if __name__ == "__main__":
    url = "https://www.pindad.com/ss3"
    text = asyncio.run(extract_pindad_page_text(url))
    
    # Simpan ke file
    filename = "pindad_weapon_ss3.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    
    print(f"✅ Ekstraksi selesai! File disimpan sebagai: {filename}")
    print(f"📊 Panjang teks: {len(text)} karakter")