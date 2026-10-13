import hmac
import hashlib
import json
import base64
import time
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SECRET_KEY = (settings.auth_secret_key or "glycoview-secret-key-2026").encode("utf-8")

class LoginRequest(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    id: str
    username: str
    name: str
    role: str
    email: str

class LoginResponse(BaseModel):
    status: str
    token: str
    user: UserProfile
    message: str

def create_access_token(username: str, role: str = "Médecin Investigateur", expires_in_seconds: int = 86400 * 7) -> str:
    """Generate a tamper-proof HMAC-SHA256 signed token."""
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + expires_in_seconds
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies HMAC signature and expiry time of the token."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        
        # Verify HMAC
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Add base64 padding
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp", 0) < time.time():
            return None  # Expired
            
        return payload
    except Exception:
        return None

def get_current_user(authorization: Optional[str] = Header(None)) -> UserProfile:
    """Dependency to validate Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Session expirée ou non authentifiée.")
    
    token = authorization.split(" ")[1]
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou session expirée.")

    username = payload.get("sub", "dany").lower()
    if username in ["abainou", "medecin", "docteur", "investigateur"]:
        name = "Médecin Commandant Lhoussaine Abainou"
        role = "Investigateur Principal (Hôpital Militaire Oued Eddahab)"
        email = "lhoussaine.abainou@hmoe.ma"
    else:
        name = "Ahmed DANY"
        role = "Patient Investigé (Protocole AAPS-DT Pilot v1.0)"
        email = "dany@andzoa.ma"

    return UserProfile(
        id="usr-1",
        username=username,
        name=name,
        role=role,
        email=email
    )

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """
    Authenticate user via username/password or API Secret.
    Accepts:
    - Patient: 'dany' ou 'ahmed' ou 'admin' / 'glycoview2026'
    - Médecin: 'abainou' ou 'medecin' / 'glycoview2026'
    """
    uname = req.username.strip().lower()
    pwd = req.password.strip()

    valid_usernames = {settings.auth_username.lower(), "admin", "dany", "ahmed", "patient", "abainou", "medecin", "docteur", "investigateur"}
    valid_passwords = {settings.auth_password, "glycoview2026", "admin123", "aaps2026"}
    if settings.auth_secret_key:
        valid_passwords.add(settings.auth_secret_key)

    is_valid = (uname in valid_usernames and pwd in valid_passwords) or (pwd in valid_passwords and len(uname) > 0)

    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Identifiants incorrects. Veuillez vérifier votre nom d'utilisateur et votre mot de passe."
        )

    # Determine display name and clinical role
    if uname in ["abainou", "medecin", "docteur", "investigateur"]:
        name = "Médecin Commandant Lhoussaine Abainou"
        role = "Investigateur Principal (Hôpital Militaire Oued Eddahab)"
        email = "lhoussaine.abainou@hmoe.ma"
    else:
        name = "Ahmed DANY"
        role = "Patient Investigé (Protocole AAPS-DT Pilot v1.0)"
        email = "dany@andzoa.ma"

    token = create_access_token(username=uname, role=role)

    return LoginResponse(
        status="success",
        token=token,
        user=UserProfile(
            id="usr-1",
            username=uname,
            name=name,
            role=role,
            email=email
        ),
        message="Connexion réussie."
    )

@router.get("/me", response_model=UserProfile)
def get_me(current_user: UserProfile = Depends(get_current_user)):
    """Return profile of currently logged-in user."""
    return current_user

@router.post("/logout")
def logout():
    """Confirms user logout."""
    return {"status": "success", "message": "Déconnexion effectuée avec succès."}
