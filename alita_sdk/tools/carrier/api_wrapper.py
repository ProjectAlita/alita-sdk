import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator, SecretStr
from .carrier_sdk import CarrierClient, CarrierCredentials, CarrierAPIError
from .utils import TicketPayload

logger = logging.getLogger(__name__)


class CarrierAPIWrapper(BaseModel):
    """
    Streamlined Wrapper for Carrier SDK API:
    - Single session initialization.
    - Authorization headers configured once.
    - Reduced redundancy using direct SDK methods.
    - Validation for required parameters.
    """

    url: str = Field(..., description="Carrier API Base URL")
    organization: str = Field(..., description="Organization identifier")
    private_token: SecretStr = Field(..., description="API authentication token")
    project_id: str = Field(..., description="Carrier Project ID")

    _client: Optional[CarrierClient] = None

    @model_validator(mode='after')
    def initialize_client(self):
        if not self.project_id:
            raise ValueError("project_id is required and cannot be empty.")
        try:
            credentials = CarrierCredentials(
                url=self.url,
                token=self.private_token.get_secret_value(),
                organization=self.organization,
                project_id=self.project_id
            )
            self._client = CarrierClient(credentials=credentials)
            logger.info("CarrierAPIWrapper initialized successfully.")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise e
        return self

    def fetch_tickets(self, board_id: str) -> List[Dict[str, Any]]:
        return self._client.fetch_tickets(board_id)

    def create_ticket(self, ticket_payload: TicketPayload) -> bool:
        try:
            json_response = self._client.create_ticket(ticket_payload)
            # Log it
            logger.info(f"Ticket successfully created: {json_response}")
            return json_response
        except CarrierAPIError as e:
            logger.error(f"Carrier API error creating ticket: {e}")
            return {}

    def fetch_test_data(self, start_time: str) -> List[Dict[str, Any]]:
        return self._client.fetch_test_data(start_time)

    def get_reports_list(self) -> List[Dict[str, Any]]:
        return self._client.get_reports_list()

    def add_tag_to_report(self, report_id, tag_name):
        return self._client.add_tag_to_report(report_id, tag_name)

    def get_tests_list(self) -> List[Dict[str, Any]]:
        return self._client.get_tests_list()

    def create_test(self, data: dict):
        return self._client.create_test(data)

    def get_integrations(self, name: str):
        return self._client.get_integrations(name)

    def get_available_locations(self):
        return self._client.get_available_locations()

    def run_test(self, test_id: str, json_body):
        return self._client.run_test(test_id, json_body)

    def run_ui_test(self, test_id: str, json_body):
        """Run a UI test with the given test ID and JSON body."""
        return self._client.run_ui_test(test_id, json_body)

    def get_engagements_list(self) -> List[Dict[str, Any]]:
        return self._client.get_engagements_list()

    def get_report_file_name(self, report_id: str, extract_to: str = "/tmp"):
        return self._client.get_report_file_name(report_id, extract_to)

    def get_report_file_log(self, bucket: str, file_name: str):
        return self._client.get_report_file_log(bucket, file_name)

    def upload_file(self, bucket_name: str, file_name: str):
        return self._client.upload_file(bucket_name, file_name)

    def get_ui_reports_list(self) -> List[Dict[str, Any]]:
        """Get list of UI test reports from the Carrier platform."""
        return self._client.get_ui_reports_list()

    def get_ui_tests_list(self) -> List[Dict[str, Any]]:
        """Get list of UI tests from the Carrier platform."""
        return self._client.get_ui_tests_list()

    def get_locations(self) -> Dict[str, Any]:
        """Get list of available locations/cloud settings from the Carrier platform."""
        return self._client.get_locations()

    def get_ui_report_links(self, uid: str) -> list:
        """Get all unique file_names for a given UI report UID, ending with .html, without #index=*, and only unique values."""
        endpoint = f"api/v1/ui_performance/results/{self.project_id}/{uid}?sort=loop&order=asc"
        try:
            response = self._client.request('get', endpoint)
            file_names = set()
            def clean_file_name(file_name):
                # Remove #index=... and everything after, then ensure it ends with .html
                # This regex removes #index=... and anything after .html
                match = re.match(r"(.+?\.html)", file_name)
                if match:
                    return match.group(1)
                return file_name
            # If the response is a dict with lists as values, flatten all file_names from all values
            if isinstance(response, dict):
                for value in response.values():
                    if isinstance(value, list):
                        for item in value:
                            file_name = item.get("file_name")
                            if file_name:
                                clean_name = clean_file_name(file_name)
                                file_names.add(clean_name)
            elif isinstance(response, list):
                for item in response:
                    file_name = item.get("file_name")
                    if file_name:
                        clean_name = clean_file_name(file_name)
                        file_names.add(clean_name)
            sorted_names = sorted(file_names)
            prefix = f"https://platform.getcarrier.io/api/v1/artifacts/artifact/default/{self.project_id}/reports/"
            return [prefix + name for name in sorted_names]
        except Exception as e:
            logger.error(f"Failed to fetch UI report links: {e}")
            return []

    def update_ui_test(self, test_id: str, json_body) -> Dict[str, Any]:
        """Update UI test configuration and schedule."""
        return self._client.update_ui_test(test_id, json_body)

    def get_ui_test_details(self, test_id: str) -> Dict[str, Any]:
        """Get detailed UI test configuration by test ID."""
        return self._client.get_ui_test_details(test_id)

    def create_ui_test(self, json_body: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new UI test."""
        return self._client.create_ui_test(json_body)

    def cancel_ui_test(self, test_id: str) -> Dict[str, Any]:
        """Cancel a UI test by setting its status to Canceled."""
        return self._client.cancel_ui_test(test_id)

    def get_ui_report_json_files(self, uid: str) -> list:
        """Get all JSON file names for a given UI report UID for Excel processing."""
        endpoint = f"api/v1/ui_performance/results/{self.project_id}/{uid}?sort=loop&order=asc"
        try:
            response = self._client.request('get', endpoint)
            file_names = set()
            
            def clean_file_name(file_name):
                # Extract JSON files only and clean the names
                if file_name.endswith('.json'):
                    return file_name
                return None
            
            # If the response is a dict with lists as values, flatten all file_names from all values
            if isinstance(response, dict):
                for value in response.values():
                    if isinstance(value, list):
                        for item in value:
                            file_name = item.get("file_name")
                            if file_name:
                                clean_name = clean_file_name(file_name)
                                if clean_name:
                                    file_names.add(clean_name)
            elif isinstance(response, list):
                for item in response:
                    file_name = item.get("file_name")
                    if file_name:
                        clean_name = clean_file_name(file_name)
                        if clean_name:
                            file_names.add(clean_name)
            
            sorted_names = sorted(file_names)
            prefix = f"https://platform.getcarrier.io/api/v1/artifacts/artifact/default/{self.project_id}/reports/"
            return [prefix + name for name in sorted_names]
        except Exception as e:
            logger.error(f"Failed to fetch UI report JSON files: {e}")
            return []

    def download_ui_report_json(self, bucket: str, file_name: str) -> str:
        """Download UI report JSON file content."""
        endpoint = f"api/v1/artifacts/artifact/default/{self.project_id}/{bucket}/{file_name}"
        try:
            response = self._client.request('get', endpoint)
            return response
        except Exception as e:
            logger.error(f"Failed to download UI report JSON: {e}")
            return None