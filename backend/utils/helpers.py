import hashlib
from werkzeug.utils import secure_filename
from ..core.config import ALLOWED_EXTENSIONS


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def hash_password(password: str) -> str:
    """Hash password using MD5"""
    return hashlib.md5(password.encode()).hexdigest()


def secure_filename_check(filename: str) -> str:
    """Secure filename using werkzeug"""
    return secure_filename(filename)