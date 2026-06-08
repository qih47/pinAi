from fastapi import APIRouter, HTTPException, Request, Query, Body, status
from pydantic import BaseModel
import hashlib
import uuid
import logging
from typing import Optional

# Hubungkan ke pool database baru kita secara aman
from backend.app.core.database import get_db, get_hris_db

router = APIRouter()
logger = logging.getLogger("CAKRA_AUTH")

# --- PYDANTIC SCHEMAS ---
class LoginRequest(BaseModel):
    username: str  # Berisi NPP Pegawai
    password: str  # Plain password dari Frontend

class LoginResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[dict] = None


# --- ENDPOINTS ---

@router.get("/verify-session", response_model=LoginResponse)
async def verify_session(token: str = Query(None)):
    """
    Mengecek status validasi token di localStorage secara asinkronus.
    """
    if not token:
        print("👤 [GUARD] Verifikasi gagal: Request datang tanpa token.")
        raise HTTPException(status_code=401, detail="Token missing")

    print(f"🔍 [AUTH] Memverifikasi session token: {token[:8]}...")
    try:
        async with get_db() as conn:
            query = """
                SELECT u.npp, u.fullname, u.divisi, u.role
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = $1 AND s.is_login = TRUE
            """
            user = await conn.fetchrow(query, token)

            if user:
                print(f"🟩 [AUTH] Session VALID untuk User: {user['fullname']} [{user['role']}]")
                
                # Update aktivitas terakhir pegawai
                await conn.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                    token,
                )
                print(f"🕒 [AUTH] last_activity updated untuk NPP: {user['npp']}")

                return LoginResponse(
                    status="success",
                    data={
                        "npp": user["npp"],
                        "username": user["npp"],
                        "fullname": user["fullname"],
                        "divisi": user["divisi"],
                        "role": user["role"],
                    }
                )
            else:
                print(f"⚠️ [AUTH] Session INVALID atau sudah kedaluwarsa untuk token: {token[:8]}...")
                raise HTTPException(status_code=401, detail="Session expired or invalid")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Verify Session Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login", response_model=LoginResponse)
