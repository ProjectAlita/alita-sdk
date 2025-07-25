import json
import logging
import requests
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from .utils import get_latest_log_file
import shutil

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

    def add_tag_to_report(self, report_id, tag_name):
        endpoint = f"api/v1/backend_performance/tags/{self.credentials.project_id}/{report_id}"
        full_url = f"{self.credentials.url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            'Authorization': f'bearer {self.credentials.token}',
            'content-type': 'application/json'
        }
        data = {"tags": [{"title": tag_name, "hex": "#5933c6"}]}
        res = requests.post(full_url, headers=headers, json=data)
        return res

    def get_tests_list(self) -> List[Dict[str, Any]]:
        endpoint = f"api/v1/backend_performance/tests/{self.credentials.project_id}"
        return self.request('get', endpoint).get("rows", [])

    def create_test(self, data):
        endpoint = f"api/v1/backend_performance/tests/{self.credentials.project_id}"
        full_url = f"{self.credentials.url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {'Authorization': f'bearer {self.credentials.token}'}
        from json import dumps
        # Serialize the `data` dictionary into a JSON string
        form_data = {"data": dumps(data)}
        # Send the POST request
        res = requests.post(full_url, headers=headers, data=form_data)
        return res

    def run_test(self, test_id: str, json_body):
        endpoint = f"api/v1/backend_performance/test/{self.credentials.project_id}/{test_id}"
        return self.request('post', endpoint, json=json_body).get("result_id", "")

    def get_integrations(self, name: str):
        endpoint = f"api/v1/integrations/integrations/{self.credentials.project_id}?name={name}"
        return self.request('get', endpoint)

    def get_available_locations(self):
        endpoint = f"api/v1/shared/locations/default/{self.credentials.project_id}"
        return self.request('get', endpoint)

    def run_ui_test(self, test_id: str, json_body):
        """Run a UI test with the given test ID and JSON body."""
        endpoint = f"api/v1/ui_performance/test/{self.credentials.project_id}/{test_id}"
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
        lg_type = report_info.get("lg_type")
        bucket_endpoint = f"api/v1/artifacts/artifacts/default/{self.credentials.project_id}/{bucket_name}"
        files_info = self.request('get', bucket_endpoint)
        file_list = [file_data["name"] for file_data in files_info["rows"]]
        report_files_list = []
        for file_name in file_list:
            if file_name.startswith(report_archive_prefix) and "excel_report" not in file_name:
                report_files_list.append(file_name)
        test_log_file_path, errors_log_file_path = self.download_and_merge_reports(report_files_list, lg_type,
                                                                                   bucket_name, extract_to)

        return report_info, test_log_file_path, errors_log_file_path

    def download_and_merge_reports(self, report_files_list: list, lg_type: str, bucket: str, extract_to: str = "/tmp"):
        if lg_type == "jmeter":
            summary_log_file_path = f"summary_{bucket}_jmeter.jtl"
            error_log_file_path = f"error_{bucket}_jmeter.log"
        else:
            summary_log_file_path = f"summary_{bucket}_simulation.log"
            error_log_file_path = f"error_{bucket}_simulation.log"
        extracted_reports = []
        for each in report_files_list:
            endpoint = f"api/v1/artifacts/artifact/{self.credentials.project_id}/{bucket}/{each}"
            response = self.session.get(f"{self.credentials.url}/{endpoint}")
            local_file_path = f"{extract_to}/{each}"
            with open(local_file_path, 'wb') as f:
                f.write(response.content)

            extract_dir = f"{local_file_path.replace('.zip', '')}"
            try:
                shutil.rmtree(extract_dir)
            except Exception as e:
                logger.error(e)
            import zipfile
            with zipfile.ZipFile(local_file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            import os
            if os.path.exists(local_file_path):
                os.remove(local_file_path)
            extracted_reports.append(extract_dir)

        # get files from extract_dirs and merge to summary_log_file_path and error_log_file_path
        self.merge_log_files(summary_log_file_path, extracted_reports, lg_type)
        try:
            self.merge_error_files(error_log_file_path, extracted_reports)
        except Exception as e:
            logger.error(f"Failed to merge errors log: {e}")

        # Clean up
        for each in extracted_reports:
            try:
                shutil.rmtree(each)
            except Exception as e:
                logger.error(e)

        return summary_log_file_path, error_log_file_path

    def merge_log_files(self, summary_file, extracted_reports, lg_type):
        with open(summary_file, mode='w') as summary:
            for i, log_file in enumerate(extracted_reports):
                if lg_type == "jmeter":
                    report_file = f"{log_file}/jmeter.jtl"
                else:
                    report_file = get_latest_log_file(log_file, "simulation.log")
                with open(report_file, mode='r') as f:
                    lines = f.readlines()
                    if i == 0:
                        # Write all lines from the first file (including the header)
                        summary.writelines(lines)
                    else:
                        # Skip the first line (header) for subsequent files
                        summary.writelines(lines[1:])

    def merge_error_files(self, error_file, extracted_reports):
        with open(error_file, mode='w') as summary_errors:
            for i, log_file in enumerate(extracted_reports):
                report_file = f"{log_file}/simulation-errors.log"
                with open(report_file, mode='r') as f:
                    lines = f.readlines()
                    summary_errors.writelines(lines)

    def get_report_file_log(self, bucket: str, file_name: str):
        bucket_endpoint = f"api/v1/artifacts/artifact/default/{self.credentials.project_id}/{bucket}/{file_name}"
        full_url = f"{self.credentials.url.rstrip('/')}/{bucket_endpoint.lstrip('/')}"
        headers = {'Authorization': f'bearer {self.credentials.token}'}
        s3_config = {'integration_id': 1, 'is_local': False}
        response = requests.get(full_url, params=s3_config, headers=headers)
        file_path = f"/tmp/{file_name}"
        with open(file_path, 'wb') as f:
            f.write(response.content)
        return file_path

    def upload_file(self, bucket_name: str, file_name: str):
        upload_url = f'api/v1/artifacts/artifacts/{self.credentials.project_id}/{bucket_name}'
        full_url = f"{self.credentials.url.rstrip('/')}/{upload_url.lstrip('/')}"
        files = {'file': open(file_name, 'rb')}
        headers = {'Authorization': f'bearer {self.credentials.token}'}
        s3_config = {'integration_id': 1, 'is_local': False}
        requests.post(full_url, params=s3_config, allow_redirects=True, files=files, headers=headers)

    def get_ui_tests_list(self) -> List[Dict[str, Any]]:
        """Get list of UI tests from the Carrier platform."""
        endpoint = f"api/v1/ui_performance/tests/{self.credentials.project_id}"
        return self.request('get', endpoint).get("rows", [])

    def get_ui_reports_list(self) -> List[Dict[str, Any]]:
        """Get list of UI test reports from the Carrier platform."""
        endpoint = f"api/v1/ui_performance/reports/{self.credentials.project_id}"
        return self.request('get', endpoint).get("rows", [])

    def get_locations(self) -> Dict[str, Any]:
        """Get list of available locations/cloud settings from the Carrier platform."""
        endpoint = f"api/v1/shared/locations/{self.credentials.project_id}"
        return self.request('get', endpoint)

    def update_ui_test(self, test_id: str, json_body) -> Dict[str, Any]:
        """Update UI test configuration and schedule."""
        endpoint = f"api/v1/ui_performance/test/{self.credentials.project_id}/{test_id}"
        return self.request('put', endpoint, json=json_body)

    def get_ui_test_details(self, test_id: str) -> Dict[str, Any]:
        """Get detailed UI test configuration by test ID."""
        endpoint = f"api/v1/ui_performance/test/{self.credentials.project_id}/{test_id}"
        return self.request('get', endpoint)

    def create_ui_test(self, json_body: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new UI test."""
        endpoint = f"api/v1/ui_performance/tests/{self.credentials.project_id}"

        # Print full JSON POST body for debugging
        print("=" * 60)
        print("DEBUG: Full JSON POST body for create_ui_test:")
        print("=" * 60)
        print(json.dumps(json_body, indent=2))
        print("=" * 60)

        # Use multipart/form-data with data field containing the JSON body
        form_data = {'data': json.dumps(json_body)}

        # Temporarily remove Content-Type header to let requests set it for multipart
        original_headers = self.session.headers.copy()
        if 'Content-Type' in self.session.headers:
            del self.session.headers['Content-Type']

        try:
            full_url = f"{self.credentials.url.rstrip('/')}/{endpoint.lstrip('/')}"
            response = self.session.post(full_url, data=form_data)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as http_err:
            logger.error(f"HTTP {response.status_code} error: {response.text[:500]}")
            raise CarrierAPIError(f"Request to {full_url} failed with status {response.status_code}")
        except json.JSONDecodeError:
            logger.error(f"Response was not valid JSON. Body:\n{response.text[:500]}")
            raise CarrierAPIError("Server returned non-JSON response")
        finally:
            # Restore original headers
            self.session.headers.update(original_headers)

    def cancel_ui_test(self, test_id: str) -> Dict[str, Any]:
        """Cancel a UI test by setting its status to Canceled."""
        endpoint = f"api/v1/ui_performance/report_status/{self.credentials.project_id}/{test_id}"

        cancel_body = {
            "test_status": {
                "status": "Canceled",
                "percentage": 100,
                "description": "Test was canceled"
            }
        }

        return self.request('put', endpoint, json=cancel_body)
