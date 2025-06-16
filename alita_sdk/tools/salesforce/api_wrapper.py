import json
from typing import Optional

import requests
from langchain_core.tools import ToolException
from pydantic import PrivateAttr, SecretStr

from .model import (
    SalesforceCreateCase,
    SalesforceCreateLead,
    SalesforceSearch,
    SalesforceUpdateCase,
    SalesforceUpdateLead,
    SalesforceInput
)
from ..elitea_base import BaseToolApiWrapper


class SalesforceApiWrapper(BaseToolApiWrapper):
    base_url: str
    client_id: str
    client_secret: SecretStr
    api_version: str = "v59.0"
    
    _access_token: Optional[str] = PrivateAttr(default=None)

    def authenticate(self):
        """
        Authenticate with Salesforce and obtain an access token.
        """
        auth_url = f"{self.base_url}/services/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret.get_secret_value()
        }

        response = requests.post(auth_url, data=payload)
        response.raise_for_status()
        self._access_token = response.json().get("access_token")

    def _parse_salesforce_error(self, response) -> Optional[str]:
        """
        Parses Salesforce error responses and returns a user-friendly error message.

        Args:
            response (requests.Response): The HTTP response from Salesforce.

        Returns:
            str | None: Parsed error message, or None if the response is successful.
        """
        try:
            if response.status_code == 204:
                return None  # No error, it's a successful No Content response

            response_data = response.json()

            # If response is successful, return None (no error)
            if response.status_code in [200, 201] and ("id" in response_data or response_data.get("success", False)):
                return None  # No error, response is valid

            # If Salesforce returns a list of errors
            if isinstance(response_data, list):
                error_messages = []
                for error in response_data:
                    message = error.get("message", "Unknown error")
                    error_code = error.get("errorCode", "UNKNOWN_ERROR")

                    # Handle Duplicate Record Error
                    if "DUPLICATES_DETECTED" in error_code:
                        return "Duplicate detected: Salesforce found similar records. Consider updating an existing record."

                    error_messages.append(message)

                return "; ".join(error_messages)

            # If Salesforce returns a single error dictionary
            elif isinstance(response_data, dict) and "message" in response_data:
                return response_data.get("message", "Unknown error")

            # Unexpected response format
            else:
                return f"Unexpected response format: {response_data}"

        except requests.exceptions.JSONDecodeError:
            return f"No JSON response from Salesforce. HTTP Status: {response.status_code}"



    def _headers(self):
        if not self._access_token:
            self.authenticate()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }

    def create_case(self, subject: str, description: str, origin: str, status: str):
        """
        Create a new Salesforce Case.
        """
        url = f"{self.base_url}/services/data/{self.api_version}/sobjects/Case/"
        payload = {
            "Subject": subject,
            "Description": description,
            "Origin": origin,
            "Status": status
        }

        response = requests.post(url, json=payload, headers=self._headers())

        if response.status_code >= 400:
            error_message = self._parse_salesforce_error(response)
            return ToolException(f"Failed to create Case. Error: {error_message}")

        return response.json()


    def create_lead(self, last_name: str, company: str, email: str, phone: str):
        """
        Create a new Salesforce Lead.
        """
        url = f"{self.base_url}/services/data/{self.api_version}/sobjects/Lead/"
        payload = {
            "LastName": last_name,
            "Company": company,
            "Email": email,
            "Phone": phone
        }

        response = requests.post(url, json=payload, headers=self._headers())

        if response.status_code >= 400:
            error_message = self._parse_salesforce_error(response)
            return ToolException(f"Failed to create Lead. Error: {error_message}")

        return response.json()



    def search_salesforce(self, object_type: str, query: str):
        """
        Perform a SOQL search in Salesforce.
        """
        url = f"{self.base_url}/services/data/{self.api_version}/query?q={query}"
        response = requests.get(url, headers=self._headers())

        if response.status_code >= 400:
            try:
                errors = response.json()
                if isinstance(errors, list):
                    error_messages = "; ".join(error.get("message", "Unknown error") for error in errors)
                else:
                    error_messages = errors.get("message", "Unknown error")
            except requests.exceptions.JSONDecodeError:
                return ToolException(f"Failed to execute SOQL query. No JSON response. Status: {response.status_code}")

            return ToolException(f"Failed to execute SOQL query. Errors: {error_messages}")

        return response.json()

    def update_case(self, case_id: str, status: str, description: str = ""):
        """
        Update an existing Salesforce Case.
        """
        url = f"{self.base_url}/services/data/{self.api_version}/sobjects/Case/{case_id}"
        payload = {"Status": status}
        if description:
            payload["Description"] = description

        response = requests.patch(url, json=payload, headers=self._headers())

        if response.status_code == 204:
            return {"success": True, "message": f"Case {case_id} updated successfully."}

        error_message = self._parse_salesforce_error(response)
        raise ToolException(f"Failed to update Case {case_id}. Error: {error_message}")


    def update_lead(self, lead_id: str, email: Optional[str] = None, phone: Optional[str] = None):
        """
        Update an existing Salesforce Lead.
        """
        url = f"{self.base_url}/services/data/{self.api_version}/sobjects/Lead/{lead_id}"
        payload = {}
        if email:
            payload["Email"] = email
        if phone:
            payload["Phone"] = phone

        response = requests.patch(url, json=payload, headers=self._headers())

        if response.status_code == 204:
            return {"success": True, "message": f"Lead {lead_id} updated successfully."}

        error_message = self._parse_salesforce_error(response)
        return ToolException(f"Failed to update Lead {lead_id}. Error: {error_message}")


    def execute_generic_rq(self, method: str, relative_url: str, params: Optional[str] = "{}"):
        """
        Execute a generic API request to Salesforce.

        Args:
            method (str): HTTP method (GET, POST, PATCH, DELETE).
            relative_url (str): Salesforce API relative URL (e.g., '/sobjects/Case/').
            params (Optional[str]): JSON string for request body or query parameters.

        Returns:
            dict | str: API response or success message.
        """
        url = f"{self.base_url}/services/data/{self.api_version}{relative_url}"

        try:
            payload = json.loads(params) if params else {}
        except json.JSONDecodeError:
            raise ToolException("Invalid JSON format in 'params'.")

        response = requests.request(method, url, headers=self._headers(), json=payload if method != "GET" else None)

        # Handle 204 No Content as a success case
        if response.status_code == 204:
            return {"success": True, "message": f"{method} request to {relative_url} executed successfully."}

        # Handle GET requests properly
        if method == "GET" and response.status_code == 200:
            return response.json()

        # Check for actual errors before raising an exception
        error_message = self._parse_salesforce_error(response)
        if error_message:
            return ToolException(f"Failed {method} request to {relative_url}. Error: {error_message}")

        return response.json()




    def get_available_tools(self):
        return [
            {"name": "create_case", "description": "Create a new Case", "args_schema": SalesforceCreateCase, "ref": self.create_case},
            {"name": "create_lead", "description": "Create a new Lead", "args_schema": SalesforceCreateLead, "ref": self.create_lead},
            {"name": "search_salesforce", "description": "Search Salesforce with SOQL", "args_schema": SalesforceSearch, "ref": self.search_salesforce},
            {"name": "update_case", "description": "Update a Case", "args_schema": SalesforceUpdateCase, "ref": self.update_case},
            {"name": "update_lead", "description": "Update a Lead", "args_schema": SalesforceUpdateLead, "ref": self.update_lead},
            {"name": "execute_generic_rq", "description": "Execute a generic Salesforce API request.", "args_schema": SalesforceInput, "ref": self.execute_generic_rq}
        ]
