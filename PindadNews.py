import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json
import time
import random
import re

# --- KONFIGURASI ---
BASE_URL = "https://pindad.com"
WEAPONS_URL = "https://pindad.com/weapon"  # ✅ URL halaman senjata
OUTPUT_FILE = "data_senjata_pindad.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- SESI REQUEST ROBUST ---
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2, 
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

http_session = create_session()

def get_weapon_detail(url):
    """Ambil detail senjata dari halaman detail"""
    detail_data = {
        "deskripsi": "",
        "spesifikasi": {},
        "gambar_tambahan": [],
        "kategori": "",
        "fitur": ""
    }
    
    try:
        response = http_session.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Ambil deskripsi utama
            content_div = soup.select_one('div.hentry__content')
            if content_div:
                paragraphs = content_div.select('p')
                if paragraphs:
                    detail_data["deskripsi"] = paragraphs[0].get_text(strip=True)
            
            # 2. Cari spesifikasi (dalam HTML yang ada)
            # Cari semua div yang mungkin mengandung spesifikasi
            all_divs = soup.select('div')
            for div in all_divs:
                text = div.get_text(strip=True, separator=' ')
                if any(keyword in text.lower() for keyword in 
                      ['kaliber', 'panjang', 'berat', 'jarak', 'mekanisme', 'kapasitas']):
                    # Coba ekstrak tabel atau list
                    rows = div.select('tr, li, p')
                    for row in rows:
                        row_text = row.get_text(strip=True, separator=' ')
                        if ':' in row_text:
                            parts = row_text.split(':', 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip()
                                detail_data["spesifikasi"][key] = value
            
            # 3. Ambil gambar tambahan
            img_tags = soup.select('img[src*="/uploads/images/product/"]')
            for img in img_tags:
                src = img.get('src')
                if src:
                    if not src.startswith('http'):
                        src = BASE_URL + src
                    if src not in detail_data["gambar_tambahan"]:
                        detail_data["gambar_tambahan"].append(src)
            
            # 4. Ambil kategori dari filter
            # Cari filter aktif berdasarkan data-filter di HTML
            filter_spans = soup.select('ul.portfolio-filter li.current a')
            if filter_spans:
                detail_data["kategori"] = filter_spans[0].get_text(strip=True)
            
            # 5. Cari fitur-fitur
            feature_keywords = ['fitur', 'keunggulan', 'features', 'kelebihan']
            for keyword in feature_keywords:
                headings = soup.find_all(['h2', 'h3', 'h4', 'strong', 'b'], 
                                        text=re.compile(keyword, re.IGNORECASE))
                for heading in headings:
                    next_elem = heading.find_next_sibling()
                    features = []
                    count = 0
                    while next_elem and count < 5:
                        if next_elem.name in ['ul', 'ol']:
                            items = next_elem.select('li')
                            features.extend([li.get_text(strip=True) for li in items])
                            break
                        elif next_elem.name == 'p':
                            features.append(next_elem.get_text(strip=True))
                        next_elem = next_elem.find_next_sibling()
                        count += 1
                    if features:
                        detail_data["fitur"] = "\n".join(features)
                        break
                    
    except Exception as e:
        print(f"    [!] Gagal ambil detail {url}: {e}")
    
    return detail_data

def scrape_pindad_weapons():
    """Scraping semua senjata dari halaman weapons"""
    all_weapons = []
    
    print(f"=== Mulai Scraping Senjata Pindad ===")
    print(f"URL: {WEAPONS_URL}")
    
    try:
        response = http_session.get(WEAPONS_URL, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            print(f"Gagal mengakses halaman (Status: {response.status_code}).")
            return all_weapons
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ✅ ANALISIS STRUKTUR HTML YANG DIBERIKAN:
        # 1. Container utama: <ul class="portfolio groups isotope">
        # 2. Setiap item: <li class="isotope-item" data-id="id-XXXX">
        # 3. Dalam setiap li ada div.image > img (gambar)
        # 4. Dan div.portfolio-detail > div.title > a (judul & link)
        
        # CARI ITEM SENJATA BERDASARKAN STRUKTUR YANG ADA
        weapons_container = soup.select_one('ul.portfolio.groups.isotope')
        
        if not weapons_container:
            print("Tidak ditemukan container senjata")
            # Coba alternatif: cari semua li dengan class isotope-item
            weapon_items = soup.select('li.isotope-item')
        else:
            weapon_items = weapons_container.select('li.isotope-item')
        
        print(f"Ditemukan {len(weapon_items)} item senjata")
        
        for item in weapon_items:
            try:
                # 1. Ambil judul dan link
                title_link = item.select_one('div.portfolio-detail div.title a')
                if not title_link:
                    continue
                    
                weapon_name = title_link.get_text(strip=True)
                link = title_link.get('href', '')
                
                if link and not link.startswith('http'):
                    link = BASE_URL + link
                
                # 2. Ambil gambar utama
                img_tag = item.select_one('div.image img')
                main_image = ""
                if img_tag:
                    main_image = img_tag.get('src', '')
                    if main_image and not main_image.startswith('http'):
                        main_image = BASE_URL + main_image
                
                # 3. Ambil kategori dari class
                categories = []
                for cls in item.get('class', []):
                    if cls != 'isotope-item':
                        categories.append(cls)
                
                # 4. Ambil deskripsi singkat (kalau ada)
                short_desc = ""
                desc_div = item.select_one('div.category')
                if desc_div:
                    short_desc = desc_div.get_text(strip=True)
                
                print(f"  > Senjata: {weapon_name}")
                
                # 5. Ambil detail lengkap
                detail_data = {}
                if link:
                    print(f"    Mengambil detail dari: {link}")
                    detail_data = get_weapon_detail(link)
                    time.sleep(random.uniform(1, 2))  # Polite delay
                
                # 6. Susun data senjata
                weapon_data = {
                    "nama": weapon_name,
                    "link_detail": link,
                    "gambar_utama": main_image,
                    "kategori": ", ".join(categories) if categories else "",
                    "deskripsi_singkat": short_desc,
                    **detail_data,  # Gabungkan detail_data
                    "timestamp_scraping": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                all_weapons.append(weapon_data)
                
            except Exception as e:
                print(f"    [!] Error processing weapon item: {e}")
                continue
        
    except Exception as e:
        print(f"Error utama: {e}")
    
    return all_weapons

def main():
    """Fungsi utama"""
    print("=== PT PINDAD WEAPONS SCRAPER ===")
    
    # Scraping data
    weapons_data = scrape_pindad_weapons()
    
    # Simpan ke JSON
    if weapons_data:
        try:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(weapons_data, f, ensure_ascii=False, indent=4)
            print(f"\n[SUKSES] {len(weapons_data)} senjata tersimpan di '{OUTPUT_FILE}'")
            
            # Tampilkan preview
            print(f"\n=== PREVIEW DATA ===")
            for i, weapon in enumerate(weapons_data[:3]):  # Tampilkan 3 pertama
                print(f"\n{i+1}. {weapon['nama']}")
                print(f"   Kategori: {weapon.get('kategori', 'N/A')}")
                print(f"   Link: {weapon['link_detail']}")
                if weapon.get('deskripsi'):
                    desc = weapon['deskripsi'][:100] + "..." if len(weapon['deskripsi']) > 100 else weapon['deskripsi']
                    print(f"   Deskripsi: {desc}")
                
        except Exception as e:
            print(f"Gagal menyimpan file JSON: {e}")
    else:
        print("\n[GAGAL] Tidak ada data yang berhasil di-scrape")

if __name__ == "__main__":
    main()