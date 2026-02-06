import boto3
import json
import logging
from typing import Any, Dict, Optional, BinaryIO
from botocore.exceptions import ClientError
from brokerage_parser.config import settings
from brokerage_parser.storage.base import StorageBackend

logger = logging.getLogger(__name__)

class S3Storage(StorageBackend):
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.AWS_ENDPOINT_URL
        )
        self.bucket = settings.S3_BUCKET

    def store_document(self, file_obj: BinaryIO, filename: str, content_type: str = "application/pdf") -> str:
        key = f"documents/{filename}"
        try:
            # Set object to expire in 7 days via lifecycle policy or tagging
            # Or assume bucket lifecycle policy handles it.
            # We can also add Tagging='lifecycle=temp' if configured.
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type}
            )
            return key
        except ClientError as e:
            logger.error(f"S3 Upload failed: {e}")
            raise e

    def get_document(self, doc_id: str) -> Optional[BinaryIO]:
        # doc_id is the S3 key
        # TODO: Implement if needed for worker (worker might just download to temp file)
        # But usually we generate presigned URL or use boto3 to download_file
        raise NotImplementedError("Use get_document_url or direct boto3 download")

    def get_document_url(self, doc_id: str, expiration: int = 900) -> Optional[str]:
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': doc_id},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"S3 Presigned URL generation failed: {e}")
            return None

    def store_report(self, doc_id: str, report_data: Dict[str, Any]) -> str:
        # doc_id is the document key e.g. documents/xyz.pdf
        # report key: reports/xyz.json
        # Extract filename from doc_id or use hash
        base_name = doc_id.split("/")[-1]
        report_key = f"reports/{base_name}.json"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=report_key,
                Body=json.dumps(report_data, default=str),
                ContentType="application/json"
            )
            return report_key
        except ClientError as e:
            logger.error(f"S3 Report Upload failed: {e}")
            raise e

    def get_report(self, doc_id: str) -> Optional[Dict[str, Any]]:
        # doc_id passed here might be the REPORT key if the caller knows it,
        # OR the document key.
        # This ambiguity needs resolving. The API usually tracks `result_s3_key`.
        # Taking `doc_id` as the key to fetch.
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=doc_id)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except ClientError as e:
            logger.warning(f"S3 Report Fetch failed or Not Found: {e}")
            return None
