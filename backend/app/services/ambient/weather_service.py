"""
Realtime Ambient & Weather Context Service for CAKRA AI
======================================================
Menyediakan informasi live cuaca (Bandung HQ) dan status jam kerja operasional PT Pindad
secara non-blocking melalui in-memory background cache.
"""

import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("CAKRA_AMBIENT")

# Koordinat Kantor Pusat PT Pindad Bandung
_BANDUNG_LAT = -6.9271
_BANDUNG_LON = 107.6413

# Cache Memory
_WEATHER_CACHE: Dict[str, Any] = {
    "temperature": 28,
    "condition": "Cerah Berawan",
    "humidity": 65,
    "wind_speed": 10,
    "last_updated": 0,
}
_CACHE_TTL_SECONDS = 1800  # 30 menit

# Weather code mapping (WMO Weather interpretation codes)
_WMO_WEATHER_MAP = {
    0: "Cerah",
    1: "Sebagian Besar Cerah",
    2: "Cerah Berawan",
    3: "Berawan",
    45: "Berkabut",
    48: "Kabut Tebal",
    51: "Gerimis Ringan",
    53: "Gerimis Sedang",
    55: "Gerimis Lebat",
    61: "Hujan Ringan",
    63: "Hujan Sedang",
    65: "Hujan Lebat",
    80: "Hujan Lokal / Sporadis",
    81: "Hujan Sedang - Lebat",
    82: "Hujan Sangat Lebat",
    95: "Badai Petir",
}


async def fetch_live_weather() -> Dict[str, Any]:
    """Fetch data cuaca live dari Open-Meteo secara asinkron (non-blocking)."""
    global _WEATHER_CACHE
    now_ts = time.time()
    
    if now_ts - _WEATHER_CACHE.get("last_updated", 0) < _CACHE_TTL_SECONDS:
        return _WEATHER_CACHE

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={_BANDUNG_LAT}&longitude={_BANDUNG_LON}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        f"&timezone=Asia%2FJakarta"
    )

    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                current = data.get("current", {})
                w_code = current.get("weather_code", 2)
                condition = _WMO_WEATHER_MAP.get(w_code, "Cerah Berawan")
                temp = round(current.get("temperature_2m", 28))
                humidity = round(current.get("relative_humidity_2m", 65))
                wind = round(current.get("wind_speed_10m", 10))

                _WEATHER_CACHE = {
                    "temperature": temp,
                    "condition": condition,
                    "humidity": humidity,
                    "wind_speed": wind,
                    "last_updated": now_ts,
                }
                logger.info(f"[AMBIENT] ⛅ Live weather Bandung updated: {temp}°C, {condition}, RH {humidity}%")
    except Exception as e:
        logger.warning(f"[AMBIENT] ⚠️ Weather fetch fallback (using cached/default): {e}")

    return _WEATHER_CACHE


def get_cached_weather_sync() -> Dict[str, Any]:
    """Mengembalikan data cuaca dari cache secara sinkron untuk prompt builder (0ms)."""
    global _WEATHER_CACHE
    # Jika cache sudah kadaluarsa, trigger background task untuk refresh
    if time.time() - _WEATHER_CACHE.get("last_updated", 0) > _CACHE_TTL_SECONDS:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(fetch_live_weather())
        except Exception:
            pass
    return _WEATHER_CACHE


def get_pindad_operational_status(now: Optional[datetime] = None) -> str:
    """
    Menghitung status jam kerja resmi PT Pindad:
    Senin - Jumat: 07:30 - 16:30 WIB
    Istirahat: 12:00 - 13:00 WIB (Jumat: 11:30 - 13:00 WIB)
    """
    if not now:
        now = datetime.now()
        
    weekday = now.weekday()  # 0=Senin, 4=Jumat, 5=Sabtu, 6=Minggu
    hour = now.hour
    minute = now.minute
    time_float = hour + (minute / 60.0)

    if weekday in (5, 6):
        return "Hari Libur Akhir Pekan"

    # Hari Kerja (Senin - Jumat)
    if time_float < 7.5:
        return "Sebelum Jam Kerja Operasional"
    elif time_float > 16.5:
        return "Di Luar Jam Kerja (Masa Lembur/Malam)"
    else:
        # Sedang dalam jam kerja, cek jam istirahat
        if weekday == 4:  # Jumat
            if 11.5 <= time_float <= 13.0:
                return "Jam Istirahat & Sholat Jumat"
        else:
            if 12.0 <= time_float <= 13.0:
                return "Jam Istirahat Kerja"
        return "Jam Kerja Aktif"


def get_ambient_context_summary(employee_name: str = "Pegawai") -> str:
    """Merangkum string ambient context awareness untuk disuntikkan ke System Prompt."""
    now = datetime.now()
    hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][now.weekday()]
    tanggal_str = now.strftime(f"{hari}, %d %B %Y — %H:%M WIB")
    
    weather = get_cached_weather_sync()
    temp = weather.get("temperature", 28)
    cond = weather.get("condition", "Cerah Berawan")
    hum = weather.get("humidity", 65)
    wind = weather.get("wind_speed", 10)
    
    op_status = get_pindad_operational_status(now)
    
    return (
        f"🌐 REALTIME ENVIRONMENT & CONTEXT AWARENESS:\n"
        f"• Waktu & Tanggal Server : {tanggal_str} (Status: {op_status})\n"
        f"• Lokasi Utama Kantor   : Kantor Pusat PT Pindad (Persero), Jl. Gatot Subroto No. 517, Bandung, Jawa Barat\n"
        f"• Cuaca Terkini (Bandung): {temp}°C, {cond} (Kelembapan: {hum}%, Angin: {wind} km/jam)\n"
        f"• Profil Korporasi       : PT Pindad (Persero) — Anggota Holding BUMN Industri Pertahanan (DEFEND ID)\n"
    )