async def login(request_body: LoginRequest, request: Request):
    """
    Endpoint Login Optimal: Mengutamakan penarikan Role dari RAGDB Lokal, 
    Validasi kredensial ke HRIS, dan Auto-Registrasi User Baru ke Lokal.
    """
    npp = request_body.username.strip()
    password_input = request_body.password

    print(f"\n🔐 [LOGIN] Menerima request login untuk NPP: {npp}")

    if not npp or not password_input:
        print("❌ [LOGIN] Gagal: Input NPP atau password kosong.")
        return LoginResponse(status="error", message="NPP dan Password wajib diisi")

    # Hitung MD5 hash untuk dicocokkan ke database HRIS remote lo
    password_md5 = hashlib.md5(password_input.encode()).hexdigest()
    
    user_fullname = None
    user_divisi = None
    current_role = "USER"  # Default role bawaan orok untuk user baru

    try:
        # =========================================================================
        # SKEPTIS 1: LOGIC BYPASS AKUN SPESIAL (TRAINER / ADMIN)
        # =========================================================================
        if str(npp) == "99999" and str(password_input) == "123456":
            print("👑 [LOGIN] Bypass Akun Spesial Terdeteksi. Mengalokasikan kasta TRAINER (Admin).")
            user_fullname = "Learn Data AI"
            user_divisi = "PINDAD"
            current_role = "TRAINER"

        else:
            # =========================================================================
            # SKEPTIS 2: CEK STATUS USER & ROLE DI RAGDB LOKAL DULU
            # =========================================================================
            print(f"💾 [LOGIN] Mengecek kasta role NPP {npp} di RAGDB Lokal...")
            async with get_db() as conn:
                local_user = await conn.fetchrow(
                    "SELECT fullname, divisi, role FROM users WHERE npp = $1", npp
                )
                
                if local_user:
                    current_role = local_user["role"]
                    print(f"🎖️  [LOGIN] User terdaftar di RAGDB Lokal. Role dikunci: {current_role}")
                else:
                    print(f"✨ [LOGIN] User baru (NPP: {npp}) belum terdaftar di RAGDB Lokal.")

            # =========================================================================
            # SKEPTIS 3: VALIDASI PASSWORD & KREDENSIAL KE DB HRIS REMOTE
            # =========================================================================
            print(f"🌐 [LOGIN] Menghubungi database HRIS Remote di 192.168.11.55 untuk verifikasi...")
            async with get_hris_db() as conn:
                user_hris = await conn.fetchrow(
                    """
                    SELECT 
                        mp.nama_lengkap as nama, tu.npp, tu.password, 
                        split_part(ref_unit.unit_path::text, '->'::text, 2) AS divisi
                    FROM master_unit unit
                    JOIN temp_ref_unit ref_unit ON ref_unit.kode_unit = unit.kode_unit
                    LEFT JOIN master_personil mp ON mp.kode_unit = unit.kode_unit
                    LEFT JOIN tabel_user tu ON tu.npp = mp.npp
                    WHERE tu.npp = $1
                    """,
                    npp,
                )

            if not user_hris:
                print(f"❌ [LOGIN] Otentikasi Gagal: NPP {npp} tidak ditemukan di DB HRIS remote.")
                raise HTTPException(status_code=404, detail="NPP tidak terdaftar di HRIS")

            print(f"🔑 [LOGIN] Memverifikasi enkripsi MD5 password untuk NPP: {npp}...")
            if user_hris["password"] != password_md5:
                print(f"❌ [LOGIN] Otentikasi Gagal: Password salah untuk NPP {npp}.")
                raise HTTPException(status_code=401, detail="Password salah")

            # Ambil data nama & divisi hasil balikan dari HRIS resmi
            user_fullname = user_hris["nama"]
            user_divisi = user_hris["divisi"] or "Umum"

        # =========================================================================
        # SKEPTIS 4: ATOMIC TRANSACTION SYNC (SINKRONISASI KE RAGDB LOKAL)
        # =========================================================================
        session_token = str(uuid.uuid4())
        user_ip = request.client.host if request.client else "127.0.0.1"
        u_agent = request.headers.get("user-agent", "FastAPI Client")

        print("📦 [LOGIN] Membuka transaksi aman untuk sinkronisasi data session lokal...")
        async with get_db() as conn:
            async with conn.transaction():
                # 🚀 JALUR AMAN SINKRONISASI USER:
                # Jika user belum ada di lokal, dia otomatis masuk dengan current_role ('USER').
                # Jika user sudah ada (User Lama), role lokalnya tetap dipertahankan (TIDAK AKAN tertimpa jadi 'USER' lagi)
                await conn.execute(
                    """
                    INSERT INTO users (npp, fullname, divisi, role) 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (npp) DO UPDATE SET 
                        fullname = EXCLUDED.fullname, 
                        divisi = EXCLUDED.divisi;
                    """,
                    npp,
                    user_fullname,
                    user_divisi,
                    current_role,
                )
                print("📝 [LOGIN] Sinkronisasi tabel 'users' lokal dikunci aman.")

                # Insert atau refresh token session aktif di tabel session_login sesuai ERD lo bolo
                await conn.execute(
                    """
                    INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity)
                    VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (npp) DO UPDATE SET 
                        session_token = EXCLUDED.session_token, 
                        is_login = TRUE, 
                        last_activity = CURRENT_TIMESTAMP;
                    """,
                    npp,
                    session_token,
                    user_ip,
                )
                print("🔑 [LOGIN] State tabel 'session_login' berhasil direfresh.")

                # Tulis rekam audit ke history_login
                await conn.execute(
                    "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                    npp,
                    user_ip,
                    u_agent,
                )
                print(f"🪵  [AUDIT] Log 'LOGIN' sukses ditulis untuk NPP: {npp}")

        print(f"🟩 [SUCCESS] Login tuntas! {user_fullname} [{current_role}] masuk ke sistem CAKRA AI.")
        return LoginResponse(
            status="success",
            data={
                "token": session_token,
                "npp": npp,
                "fullname": user_fullname,
                "divisi": user_divisi,
                "role": current_role,  # 🔥 Role lokal lo aman dikirim ke Frontend!
            },
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Login Critical Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(request: Request, payload: dict = Body(...)):
    """
    Logout Sektor: Mematikan token session dan mencatat audit trail history.
    """
    token = payload.get("token")
    if not token:
        return {"status": "success", "message": "No token provided"}

    user_ip = request.client.host if request.client else "127.0.0.1"
    print(f"\n🛑 [LOGOUT] Memproses request keluar untuk token: {token[:8]}...")

    try:
        async with get_db() as conn:
            row = await conn.fetchrow(
                "SELECT npp FROM session_login WHERE session_token = $1", token
            )

            if row:
                npp = row["npp"]
                async with conn.transaction():
                    # Nonaktifkan token di session
                    await conn.execute(
                        "UPDATE session_login SET is_login = FALSE, session_token = '' WHERE npp = $1",
                        npp,
                    )
                    # Catat rekam jejak keluar
                    await conn.execute(
                        "INSERT INTO history_login (npp, action, ip_address) VALUES ($1, 'LOGOUT', $2)",
                        npp,
                        user_ip,
                    )
                print(f"✨ [LOGOUT] Clean shutdown session untuk NPP: {npp}. Jejak audit aman, bolo!")
                return {"status": "success", "message": "Logged out successfully"}

            print("⚠️  [LOGOUT] Sesi token sudah tidak aktif sebelumnya.")
            return {"status": "success", "message": "Session already inactive"}

    except Exception as e:
        logger.error(f"❌ Logout Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error during logout")