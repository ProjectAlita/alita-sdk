import logging
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

    def get_tests_list(self) -> List[Dict[str, Any]]:
        return self._client.get_tests_list()

    def run_test(self, test_id: str, json_body):
        return self._client.run_test(test_id, json_body)

    def get_engagements_list(self) -> List[Dict[str, Any]]:
        return self._client.get_engagements_list()

    def download_and_unzip_reports(self, file_name: str, bucket: str, extract_to: str = "/tmp") -> str:
        return self._client.download_and_unzip_reports(file_name, bucket, extract_to)

    def get_report_file_name(self, report_id: str, extract_to: str = "/tmp"):
        return self._client.get_report_file_name(report_id, extract_to)

    def upload_excel_report(self, bucket_name: str, excel_report_name: str):
        return self._client.upload_excel_report(bucket_name, excel_report_name)
