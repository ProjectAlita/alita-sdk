import json
import logging
import requests
from typing import Any, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger("carrier_sdk")


class CarrierAPIError(Exception):
    """Base exception for Carrier SDK errors."""
    pass


class CarrierCredentials(BaseModel):
    url: str
    token: str
    organization: str
    project_id: str


class CarrierClient(BaseModel):
    credentials: CarrierCredentials
    session: requests.Session = Field(default_factory=requests.Session, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context):
        headers = {
            'Authorization': f'Bearer {self.credentials.token}',
            'Content-Type': 'application/json',
            'X-Organization': self.credentials.organization
        }
        self.session.headers.update(headers)

    def request(self, method: str, endpoint: str, **kwargs) -> Any:
        full_url = f"{self.credentials.url.rstrip('/')}/{endpoint.lstrip('/')}"
        response = self.session.request(method, full_url, **kwargs)
        try:
            response.raise_for_status()  # This will raise for 4xx/5xx
        except requests.HTTPError as http_err:
            # Log or parse potential HTML in response.text
            logger.error(f"HTTP {response.status_code} error: {response.text[:500]}")  # short snippet
            raise CarrierAPIError(f"Request to {full_url} failed with status {response.status_code}")

        # If the response is JSON, parse it. If it’s HTML or something else, handle gracefully
        try:
            return response.json()
        except json.JSONDecodeError:
            # Possibly HTML error or unexpected format
            logger.error(f"Response was not valid JSON. Body:\n{response.text[:500]}")
            raise CarrierAPIError("Server returned non-JSON response")

    def create_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = f"api/v1/issues/issues/{self.credentials.project_id}"
        logger.info(f"ENDPOINT: {endpoint}")
        response = self.request('post', endpoint, json=ticket_data)

        # Optionally check for successful creation:
        # Some APIs return status=201, or an `item` field in JSON
        if not response or "item" not in response:
            # We expected "item" in the response
            logger.warning(f"Unexpected response: {response}")
            raise CarrierAPIError("Carrier did not return a valid ticket response")

        # Return the entire JSON so the tool can parse "id", "hash_id", or others
        return response

    def fetch_tickets(self, board_id: str) -> List[Dict[str, Any]]:
        endpoint = f"api/v1/issues/issues/{self.credentials.project_id}?board_id={board_id}&limit=100"
        return self.request('get', endpoint).get("rows", [])

    def get_reports_list(self) -> List[Dict[str, Any]]:
        endpoint = f"api/v1/backend_performance/reports/{self.credentials.project_id}"
        return self.request('get', endpoint).get("rows", [])

    def get_tests_list(self) -> List[Dict[str, Any]]:
        endpoint = f"api/v1/backend_performance/tests/{self.credentials.project_id}"
        return self.request('get', endpoint).get("rows", [])

    def run_test(self, test_id: str, json_body):
        endpoint = f"api/v1/backend_performance/test/{self.credentials.project_id}/{test_id}"
        return self.request('post', endpoint, json=json_body).get("result_id", "")

    def get_engagements_list(self) -> List[Dict[str, Any]]:
        endpoint = f"api/v1/engagements/engagements/{self.credentials.project_id}"
        return self.request('get', endpoint).get("items", [])

    def download_and_unzip_reports(self, file_name: str, bucket: str, extract_to: str = "/tmp") -> str:
        endpoint = f"api/v1/artifacts/artifact/{self.credentials.project_id}/{bucket}/{file_name}"
        response = self.session.get(f"{self.credentials.url}/{endpoint}")
        local_file_path = f"{extract_to}/{file_name}"
        with open(local_file_path, 'wb') as f:
            f.write(response.content)

        extract_dir = f"{local_file_path.replace('.zip', '')}"
        import shutil
        try:
            shutil.rmtree(extract_dir)
        except Exception as e:
            print(e)
        import zipfile
        with zipfile.ZipFile(local_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        import os
        if os.path.exists(local_file_path):
            os.remove(local_file_path)

        return extract_dir

    def get_report_file_name(self, report_id: str, extract_to: str = "/tmp"):
        endpoint = f"api/v1/backend_performance/reports/{self.credentials.project_id}?report_id={report_id}"
        report_info = self.request('get', endpoint)
        bucket_name = report_info["name"].replace("_", "").replace(" ", "").lower()
        report_archive_prefix = f"reports_test_results_{report_info['build_id']}"

        bucket_endpoint = f"api/v1/artifacts/artifacts/default/{self.credentials.project_id}/{bucket_name}"
        files_info = self.request('get', bucket_endpoint)
        file_list = [file_data["name"] for file_data in files_info["rows"]]

        for file_name in file_list:
            if file_name.startswith(report_archive_prefix):
                return report_info, self.download_and_unzip_reports(file_name, bucket_name, extract_to)

        return report_info, None

    def upload_excel_report(self, bucket_name: str, excel_report_name: str):
        upload_url = f'api/v1/artifacts/artifacts/{self.credentials.project_id}/{bucket_name}'
        full_url = f"{self.credentials.url.rstrip('/')}/{upload_url.lstrip('/')}"
        files = {'file': open(excel_report_name, 'rb')}
        headers = {'Authorization': f'bearer {self.credentials.token}'}
        s3_config = {'integration_id': 1, 'is_local': False}
        requests.post(full_url, params=s3_config, allow_redirects=True, files=files, headers=headers)

