from itsdangerous import BadSignature, URLSafeSerializer

from app.config import get_settings

settings = get_settings()
serializer = URLSafeSerializer(settings.secret_key)


def create_session(user_id: str) -> str:
    return serializer.dumps({"user_id": user_id})


def decode_session(token: str) -> dict:
    return serializer.loads(token)


__all__ = ["BadSignature", "create_session", "decode_session"]
