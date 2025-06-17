import json
from typing import Any, Optional, List, Dict

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from pydantic import Field, PrivateAttr, model_validator, create_model, SecretStr
from requests import Session

from ...elitea_base import BaseToolApiWrapper


class GCPApiWrapper(BaseToolApiWrapper):
    api_key: SecretStr
    _credentials: Optional[Credentials] = PrivateAttr()
    _session: Optional[Session] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        api_key = values.get('api_key')
        if not api_key:
            raise ValueError("API key is required.")

        try:
            api_key_dict = json.loads(api_key)
            credentials = Credentials.from_service_account_info(api_key_dict)
            auth_request = Request()
            credentials.refresh(auth_request)
            session = Session()
            session.headers["Authorization"] = "Bearer " + credentials.token
            values['_credentials'] = credentials
            values['_session'] = session
        except Exception as e:
            raise ValueError(f"Error initializing GCP credentials: {str(e)}")

        return values

    def execute_request(self, method: str, scopes: List[str], url: str, optional_args: Optional[Dict[str, Any]] = None) -> str:
        """Execute a request to the Google Cloud REST API."""
        if not url:
            return "Error: No URL provided."

        try:
            self._credentials = Credentials.from_service_account_info(self.api_key, scopes=scopes)
            auth_request = Request()
            self._credentials.refresh(auth_request)
            self._session.headers["Authorization"] = "Bearer " + self._credentials.token
        except Exception as e:
            return f"Error: {str(e)}"

        try:
            response = self._session.request(method=method, url=url, **(optional_args or {}))
            if response.status_code < 400:
                return response.json() if response.text else "Success: The request has been fulfilled and resulted in a new resource being created."
            else:
                return f"Error: {response.status_code}, {response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_available_tools(self):
        return [
            {
                "name": "execute_request",
                "ref": self.execute_request,
                "description": self.execute_request.__doc__,
                "args_schema": create_model(
                    "ExecuteRequestModel",
                    method=(str, Field(description="The HTTP method to use for the request (GET, POST, PUT, DELETE, etc.).")),
                    scopes=(List[str], Field(description="List of OAuth 2.0 Scopes for Google APIs.")),
                    url=(str, Field(description="Absolute URI for Google Cloud REST API.")),
                    optional_args=(Optional[Dict[str, Any]], Field(description="Optional JSON object to be sent in request with possible keys: 'data', 'json', 'params', 'headers'.", default=None))
                ),
            }
        ]