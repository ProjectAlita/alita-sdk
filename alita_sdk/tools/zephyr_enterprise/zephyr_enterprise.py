import base64
import json
from typing import Optional

import requests
from langchain_core.tools import ToolException


class ZephyrEndpoints:
    TESTCASE = "/flex/services/rest/latest/testcase/"
    ADVANCESEARCH_ZQL = "/flex/services/rest/latest/advancesearch/zql"
    TESTCASE_VERSIONS = "/flex/services/rest/latest/testcase/versions"
    TESTSTEP_DETAIL = "/flex/services/rest/latest/testcase/{test_case_version_id}/teststep/detail/{test_case_zephyr_id}"
    TESTSTEP = "/flex/services/rest/latest/testcase/{test_case_version_id}/teststep"
    TESTCASE_ZQL = "/flex/services/rest/latest/testcase"

class ZephyrClient:
    def __init__(self, base_url, token):
        """
        Initialize the Zephyr Enterprise Client.

        :param base_url: The base URL of the Zephyr Enterprise instance.
        :param username: The username for authentication.
        :param password: The password for authentication.
        """
        self.base_url = base_url.rstrip("/")  # Ensure no trailing slash
        self.auth_header = self._generate_auth_header(token=token)

    def _generate_auth_header(self, token: str = None, username: str = None, password: str = None):
        """
        Generate the Basic Authentication header.

        :param token: Token for authentication.
        :param username: The username for authentication.
        :param password: The password for authentication.
        :return: A dictionary containing the Authorization header.
        """

        if not (token or (username and password)):
            raise ToolException("You have to declare token or username with password for authentication")

        if token:
            return {"Authorization": f"Bearer {token}"}

        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded_credentials}"}

    def _request(self, method, endpoint, params=None, data=None):
        """
        Generic method to make API requests.

        :param method: HTTP method (GET, POST, PUT, DELETE).
        :param endpoint: API endpoint (relative to the base URL).
        :param params: Query parameters (optional).
        :param data: Request body (optional, for POST/PUT).
        :return: Response JSON or raise an exception for errors.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {**self.auth_header, "Content-Type": "application/json"}

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=json.dumps(data) if data else None,
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    def get_test_case(self, testcase_id: str):

        """
        Retrieve test case information by id

        :param testcase_id: The ID of the test case.
        :return: Test case information.
        """
        return self._request("GET", f"{ZephyrEndpoints.TESTCASE}{testcase_id}")

    def search_by_zql(self, zql_json: str):

        """
        Retrieve Zephyr entities by zql

        :param zql_json: ZQL json.
        :return: List of entities.
        """
        return self._request("POST", ZephyrEndpoints.ADVANCESEARCH_ZQL, data=json.loads(zql_json))

    def create_testcase(self, create_testcase_json: str):

        """
        Creates new test case per given create_testcase_json fields

        :param create_testcase_json: JSON string testcase entity.
        :return: Test case data.
        """
        return self._request("POST", ZephyrEndpoints.TESTCASE, data=json.loads(create_testcase_json))

    def get_testcase_versions(self, testcaseid: str):

        """
        Retrieve test case versions by id
        :param testcaseid: The ID of the test case.
        :return: Test case versions.
        """
        return self._request("GET", ZephyrEndpoints.TESTCASE_VERSIONS, params={"testcaseid": testcaseid})

    def get_testcase_steps(self, test_case_version_id: str):

        """
        Retrieve test case steps from specific test case version
        :param test_case_version_id: The ID of the test case version.
        :return: Test case steps.
        """
        return self._request("GET", ZephyrEndpoints.TESTSTEP.format(test_case_version_id=test_case_version_id))

    def add_subsequent_step(self, test_case_version_id: str, test_case_zephyr_id: str, max_id: str,
                            step: str, data: str, result: str,
                            test_steps_id: Optional[str] = None,
                            order_id: Optional[str] = None):

        """
        Add subsequent step to test case with specified version
        :param test_case_version_id: The ID of the test case version.
        :param test_case_zephyr_id: The ID of the test case.
        :param test_steps_id: The ID of the test steps.
        :param max_id: The maximum ID for the step.
        :param order_id: The order ID for the step.
        :param step: The step to add.
        :param data: The data for the step.
        :param result: The expected result for the step.
        :return: Response from the API.
        """
        body = {
                "tcId": test_case_version_id,
                "maxId": max_id,
                "step": {
                    "step": step,
                    "data": data,
                    "result": result,
                    "orderId": order_id if order_id else "1"
                },
                "tctId": test_case_zephyr_id
            }
        if test_steps_id:
            body.update({"id": test_steps_id})
        return self._request(
            "POST",
            ZephyrEndpoints.TESTSTEP_DETAIL.format(test_case_version_id=test_case_version_id,
                                                   test_case_zephyr_id=test_case_zephyr_id),
            data={
                "tcId": test_case_version_id,
                "maxId": max_id,
                "step": {
                    "step": step,
                    "data": data,
                    "result": result,
                    "orderId": order_id
                },
                "tctId": test_case_zephyr_id,
                "id": test_steps_id
            }
        )

    def get_testcases_by_zql(self, zql: str):

        """
        Retrieve test cases by ZQL query.
        :param zql: ZQL query string.
        :return: List of test cases matching the ZQL query.
        """
        return self._request("GET", ZephyrEndpoints.TESTCASE_ZQL, params={"zqlquery": zql})
