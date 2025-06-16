import requests

from typing import Optional, List, Dict, Any, Union

from pydantic import model_validator, create_model, Field, SecretStr

from ..elitea_base import BaseToolApiWrapper

from logging import getLogger
logger = getLogger(__name__)


GET_TEST_CASES_FOR_TEST = """Retrieve detailed information about test cases for a particular launch (test)
including test cases description, steps and expected result.
"""

GET_TEST_CASES_STATUSES_FOR_TEST = """Fetch information regarding statuses of executed test cases within a particular launch (test),
e.g. Passed, Failed, Pending.
"""

LIST_BUGS_FOR_TEST_WITH_FILTER = """Retrieve detailed information about bugs associated with test cases
executed within a particular launch (test) with optional filters.
"""

LIST_PRODUCTS = """Retrieve a list of all available products with optional filtering by product IDs."""

GET_PRODUCT = """Retrieve detailed information about a specific product by its ID."""

LIST_FEATURES = """Retrieve a comprehensive list of features across all products with optional filtering by feature IDs."""

GET_FEATURE = """Retrieve detailed information about a specific feature by its ID."""

LIST_USER_STORIES = """Retrieve a list of user stories with optional filtering by story IDs."""

GET_USER_STORY = """Retrieve detailed information about a specific user story by its ID."""

LIST_EXPLORATORY_TESTS = """Retrieve a list of exploratory tests with optional filtering by product ID."""

GET_EXPLORATORY_TEST = """Retrieve detailed information about a specific exploratory test by its ID."""

CREATE_EXPLORATORY_TEST = """Create a new exploratory test with specified parameters including product, section, test type, devices, etc."""

LIST_TEST_CASES = """Retrieve a list of test cases for a specific product with optional filtering by section."""

GET_TEST_CASE = """Retrieve detailed information about a specific test case by its ID and product ID."""

CONFIRM_BUG_FIX = """Confirm the status of a bug fix with optional comments."""

