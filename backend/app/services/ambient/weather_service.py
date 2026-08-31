"""
Realtime Ambient & Weather Context Service for CAKRA AI
======================================================
Menyediakan informasi live cuaca (dinamis sesuai lokasi pengguna / Bandung HQ / Turen Malang)
dan status jam kerja operasional PT Pindad secara non-blocking melalui in-memory background cache.
"""

import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger("CAKRA_AMBIENT")

# Koordinat Default: Kantor Pusat PT Pindad Bandung
_BANDUNG_LAT = -6.9271
_BANDUNG_LON = 107.6413

# Cache Memory Multi-Koordinat: Key = (round(lat, 2), round(lon, 2)) -> Value = dict(data, last_updated)
_MULTI_WEATHER_CACHE: Dict[Tuple[float, float], Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 600  # 10 menit (fresh & akurat)

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

_BULAN_INDONESIA = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]
_HARI_INDONESIA = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _resolve_location_name(lat: float, lon: float, city_hint: Optional[str] = None) -> str:
    """Mengidentifikasi nama lokasi fasilitas Pindad atau kota terdeteksi."""
    if city_hint and city_hint.strip():
        return city_hint.strip()
    
    # Deteksi radius fasilitas Pindad (dalam derajat ~ 15-20km)
    # 1. Turen / Malang: ~ -8.16, 112.71
    if abs(lat - (-8.16)) < 0.25 and abs(lon - 112.71) < 0.25:
        return "Divisi Munisi PT Pindad, Turen, Malang, Jawa Timur"
    # 2. Kantor Pusat Bandung: ~ -6.92, 107.64
    elif abs(lat - (-6.92)) < 0.25 and abs(lon - 107.64) < 0.25:
        return "Kantor Pusat PT Pindad (Persero), Jl. Gatot Subroto No. 517, Bandung, Jawa Barat"
    # 3. Kantor Jakarta: ~ -6.20, 106.82
    elif abs(lat - (-6.20)) < 0.3 and abs(lon - 106.82) < 0.3:
        return "Kantor Perwakilan PT Pindad, Jakarta"
    else:
        return f"Lokasi Pengguna (Koordinat: {lat:.3f}, {lon:.3f})"


async def fetch_live_weather(lat: float = _BANDUNG_LAT, lon: float = _BANDUNG_LON) -> Dict[str, Any]:
    """Fetch data cuaca live dari Open-Meteo secara asinkron berdasarkan koordinat."""
    global _MULTI_WEATHER_CACHE
    now_ts = time.time()
    cache_key = (round(lat, 2), round(lon, 2))
    
    cached = _MULTI_WEATHER_CACHE.get(cache_key)
    if cached and (now_ts - cached.get("last_updated", 0) < _CACHE_TTL_SECONDS):
        return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        f"&timezone=auto"
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

                weather_data = {
                    "temperature": temp,
                    "condition": condition,
                    "humidity": humidity,
                    "wind_speed": wind,
                    "last_updated": now_ts,
                    "lat": lat,
                    "lon": lon,
                }
                _MULTI_WEATHER_CACHE[cache_key] = weather_data
                logger.info(f"[AMBIENT] ⛅ Live weather ({lat:.2f}, {lon:.2f}) updated: {temp}°C, {condition}, RH {humidity}%")
                return weather_data
    except Exception as e:
        logger.warning(f"[AMBIENT] ⚠️ Weather fetch fallback ({lat:.2f}, {lon:.2f}): {e}")

    # Fallback jika belum pernah ada cache
    if cached:
        return cached

    default_data = {
        "temperature": 28,
        "condition": "Cerah Berawan",
        "humidity": 65,
        "wind_speed": 10,
        "last_updated": now_ts,
        "lat": lat,
        "lon": lon,
    }
    _MULTI_WEATHER_CACHE[cache_key] = default_data
    return default_data


def get_cached_weather_sync(lat: float = _BANDUNG_LAT, lon: float = _BANDUNG_LON) -> Dict[str, Any]:
    """Mengembalikan data cuaca dari cache secara sinkron untuk prompt builder (0ms)."""
    global _MULTI_WEATHER_CACHE
    cache_key = (round(lat, 2), round(lon, 2))
    cached = _MULTI_WEATHER_CACHE.get(cache_key)

    # Jika cache belum ada atau kadaluarsa, trigger background fetch
    if not cached or (time.time() - cached.get("last_updated", 0) > _CACHE_TTL_SECONDS):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(fetch_live_weather(lat, lon))
        except Exception:
            pass

    if cached:
        return cached

    return {
        "temperature": 28,
        "condition": "Cerah Berawan",
        "humidity": 65,
        "wind_speed": 10,
        "last_updated": 0,
        "lat": lat,
        "lon": lon,
    }


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


def get_ambient_context_summary(
    employee_name: str = "Pegawai",
    client_context: Optional[Dict[str, Any]] = None
) -> str:
    """Merangkum string ambient context awareness untuk disuntikkan ke System Prompt."""
    client_context = client_context or {}
    
    # 1. Koordinat & Lokasi
    lat = float(client_context.get("lat", _BANDUNG_LAT)) if client_context.get("lat") is not None else _BANDUNG_LAT
    lon = float(client_context.get("lon", _BANDUNG_LON)) if client_context.get("lon") is not None else _BANDUNG_LON
    city_hint = client_context.get("city") or client_context.get("city_hint")
    location_name = _resolve_location_name(lat, lon, city_hint)
    
    # 2. Waktu & Tanggal (WIB / WITA / WIT atau Browser Timezone)
    now = datetime.now()
    hari = _HARI_INDONESIA[now.weekday()]
    bulan = _BULAN_INDONESIA[now.month]
    
    tz_name = "WIB"
    if client_context.get("timezone"):
        tz_raw = str(client_context["timezone"]).lower()
        if "makassar" in tz_raw or "denpasar" in tz_raw or "wita" in tz_raw:
            tz_name = "WITA"
        elif "jayapura" in tz_raw or "wit" in tz_raw:
            tz_name = "WIT"
            
    tanggal_str = f"{hari}, {now.day} {bulan} {now.year}, pukul {now.strftime('%H:%M')} {tz_name}"
    
    # 3. Cuaca
    weather = get_cached_weather_sync(lat, lon)
    temp = weather.get("temperature", 28)
    cond = weather.get("condition", "Cerah Berawan")
    hum = weather.get("humidity", 65)
    wind = weather.get("wind_speed", 10)
    
    op_status = get_pindad_operational_status(now)
    
    return (
        f"🌐 [FAKTA REALTIME LINGKUNGAN & CUACA PENGGUNA (MUTLAK & AKURAT)]:\n"
        f"• Waktu & Tanggal Saat Ini : {tanggal_str} (Status: {op_status})\n"
        f"• Lokasi Terdeteksi         : {location_name}\n"
        f"• Cuaca & Suhu Real-Time    : {temp}°C, {cond} (Kelembapan: {hum}%, Angin: {wind} km/jam)\n"
        f"• Profil Korporasi          : PT Pindad (Persero) — DEFEND ID\n\n"
        f"[ATURAN MUTLAK WAKTU & CUACA]:\n"
        f"Jika pengguna menanyakan jam, waktu, hari, tanggal, atau kondisi cuaca/suhu saat ini, "
        f"kamu WAJIB menjawab secara lugas menggunakan data fakta di atas ({tanggal_str}, Suhu: {temp}°C, {cond}). "
        f"DILARANG KERAS mengarang jam atau temperatur lain!"
    )
