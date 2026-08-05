import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("CAKRA_GEOCODING")

async def geocode_osm(address: str) -> Optional[Dict[str, float]]:
    """
    Mencari kordinat Latitude dan Longitude berdasarkan alamat menggunakan Nominatim (OpenStreetMap).
    Tanpa API Key, gratis, batasan 1 request / detik.
    """
    if not address or len(address.strip()) < 3:
        return None

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
