import jwt
from jwt import PyJWKClient
import os
import json
import base64
import time


def fix_padding(b64_string):
    return b64_string + "=" * (-len(b64_string) % 4)


def azure_token_middleware(token):
    try:
        tokenData = token.split(".")[1]
        fixedPadding = fix_padding(tokenData)
        decodedBytes = base64.b64decode(fixedPadding)
        decodedStr = decodedBytes.decode("utf-8")

        tokenDict = json.loads(decodedStr)

        timestamp = time.time()

        if tokenDict["exp"] < timestamp:
            return False
        else:
            return True
    except jwt.ExpiredSignatureError:
        return False


def token_middleware(token):
    return True
    # try:
    #     strippedToken = token.split(" ")[1]
    #     jwkURL = os.environ.get("JWK_URL")
    #     optional_custom_headers = {"User-agent": "custom-user-agent"}
    #     jwks_client = PyJWKClient(jwkURL, headers=optional_custom_headers)
    #     signing_key = jwks_client.get_signing_key_from_jwt(strippedToken)
    #     jwt.decode(
    #         strippedToken,
    #         signing_key,
    #         algorithms=["RS256"],
    #     )

    #     # Decode the JWT token
    #     decoded_token = jwt.decode(
    #         strippedToken,
    #         signing_key.key,  # Use the key attribute of signing_key
    #         algorithms=["RS256"],
    #     )

    #     required_scope = "api:knowledge:v1:complibot"

    #     # Check if 'scope' exists in the token
    #     token_scopes = decoded_token.get("scope", "")

    #     # Split the token's scopes into a list (space-separated)
    #     token_scopes_list = token_scopes.split()

    #     # Check if the required scope is partially present in any of the scopes
    #     if any(required_scope in scope for scope in token_scopes_list):
    #         return True
    #     else:
    #         return False  # Valid token, but the required scope is missing

    # except jwt.ExpiredSignatureError:
    #     return False
    # except jwt.InvalidTokenError:
    #     return False
