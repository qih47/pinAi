import re
import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("CAKRA_GEOCODING")

# Cache lokasi korporat PT Pindad untuk resolusi instan tanpa dependensi jaringan
PINDAD_LOCATIONS = {
    "bandung": {
        "lat": -6.9189,
        "lng": 107.6338,
        "name": "PT Pindad (Persero) Kantor Pusat Bandung, Jl. Gatot Subroto No. 517, Bandung",
        "division": "Kantor Pusat, Divisi Senjata, Divisi Kendaraan Khusus, Divisi Alat Berat",
    },
    "turen": {
        "lat": -8.1728,
        "lng": 112.7092,
        "name": "PT Pindad (Persero) Divisi Munisi Turen, Jl. Panglima Sudirman No. 1, Turen, Malang, Jawa Timur",
        "division": "Divisi Munisi",
    },
    "malang": {
        "lat": -8.1728,
        "lng": 112.7092,
        "name": "PT Pindad (Persero) Divisi Munisi Turen, Malang, Jawa Timur",
        "division": "Divisi Munisi",
    },
    "subang": {
        "lat": -6.5683,
        "lng": 107.7594,
        "name": "PT Pindad Fasilitas Uji Coba & Gudang Terpadu Subang, Jawa Barat",
        "division": "Fasilitas Pengujian & Gudang Munisi",
    },
    "jakarta": {
        "lat": -6.2146,
        "lng": 106.8451,
        "name": "PT Pindad Kantor Perwakilan Jakarta",
        "division": "Kantor Perwakilan & Hubungan Kelembagaan",
    },
}


async def geocode_osm(address: str) -> Optional[Dict[str, Any]]:
    """
    Mencari kordinat Latitude dan Longitude berdasarkan alamat menggunakan Nominatim (OpenStreetMap)
    dengan cache lokasi internal PT Pindad untuk respon cepat dan andal.
    """
    if not address or len(address.strip()) < 3:
        return None

    clean_addr = address.strip().lower()

    # 1. Cek Cache Korporat PT Pindad (Instan & Offline)
    for key, loc in PINDAD_LOCATIONS.items():
        if key in clean_addr or (f"pindad {key}" in clean_addr) or (key in clean_addr and "pindad" in clean_addr):
            logger.info(f"[GEOCODING] ⚡ Corporate Cache HIT for '{address}': {loc['name']}")
            return {
                "lat": loc["lat"],
                "lng": loc["lng"],
                "name": loc["name"],
                "division": loc.get("division"),
                "source": "pindad_corporate_cache"
            }

    try:
        logger.info(f"[GEOCODING] Melacak koordinat untuk: '{address}' via Nominatim OSM")
        
        # Wajib menyertakan User-Agent yang unik sesuai kebijakan Nominatim
        headers = {
            "User-Agent": "CAKRA-AI-PinAi/1.0 (internal_corporate_agent)"
        }
        
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers=headers
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                lat = float(result["lat"])
                lng = float(result["lon"])
                name = result.get("display_name", address)
                
                logger.info(f"[GEOCODING] ✅ Ditemukan: {lat}, {lng} ({name[:50]}...)")
                return {
                    "lat": lat,
                    "lng": lng,
                    "name": name
                }
            else:
                logger.warning(f"[GEOCODING] ❌ Tidak ditemukan koordinat untuk: '{address}'")
                return None
                
    except Exception as e:
        logger.error(f"[GEOCODING] Error memanggil Nominatim API: {e}")
        return None
