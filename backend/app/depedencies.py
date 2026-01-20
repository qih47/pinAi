from fastapi import HTTPException, Header, Depends
from typing import Optional
from .database import get_db


async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify session token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token missing or invalid")

    token = authorization[7:]  # Remove "Bearer " prefix

    async with get_db() as conn:
        user = await conn.fetchrow(
            """
            SELECT u.npp, u.fullname, u.divisi 
            FROM session_login s
            JOIN users u ON s.npp = u.npp
            WHERE s.session_token = $1 AND s.is_login = TRUE
        """,
            token,
        )

        if not user:
            raise HTTPException(status_code=401, detail="Session expired or invalid")

        # Update last activity
        await conn.execute(
            "UPDATE session_login SET last_activity = CURRENT_TIMESTAMP WHERE session_token = $1",
            token,
        )

        return {
            "npp": user["npp"],
            "fullname": user["fullname"],
            "divisi": user["divisi"],
            "token": token,
        }


async def get_current_user(user_data: dict = Depends(verify_token)):
    """Get current user from verified token"""
    return user_data
