from fastapi import APIRouter, HTTPException, Request, Query, Body, status
from pydantic import BaseModel
import hashlib
import uuid
import logging
from typing import Optional
import bcrypt

# Hubungkan ke pool database baru kita secara aman
from backend.app.core.database import get_db, get_hris_db
from backend.app.core.config import settings

router = APIRouter()
logger = logging.getLogger("CAKRA_AUTH")

# --- PYDANTIC SCHEMAS ---
from backend.app.api.schemas import LoginRequest, LoginResponse, ExtendSessionRequest


# --- ENDPOINTS ---

@router.get("/verify-session", response_model=LoginResponse)
async def verify_session(token: str = Query(None)):
    """
    Mengecek status validasi token di localStorage secara asinkronus.
    """
    if not token:
        logger.warning("👤 [GUARD] Verifikasi gagal: Request datang tanpa token.")
        raise HTTPException(status_code=401, detail="Token missing")

    logger.info(f"🔍 [AUTH] Memverifikasi session token: {token[:8]}...")
    try:
        async with get_db() as conn:
            query = """
                SELECT u.npp, u.fullname, u.divisi, u.role, s.expires_at
                FROM session_login s
                JOIN users u ON s.npp = u.npp
                WHERE s.session_token = $1 AND s.is_login = TRUE AND s.expires_at > NOW()
            """
            user = await conn.fetchrow(query, token)

            if user:
                logger.info(f"🟩 [AUTH] Session VALID untuk User: {user['fullname']} [{user['role']}]")
                
                # Update aktivitas terakhir pegawai
                await conn.execute(
                    "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
                    token,
                )
                logger.info(f"🕒 [AUTH] last_activity updated untuk NPP: {user['npp']}")

                return LoginResponse(
                    status="success",
                    data={
                        "npp": user["npp"],
                        "username": user["npp"],
                        "fullname": user["fullname"],
                        "divisi": user["divisi"],
                        "role": user["role"],
                        "expires_at": user["expires_at"].isoformat() if user["expires_at"] else None
                    }
                )
            else:
                logger.warning(f"⚠️ [AUTH] Session INVALID atau sudah kedaluwarsa untuk token: {token[:8]}...")
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

    logger.info(f"\n🔐 [LOGIN] Menerima request login untuk NPP: {npp}")

    if not npp or not password_input:
        logger.warning("❌ [LOGIN] Gagal: Input NPP atau password kosong.")
        return LoginResponse(status="error", message="NPP dan Password wajib diisi")

    # Hitung MD5 hash untuk dicocokkan ke database HRIS remote lo
    password_md5 = hashlib.md5(password_input.encode()).hexdigest()
    
    user_fullname = None
    user_divisi = None
    current_role = "USER"  # Default role bawaan orok untuk user baru

    try:
        # =========================================================================
        # SKEPTIS 1: LOGIC BYPASS AKUN SPESIAL (TRAINER / ADMIN) — FROM ENV VARS
        # =========================================================================
        bypass_enabled = settings.BYPASS_ACCOUNT_ENABLED
        bypass_npp = settings.BYPASS_ACCOUNT_NPP or "99999"
        bypass_password_hash = settings.BYPASS_ACCOUNT_PASSWORD_HASH or ""
        
        if bypass_enabled and str(npp) == bypass_npp:
            # Validasi password menggunakan bcrypt (lebih aman dari MD5)
            if bypass_password_hash and bcrypt.checkpw(password_input.encode(), bypass_password_hash.encode()):
                logger.warning(f"👑 [LOGIN] Bypass Account Spesial (NPP: {bypass_npp}) berhasil login. Mengalokasikan kasta TRAINER.")
                user_fullname = "Admin CAKRA"
                user_divisi = "System Admin"
                current_role = "TRAINER"
            else:
                logger.warning(f"⚠️ [LOGIN] Bypass account attempt dengan password salah untuk NPP: {npp}")
                raise HTTPException(status_code=401, detail="Password salah")
        else:
            # =========================================================================
            # SKEPTIS 2: CEK STATUS USER & ROLE DI RAGDB LOKAL DULU
            # =========================================================================
            logger.info(f"💾 [LOGIN] Mengecek kasta role NPP {npp} di RAGDB Lokal...")
            async with get_db() as conn:
                local_user = await conn.fetchrow(
                    "SELECT fullname, divisi, role FROM users WHERE npp = $1", npp
                )
                
                if local_user:
                    current_role = local_user["role"]
                    logger.info(f"🎖️  [LOGIN] User terdaftar di RAGDB Lokal. Role dikunci: {current_role}")
                else:
                    logger.info(f"✨ [LOGIN] User baru (NPP: {npp}) belum terdaftar di RAGDB Lokal.")

            # =========================================================================
            # SKEPTIS 3: VALIDASI PASSWORD & KREDENSIAL KE DB HRIS REMOTE
            # =========================================================================
            logger.info(f"🌐 [LOGIN] Menghubungi database HRIS Remote di 192.168.11.55 untuk verifikasi...")
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
                logger.error(f"❌ [LOGIN] Otentikasi Gagal: NPP {npp} tidak ditemukan di DB HRIS remote.")
                raise HTTPException(status_code=404, detail="NPP tidak terdaftar di HRIS")

            logger.info(f"🔑 [LOGIN] Memverifikasi enkripsi MD5 password untuk NPP: {npp}...")
            if user_hris["password"] != password_md5:
                logger.error(f"❌ [LOGIN] Otentikasi Gagal: Password salah untuk NPP {npp}.")
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

        logger.info("📦 [LOGIN] Membuka transaksi aman untuk sinkronisasi data session lokal...")
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
                logger.info("📝 [LOGIN] Sinkronisasi tabel 'users' lokal dikunci aman.")

                # Bersihkan sesi lama yang sudah kadaluarsa untuk NPP ini
                await conn.execute(
                    "DELETE FROM session_login WHERE npp = $1 AND expires_at < NOW()",
                    npp
                )

                # Insert session token baru (Multiple device support)
                expires_at = await conn.fetchval(
                    """
                    INSERT INTO session_login (npp, session_token, ip_address, is_login, last_activity, expires_at)
                    VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP, NOW() + INTERVAL '1 month')
                    RETURNING expires_at;
                    """,
                    npp,
                    session_token,
                    user_ip,
                )
                logger.info("🔑 [LOGIN] State tabel 'session_login' berhasil direfresh.")

                # Tulis rekam audit ke history_login
                await conn.execute(
                    "INSERT INTO history_login (npp, action, ip_address, user_agent) VALUES ($1, 'LOGIN', $2, $3)",
                    npp,
                    user_ip,
                    u_agent,
                )
                logger.info(f"🪵  [AUDIT] Log 'LOGIN' sukses ditulis untuk NPP: {npp}")

        guest_session_id = request_body.guest_session_id
        if guest_session_id:
            try:
                async with get_db() as main_conn:
                    res = await main_conn.execute(
                        """
                        UPDATE chat_sessions 
                        SET npp = $1 
                        WHERE session_uuid = $2 AND (npp = 'GUEST' OR npp IS NULL)
                        """,
                        npp, guest_session_id
                    )
                    if res != "UPDATE 0":
                        logger.info(f"🔄 [MIGRATION] Sesi GUEST {guest_session_id} resmi menjadi milik NPP: {npp}")
            except Exception as e:
                logger.error(f"Gagal migrasi sesi GUEST: {e}")

        logger.info(f"🟩 [SUCCESS] Login tuntas! {user_fullname} [{current_role}] masuk ke sistem CAKRA AI.")
        return LoginResponse(
            status="success",
            data={
                "token": session_token,
                "npp": npp,
                "fullname": user_fullname,
                "divisi": user_divisi,
                "role": current_role,
                "expires_at": expires_at.isoformat() if expires_at else None,
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
    logger.info(f"\n🛑 [LOGOUT] Memproses request keluar untuk token: {token[:8]}...")

    try:
        async with get_db() as conn:
            row = await conn.fetchrow(
                "SELECT npp FROM session_login WHERE session_token = $1", token
            )

            if row:
                npp = row["npp"]
                async with conn.transaction():
                    # Nonaktifkan token di session secara spesifik untuk perangkat ini
                    await conn.execute(
                        "UPDATE session_login SET is_login = FALSE WHERE session_token = $1",
                        token,
                    )
                    # Catat rekam jejak keluar
                    await conn.execute(
                        "INSERT INTO history_login (npp, action, ip_address) VALUES ($1, 'LOGOUT', $2)",
                        npp,
                        user_ip,
                    )
                logger.info(f"[AUTH_LOGOUT_SUCCESS] Clean shutdown session for NPP: {npp}. Audit trail secured.")
                return {"status": "success", "message": "Logged out successfully"}

            logger.warning("⚠️  [LOGOUT] Sesi token sudah tidak aktif sebelumnya.")
            return {"status": "success", "message": "Session already inactive"}

    except Exception as e:
        logger.error(f"[AUTH_LOGOUT_ERROR] Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error during logout")

@router.post("/extend-session")
async def extend_session(request: Request, body: ExtendSessionRequest = Body(...)):
    """
    Memperpanjang masa aktif session token user yang sedang login.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("👤 [GUARD] Perpanjangan sesi gagal: Token tidak disertakan atau format salah.")
        raise HTTPException(status_code=401, detail="Token missing or invalid")
    
    token = auth_header.split(" ")[1]
    
    from backend.app.utils.token_expiry import extend_session_expiry_by_token
    new_expiry = await extend_session_expiry_by_token(token, body.hours_to_add)
    
    if not new_expiry:
        logger.warning("⚠️ [AUTH] Gagal memperpanjang sesi. Token tidak valid atau tidak aktif.")
        raise HTTPException(status_code=401, detail="Session invalid or expired")
        
    logger.info(f"🕒 [AUTH] Sesi diperpanjang. Expiry baru: {new_expiry.isoformat()}")
    return {
        "status": "success",
        "expires_at": new_expiry.isoformat(),
        "message": "Session extended successfully"
    }