import boto3
import json

region_name = "us-east-1"

def get_secret(secret_name):
    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        # Retrieve the secret value
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        print(f"Error retrieving secret: {e}")
        return None

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

# def test_get_secret():
#     # Test retrieving a valid secret
#     secret_name = "supersearch/prod/apiClientSecrets"
#     result = get_secret(secret_name)
#     if result is not None:
#         print(f"Retrieved secret: {result}")
#         print(f"API Key: {result['api_key']}")

#     # Test with invalid secret name
#     # invalid_secret = "invalid-secret"
#     # result = get_secret(invalid_secret)
#     # print(f"Result with invalid secret: {result}")

# if __name__ == "__main__":
#     test_get_secret()