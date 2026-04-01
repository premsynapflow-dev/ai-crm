import base64
import hashlib

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]

from app.config import get_settings

settings = get_settings()


def _fernet() -> Fernet:
    if Fernet is None:  # pragma: no cover
        raise RuntimeError("cryptography is required for channel credential encryption")

    secret_material = (settings.channel_crypto_key or settings.secret_key).encode("utf-8")
    digest = hashlib.sha256(secret_material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored channel credential") from exc
