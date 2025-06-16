from typing import Optional, Dict, Any
from pydantic import BaseModel, model_validator, create_model, Field

import requests
import json

from ..elitea_base import BaseToolApiWrapper


class KeycloakApiWrapper(BaseToolApiWrapper):
    base_url: str
    realm: str
    client_id: str
    client_secret: str
    # Changed from PrivateAttr to Optional field with exclude=True
    client: Optional[requests.Session] = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        base_url = values.get('base_url')
        realm = values.get('realm')
        client_id = values.get('client_id')
        client_secret = values.get('client_secret')
        values['client'] = requests.Session()
        values['client'].headers.update({'Content-Type': 'application/json'})
        values['client'].auth = (client_id, client_secret)
        return values

    def get_keycloak_admin_token(self):
        url = f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token"
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        response = self.client.post(url, data=payload)
        response.raise_for_status()
        return response.json()['access_token']

    def execute(self, method: str, relative_url: str, params: Optional[str] = ""):
        """Execute a request to the Keycloak Admin API."""
        if not relative_url.startswith('/'):
            raise ValueError("The 'relative_url' must start with '/'.")

        full_url = f"{self.base_url}/admin/realms/{self.realm}{relative_url}"
        access_token = self.get_keycloak_admin_token()
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        self.client.headers.update(headers)
        payload_params = self.parse_payload_params(params)
        response = self.client.request(method, full_url, json=payload_params)
        response.raise_for_status()
        return response.text

    def parse_payload_params(self, params: Optional[str]) -> Dict[str, Any]:
        if params:
            json_acceptable_string = params.replace("'", "\"")
            return json.loads(json_acceptable_string)
        return {}

    def get_available_tools(self):
        return [
            {
                "name": "execute",
                "ref": self.execute,
                "description": self.execute.__doc__,
                "args_schema": create_model(
                    "ExecuteModel",
                    method=(str, Field(description="The HTTP method to use for the request (GET, POST, PUT, DELETE, etc.).")),
                    relative_url=(str, Field(description="The relative URL of the Keycloak Admin API to call, e.g. '/users'.")),
                    params=(Optional[str], Field(description="Optional string dictionary of parameters to be sent in the query string or request body.", default=""))
                ),
            }
        ]