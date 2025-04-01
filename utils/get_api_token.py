import os
import base64
import requests
from dotenv import load_dotenv
import time
from utils.get_secrets import get_secret

# Load environment variables from .env file
load_dotenv()

#read secret from secret manager
secret_name = "supersearch/prod/apiClientSecrets"
result = get_secret(secret_name)
if result is not None:
    #print(f"Retrieved secret: {result}")
    client_id = result['API_CLIENT_ID']
    client_secret = result['API_CLIENT_SECRET']
    print(f"API Key:  {client_id[:5]}")
    print(f"API Secret:  {client_secret[:5]}")
else:
    print("Failed to retrieve secret from secrets manager.")

# Retrieve Cognito URL, client ID, and client secret from environment variables
cognito_url = os.getenv('COGNITO_URL')
if not cognito_url:
    raise ValueError("Environment variable cognito_url is not set.")

# Cache to store the token and its expiration time
token_cache = {
    'token': None,
    'expiration': 0
}

def get_cognito_token():
    global token_cache
    
    # Check if the token is cached and not expired
    if token_cache['token'] and token_cache['expiration'] > time.time():
        return token_cache['token']
    
    # If the token is expired or not cached, fetch a new one
    try:
        # Encode client ID and client secret in base64 for Basic auth
        auth_str = f"{client_id}:{client_secret}"
        auth_bytes = auth_str.encode('utf-8')
        auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        # Set headers for the POST request
        headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Set payload for the POST request
        payload = {
            'grant_type': 'client_credentials'
        }
        
        # Make the POST request to fetch the token
        response = requests.post(cognito_url, headers=headers, data=payload)
        
        # Check if the request was successful
        if response.status_code == 200:
            response_data = response.json()
            
            # Extract the token and its expiration time from the response
            id_token = response_data['access_token']
            print(f"Cognito Token retrieved: {id_token[:5]}")
            expires_in = response_data['expires_in']
            print("expires_in: ",expires_in)
            
            # Cache the token and its expiration time
            token_cache['token'] = id_token
            token_cache['expiration'] = time.time() + expires_in
            
            return id_token
        
        else:
            print(f"Failed to fetch token: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def refresh_token():
    global token_cache
    
    # Force refresh the token by setting expiration to 0
    token_cache['expiration'] = 0
    
    return get_cognito_token()

# # Example usage
# token = get_cognito_token()
# print(f"Cognito Token: {token}")

# # Automatically refresh the token if needed
# if not token or token_cache['expiration'] <= time.time():
#     print("Refreshing token...")
#     token = refresh_token()
#     print(f"Refreshed Cognito Token: {token}")