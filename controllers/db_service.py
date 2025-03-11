# db_service.py
import pymongo
import os
from models import AnalysisResult
from typing import List, Optional
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal


def getRealDecimal(obj):

    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: getRealDecimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [getRealDecimal(i) for i in obj]
    return obj


class DynamoDBService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = self.dynamodb.Table('super-search-analysis_results')

    def save_result(self, result: AnalysisResult) -> str:
        """Save analysis result to DynamoDB and return its ID"""
        result_dict = result.model_dump()
        result_dict['created_at'] = result.created_at.isoformat()


        result_dict = getRealDecimal(result_dict)

        # Insert document
        insert_result = self.table.put_item(
            Item=result_dict
        )
        return result_dict['id']

    def get_results_by_source_id(self, source_id: str) -> List[AnalysisResult]:
        """Retrieve analysis results by source ID"""
        response = self.table.query(
            IndexName='source_id-index',  
            KeyConditionExpression=Key('source_id').eq(source_id)
        )
        items = response.get('Items', [])
        results = [AnalysisResult(**item) for item in items]
        return results

    def get_flagged_results(self, limit: int = 100) -> List[AnalysisResult]:
        """Retrieve results that have flags"""
        response = self.table.query(
            IndexName='has_flags-index',
            KeyConditionExpression=Key('has_flags').eq("true")
        )
        items = response.get('Items', [])
        results = [AnalysisResult(**item) for item in items]
        return results

    def get_result_by_request_id(self, request_id: str) -> Optional[AnalysisResult]:
        """Retrieve analysis result by request ID"""
        response = self.table.query(
            IndexName='request_id-index',
            KeyConditionExpression=Key('request_id').eq(request_id)
        )
        items = response.get('Items', [])
        if items:
            item = AnalysisResult(**items[0])
            return item
        return []