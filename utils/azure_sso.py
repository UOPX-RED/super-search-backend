import jwt
from jwt import PyJWKClient
import os
import json
import base64
import time
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Callable, Optional
from dotenv import load_dotenv
from utils.get_secrets import get_secret

if os.getenv('ENVIRONMENT') == 'LOCAL':
    load_dotenv(".env-local")
    print("Loaded environment variables from .env-local")
else:
    load_dotenv()

secret_name = "supersearch/prod/azureClientSecrets"
result = get_secret(secret_name)
if result is not None:
    #print(f"Retrieved secret: {result}")
    print(f"AZURE_CLIENT_ID: {result['AZURE_CLIENT_ID']}")
    TENANT_ID = result['TENANT_ID']
    CLIENT_ID = result['AZURE_CLIENT_ID']
    CLIENT_SECRET = result["AZURE_CLIENT_SECRET"]
else:
    print("Failed to retrieve secret from secrets manager.")

REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL")
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"


def fix_padding(b64_string):
    return b64_string + "=" * (-len(b64_string) % 4)


def azure_token_middleware(token):
    try:
        token_parts = token.split(".")
        if len(token_parts) != 3:
            return False

        payload = token_parts[1]
        fixed_padding = fix_padding(payload)
        decoded_bytes = base64.b64decode(fixed_padding)
        decoded_str = decoded_bytes.decode("utf-8")

        token_data = json.loads(decoded_str)

        current_time = time.time()
        if token_data.get("exp", 0) < current_time:
            return False

        if token_data.get("aud") != CLIENT_ID:
            return False

        expected_issuer = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
        if token_data.get("iss") != expected_issuer:
            return False

        return True
    except Exception:
        return False


def validate_token(token: str) -> bool:
    try:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        jwks_client = PyJWKClient(JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        decoded_token = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
        )

        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False
    except Exception:
        return False


def get_token_from_request(request: Request) -> Optional[str]:
    azure_token = request.headers.get("X-Azure-Token")
    if azure_token:
        return azure_token

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]

    token = request.cookies.get("auth_token")
    if token:
        return token

    return None


def decode_token(token: str) -> Optional[dict]:
    try:
        token_parts = token.split(".")
        if len(token_parts) != 3:
            return None

        payload = token_parts[1]
        fixed_padding = fix_padding(payload)
        decoded_bytes = base64.b64decode(fixed_padding)
        decoded_str = decoded_bytes.decode("utf-8")

        return json.loads(decoded_str)
    except Exception:
        return None


async def auth_middleware(request: Request, call_next, open_paths=None):
    if open_paths is None:
        open_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/auth/login",
            "/auth/init"
        ]

    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path in open_paths:
        return await call_next(request)

    token = get_token_from_request(request)
    if not token:
        return JSONResponse(
            content={"message": "Unauthorized - Authentication token required"},
            status_code=401
        )

    is_valid = (
        azure_token_middleware(token) if request.headers.get("X-Azure-Token")
        else validate_token(token)
    )

    if not is_valid:
        return JSONResponse(
            content={"message": "Unauthorized - Invalid authentication token"},
            status_code=401
        )

    return await call_next(request)


async def init_auth():
    auth_url = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code%20id_token"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_mode=form_post"
        f"&scope=openid%20profile%20email%20offline_access"
        f"&nonce={int(time.time())}"
    )

    return RedirectResponse(auth_url)


def get_user_info_from_token(token: str) -> Optional[dict]:
    try:
        token_parts = token.split(".")
        if len(token_parts) != 3:
            return None

        payload = token_parts[1]
        fixed_padding = fix_padding(payload)
        decoded_bytes = base64.b64decode(fixed_padding)
        decoded_str = decoded_bytes.decode("utf-8")

        token_data = json.loads(decoded_str)

        user_info = {
            "user_id": token_data.get("oid", ""),
            "name": token_data.get("name", ""),
            "email": token_data.get("email", token_data.get("preferred_username", "")),
            "tenant_id": token_data.get("tid", ""),
        }

        return user_info
    except Exception:
        return None


async def login(request: Request):
    try:
        form_data = await request.form()
        form_dict = dict(form_data)

        id_token = form_dict.get("id_token")
        if not id_token:
            return JSONResponse(
                content={"message": "Authentication failed - No token"},
                status_code=401
            )

        if not azure_token_middleware(id_token):
            return JSONResponse(
                content={"message": "Authentication failed - Invalid token"},
                status_code=401
            )

        return RedirectResponse(f"{FRONTEND_URL}?token={id_token}", status_code=302)

    except Exception as e:
        return JSONResponse(
            content={"message": f"Authentication error: {str(e)}"},
            status_code=500
        )
