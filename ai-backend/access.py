from typing import Optional

from fastapi import HTTPException


def validate_upload_access(user: dict, client_id: Optional[int]) -> int:
    """Validate whether a user is allowed to upload documents to the target client."""
    if user["role"] not in ["admin", "admin_client"]:
        raise HTTPException(status_code=403, detail="Anda tidak diizinkan mengunggah dokumen.")

    user_cid = user.get("client_id")

    if user["role"] == "admin_client":
        if user_cid is None:
            raise HTTPException(
                status_code=403,
                detail="Akses ditolak. Akun Admin Client Anda belum memiliki Client ID yang ditugaskan."
            )

        try:
            return int(user_cid)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Client ID milik user tidak valid.")

    # Untuk role superadmin / admin (global):
    if client_id is None:
        raise HTTPException(status_code=400, detail="client_id wajib diisi untuk Admin / Superadmin.")

    try:
        return int(client_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="client_id yang dikirim tidak valid.")


