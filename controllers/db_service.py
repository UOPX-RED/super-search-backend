# db_service.py
import pymongo
import os
from models import AnalysisResult
from typing import List, Optional


class DocumentDBService:
    def __init__(self):
        # Connection string for AWS DocumentDB
        connection_string = os.environ.get('DOCUMENT_DB_CONNECTION_STRING')

        # Initialize MongoDB client
        self.client = pymongo.MongoClient(connection_string, connect=False)
        self.db = self.client[os.environ.get('MONGO_DB', 'text_analysis')]
        self.collection = self.db[os.environ.get('MONGODB_COLLECTION', 'analysis_results')]

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