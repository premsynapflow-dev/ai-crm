from fastapi import APIRouter, Depends

from app.auth import get_current_client, get_current_client_user, serialize_client_user
from app.db.models import Client, ClientUser

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/me")
def get_current_user(
    user: ClientUser = Depends(get_current_client_user),
    client: Client = Depends(get_current_client),
):
    return serialize_client_user(user, client)
