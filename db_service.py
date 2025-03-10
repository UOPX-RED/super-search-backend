# db_service.py
import pymongo
import os
from models import AnalysisResult
import json
from typing import List, Optional
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import os
from dotenv import load_dotenv

if os.environ.get("ENVIRONMENT") == "LOCAL":
    load_dotenv('.env-local')

class DocumentDBService:
    def __init__(self):
        # Connection string for AWS DocumentDB
        connection_string = os.environ.get('DOCUMENT_DB_CONNECTION_STRING')
        if connection_string is None:
            raise ValueError("Invalid connection_string: received None")
        print(f"connection_string: {connection_string}")

        # Retrieve the password from AWS Secrets Manager
        password = self.get_secret()

        if not password:
            raise ValueError("Failed to retrieve password from AWS Secrets Manager");
        print(f"connection_string: {connection_string}")
        connection_string = connection_string.replace('<password>', password)
        print(f"connection_string: {connection_string}")

        # Initialize MongoDB client
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client[os.environ.get('DB_NAME', 'text_analysis')]
        self.collection = self.db[os.environ.get('COLLECTION_NAME', 'analysis_results')]

    def get_secret(self):

        secret_name = "rds!cluster-e9d0c63e-4a8c-4041-8b58-da5f42800f2e"
        region_name = "us-east-1"

        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )

        try:
            get_secret_value_response = client.get_secret_value(
                SecretId=secret_name
            )
            #print(get_secret_value_response);

        except ClientError as e:
            # Log the exception
            print(f"An error occurred: {e}")
            # Optionally, handle specific exceptions or re-raise if necessary
            raise

        if 'SecretString' in get_secret_value_response:
            secret_str = get_secret_value_response['SecretString']
            secret_dict = json.loads(secret_str)
            password = secret_dict.get('password')
            #print("password: "+password);
            return password;

    def save_result(self, result: AnalysisResult) -> str:
        """Save analysis result to DocumentDB and return its ID"""
        result_dict = result.model_dump()

        # Handle datetime serialization
        result_dict['created_at'] = result.created_at

        # Insert document
        insert_result = self.collection.insert_one(result_dict)
        return str(insert_result.inserted_id)

    def get_results_by_source_id(self, source_id: str) -> List[AnalysisResult]:
        """Retrieve analysis results by source ID"""
        cursor = self.collection.find({"source_id": source_id})
        results = []

        for doc in cursor:
            doc['id'] = str(doc.pop('_id'))
            results.append(AnalysisResult(**doc))

        return results

    def get_flagged_results(self, limit: int = 100) -> List[AnalysisResult]:
        """Retrieve results that have flags"""
        cursor = self.collection.find({"has_flags": True}).limit(limit)
        results = []

        for doc in cursor:
            doc['id'] = str(doc.pop('_id'))
            results.append(AnalysisResult(**doc))

        return results

    def get_result_by_request_id(self, request_id: str) -> Optional[AnalysisResult]:
        """Retrieve analysis result by request ID"""
        doc = self.collection.find_one({"request_id": request_id})

        if not doc:
            return None

        doc['id'] = str(doc.pop('_id'))
        return AnalysisResult(**doc)