class TestIOApiWrapper(BaseToolApiWrapper):
    endpoint: str
    api_key: SecretStr
    headers: Optional[Dict[str, str]] = None

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        endpoint = values.get('endpoint')
        if endpoint is not None:
            values['endpoint'] = endpoint.rstrip('/')

        api_key = values.get('api_key')
        if api_key is not None:
            values['headers'] = {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
        return values

    def _handle_response(self, response: requests.Response):
        if response.status_code == 401:
            raise ValueError("Unauthorized: Invalid API key")
        if response.status_code == 404:
            raise ValueError("Not Found: The requested resource does not exist")
        response.raise_for_status()

    def get_test_cases_for_test(
        self,
        product_id: int,
        test_case_test_id: int,
        client_fields: Optional[List[str]] = None
    ) -> str:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/test_case_tests/{test_case_test_id}"
        response = requests.get(url, headers=self.headers)
        self._handle_response(response)
        data =response.json().get('test_case_test')
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data


    def get_test_cases_statuses_for_test(
        self,
        product_id: int,
        test_case_test_id: int,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/test_case_tests/{test_case_test_id}/results"
        response = requests.get(url, headers=self.headers)
        self._handle_response(response)
        data = response.json()
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def list_bugs_for_test_with_filter(
        self,
        filter_product_ids: Optional[str] = None,
        filter_test_cycle_ids: Optional[str] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/bugs"
        params: Dict[str, Any] = {}
        if filter_product_ids:
            params["filter_product_ids"] = filter_product_ids
        if filter_test_cycle_ids:
            params["filter_test_cycle_ids"] = filter_test_cycle_ids
        response = requests.get(url, headers=self.headers, params=params)
        self._handle_response(response)
        data = response.json().get('bugs', [])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def list_products(
        self,
        filter_product_ids: Optional[List[int]] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products"
        params: Dict[str, Any] = {}
        if filter_product_ids:
            params["filter"] = {"product_ids": filter_product_ids}
        response = requests.get(url, headers=self.headers, params=params)
        data = response.json().get('products', [])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def get_product(
        self,
        product_id: int,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}"
        response = requests.get(url, headers=self.headers)
        self._handle_response(response)
        data = response.json().get('product', {})
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def list_features(
        self,
        product_id: int,
        filter_ids: Optional[List[int]] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/features"
        params: Dict[str, Any] = {}
        if filter_ids:
            params['filter_feature_ids'] = ','.join(map(str, filter_ids))
        response = requests.get(url, headers=self.headers, params=params)
        self._handle_response(response)
        data = response.json().get('features', [])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def get_feature(
        self,
        product_id: int,
        feature_id: int,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        data = self.list_features(product_id=product_id, filter_ids=[feature_id])
        if data:
            data = data[0]
        else:
            data = {}
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def list_user_stories(
        self,
        product_id: Optional[int] = None,
        filter_ids: Optional[List[int]] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/user_stories"
        params: Dict[str, Any] = {}
        if filter_ids:
            params['filter_user_story_ids'] = ','.join(map(str, filter_ids))
        response = requests.get(url, headers=self.headers, params=params)
        self._handle_response(response)
        data = response.json().get('user_stories', [])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def get_user_story(
        self,
        product_id: int,
        story_id: int,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        data = self.list_user_stories(product_id=product_id, filter_ids=[story_id])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def list_exploratory_tests(
        self,
        product_id: Optional[int] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/exploratory_tests"
        params: Dict[str, Any] = {}
        response = requests.get(url, headers=self.headers, params=params)
        self._handle_response(response)
        data = response.json().get('exploratory_tests', [])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def get_exploratory_test(
        self,
        product_id: int,
        exploratory_test_id: int,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        data = self.list_exploratory_tests(product_id=product_id)
        data = next((test for test in data if test['id'] == exploratory_test_id), None)
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def create_exploratory_test(
        self,
        product_id: int,
        section_id: int,
        test_type: str,
        devices: List[int],
        features: List[int],
        start_date: str,
        end_date: str,
        test_goal: str,
        out_of_scope: Optional[str] = None,
        requirements: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        url = f"{self.endpoint}/customer/v2/exploratory_tests"
        payload: Dict[str, Any] = {
            'product_id': product_id,
            'section_id': section_id,
            'test_type': test_type,
            'devices': devices,
            'features': features,
            'start_date': start_date,
            'end_date': end_date,
            'test_goal': test_goal
        }
        if out_of_scope:
            payload['out_of_scope'] = out_of_scope
        if requirements:
            payload['requirements'] = requirements
        response = requests.post(url, headers=self.headers, json=payload)
        self._handle_response(response)
        return response.json()

    def list_test_cases(
        self,
        product_id: int,
        cycle_id: int,
        section_id: Optional[int] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/test_case_tests/{cycle_id}"
        params: Dict[str, Any] = {}
        if section_id:
            params['filter_section_ids'] = section_id
        response = requests.get(url, headers=self.headers, params=params)
        self._handle_response(response)
        data = response.json().get('test_cases', [])
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def get_test_case(
        self,
        product_id: int,
        test_case_id: int,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/products/{product_id}/test_cases/{test_case_id}"
        response = requests.get(url, headers=self.headers)
        self._handle_response(response)
        data = response.json().get('test_case', {})
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def confirm_bug_fix(
        self,
        bug_id: int,
        status: str,
        comment: Optional[str] = None,
        client_fields: Optional[List[str]] = None
    ) -> Any:
        url = f"{self.endpoint}/customer/v2/bug_report_confirmations"
        payload: Dict[str, Any] = {'bug_id': bug_id, 'status': status}
        if comment:
            payload['comment'] = comment
        response = requests.post(url, headers=self.headers, json=payload)
        self._handle_response(response)
        data = response.json()
        if client_fields:
            return self.filter_fields(data, client_fields)
        return data

    def filter_fields(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        fields: List[str]
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Returns only the specified fields from each dict in a list or a single dict.
        """
        def _filter(item: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v for k, v in item.items() if k in fields}

        if isinstance(data, list):
            return [_filter(item) for item in data]
        if isinstance(data, dict):
            return _filter(data)
        return data

    def get_available_tools(self):
        return [
            {
                "name": "list_products",
                "description": LIST_PRODUCTS,
                "args_schema": create_model(
                    "ListProductsModel",
                    filter_product_ids=(Optional[List[int]], Field(description="List of product IDs to filter by", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.list_products
            },
            {
                "name": "get_product",
                "description": GET_PRODUCT,
                "args_schema": create_model(
                    "GetProductModel",
                    product_id=(int, Field(description="The ID of the product")),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.get_product
            },
            {
                "name": "list_features",
                "description": LIST_FEATURES,
                "args_schema": create_model(
                    "ListFeaturesModel",
                    product_id=(int, Field(description="The ID of the product")),
                    filter_ids=(Optional[List[int]], Field(description="Filter by feature IDs", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.list_features
            },
            {
                "name": "get_feature",
                "description": GET_FEATURE,
                "args_schema": create_model(
                    "GetFeatureModel",
                    product_id=(int, Field(description="The ID of the product")),
                    feature_id=(int, Field(description="The ID of the feature")),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.get_feature
            },
            {
                "name": "list_user_stories",
                "description": LIST_USER_STORIES,
                "args_schema": create_model(
                    "ListUserStoriesModel",
                    product_id=(int, Field(description="The ID of the product")),
                    filter_ids=(Optional[List[int]], Field(description="Filter by user story IDs", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.list_user_stories
            },
            {
                "name": "get_user_story",
                "description": GET_USER_STORY,
                "args_schema": create_model(
                    "GetUserStoryModel",
                    product_id=(int, Field(description="The ID of the product")),
                    story_id=(int, Field(description="The ID of the user story")),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.get_user_story
            },
            {
                "name": "list_exploratory_tests",
                "description": LIST_EXPLORATORY_TESTS,
                "args_schema": create_model(
                    "ListExploratoryTestsModel",
                    product_id=(Optional[int], Field(description="Filter by product ID", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.list_exploratory_tests
            },
            {
                "name": "get_exploratory_test",
                "description": GET_EXPLORATORY_TEST,
                "args_schema": create_model(
                    "GetExploratoryTestModel",
                    exploratory_test_id=(int, Field(description="The ID of the exploratory test")),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.get_exploratory_test
            },
            {
                "name": "create_exploratory_test",
                "description": CREATE_EXPLORATORY_TEST,
                "args_schema": create_model(
                    "CreateExploratoryTestModel",
                    product_id=(int, Field(description="The ID of the product")),
                    section_id=(int, Field(description="The ID of the section")),
                    test_type=(str, Field(description="Type of the test")),
                    devices=(List[int], Field(description="List of device IDs")),
                    features=(List[int], Field(description="List of feature IDs")),
                    start_date=(str, Field(description="Start date in ISO format")),
                    end_date=(str, Field(description="End date in ISO format")),
                    test_goal=(str, Field(description="Description of the test goal")),
                    out_of_scope=(Optional[str], Field(description="Description of what's out of scope", default=None)),
                    requirements=(Optional[List[str]], Field(description="List of requirements", default=None))
                ),
                "ref": self.create_exploratory_test
            },
            {
                "name": "list_test_cases",
                "description": LIST_TEST_CASES,
                "args_schema": create_model(
                    "ListTestCasesModel",
                    product_id=(int, Field(description="The ID of the product")),
                    cycle_id=(int, Field(description="The ID of the test cycle")),
                    section_id=(Optional[int], Field(description="Filter by section ID", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.list_test_cases
            },
            {
                "name": "get_test_case",
                "description": GET_TEST_CASE,
                "args_schema": create_model(
                    "GetTestCaseModel",
                    product_id=(int, Field(description="The ID of the product")),
                    test_case_id=(int, Field(description="The ID of the test case")),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.get_test_case
            },
            {
                "name": "confirm_bug_fix",
                "description": CONFIRM_BUG_FIX,
                "args_schema": create_model(
                    "ConfirmBugFixModel",
                    bug_id=(int, Field(description="The ID of the bug")),
                    status=(str, Field(description="Status of the bug fix confirmation")),
                    comment=(Optional[str], Field(description="Optional comment on the bug fix", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.confirm_bug_fix
            },
            {
                "name": "get_test_cases_for_test",
                "description": GET_TEST_CASES_FOR_TEST,
                "args_schema": create_model(
                    "GetTestCasesForTestModel",
                    product_id=(int, Field(description="The ID of the product")),
                    test_case_test_id=(int, Field(description="The ID of the test case test"))
                ),
                "ref": self.get_test_cases_for_test
            },
            {
                "name": "get_test_cases_statuses_for_test",
                "description": GET_TEST_CASES_STATUSES_FOR_TEST,
                "args_schema": create_model(
                    "GetTestCasesStatusesForTestModel",
                    product_id=(int, Field(description="The ID of the product")),
                    test_case_test_id=(int, Field(description="The ID of the test case test")),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.get_test_cases_statuses_for_test,
            },
            {
                "name": "list_bugs_for_test_with_filter",
                "description": LIST_BUGS_FOR_TEST_WITH_FILTER,
                "args_schema": create_model(
                    "ListBugsForTestWithFilterModel",
                    filter_product_ids=(Optional[str], Field(description="Comma-separated list of product IDs to filter by", default=None)),
                    filter_test_cycle_ids=(Optional[str], Field(description="Comma-separated list of test cycle IDs to filter by", default=None)),
                    client_fields=(Optional[List[str]], Field(description="Fields to include in the response", default=None))
                ),
                "ref": self.list_bugs_for_test_with_filter,
            }
        ]
