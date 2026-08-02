from typing import Optional

from fastapi import HTTPException


def validate_upload_access(user: dict, client_id: Optional[int]) -> int:
    """Validate whether a user is allowed to upload documents to the target client."""
    if user["role"] not in ["admin", "superadmin", "admin_client"]:
        raise HTTPException(status_code=403, detail="Anda tidak diizinkan mengunggah dokumen.")

    if client_id is None:
        if user["role"] == "admin_client":
            if user.get("client_id") is None:
                raise HTTPException(status_code=400, detail="Admin client belum memiliki client yang ditetapkan.")
            return user["client_id"]
        raise HTTPException(status_code=400, detail="client_id wajib diisi.")

    if user["role"] == "admin_client" and user.get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Anda hanya diizinkan mengunggah dokumen ke Client Anda sendiri.")

    return client_id
