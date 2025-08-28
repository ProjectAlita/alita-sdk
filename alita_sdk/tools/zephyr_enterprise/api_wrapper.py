import logging
from typing import Optional, List, Generator, Literal

from langchain_core.tools import ToolException
from pydantic import create_model, model_validator, PrivateAttr, Field, SecretStr

from langchain_core.documents import Document
from .zephyr_enterprise import ZephyrClient
from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools

logger = logging.getLogger(__name__)

zql_description = """
                    ZQL query to search for test cases. 
                    Supported: estimatedTime, testcaseId, creator, release,
                    project, priority, altId, version,
                    versionId, automated, folder, contents,
                    name, comment, tag

                    It has to follow the syntax in examples:
                    "folder=\"TestToolkit\"", "name~\"TestToolkit5\"
                    """

class ZephyrApiWrapper(NonCodeIndexerToolkit):
    base_url: str
    token: SecretStr
    _client: Optional[ZephyrClient] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        base_url = values.get('base_url')
        token = values.get('token')
        cls._client = ZephyrClient(base_url=base_url, token=token)
        return super().validate_toolkit(values)

    def get_test_case(self, testcase_id: str):

        """Retrieve test case data by id."""
        try:
            return self._client.get_test_case(testcase_id)
        except Exception as e:
            return ToolException(f"Unable to retrieve test cases: {e}")

    def search_zql(self, zql_json: str):

        """Retrieve Zephyr entities by zql."""
        try:
            return self._client.search_by_zql(zql_json)
        except Exception as e:
            return ToolException(f"Unable to retrieve Zephyr entities: {e}")


    def get_testcases_by_zql(self, zql: str, return_as_list: bool = False):

        """
        Retrieve testcases by zql.
        :param zql: ZQL query to search for test cases.
        :return: List of test cases matching the ZQL query.
        """
        try:
            testcases = self._client.get_testcases_by_zql(zql)
            parsed_test_cases = []
            if testcases['resultSize'] == 0:
                if return_as_list:
                    return []
                return "No test cases found for the provided ZQL query."
            logger.info(f"Retrieved test cases: {testcases}")
            if return_as_list:
                return [test_case['testcase'] for test_case in testcases['results']]
            for test_case in testcases['results']:
                parsed_test_cases.append(f"Test case ID: {test_case.get('id')}, Test case: {test_case['testcase']}")
            return "\n".join(parsed_test_cases)
        except Exception as e:
            return ToolException(f"Unable to retrieve Zephyr entities: {e}")

    def create_testcase(self, create_testcase_json: str):

        """
        Creates test case per given test case properties as JSON.
        NOTE: steps cannot be added from this method use method `add_steps` instead.
        """
        try:
            return self._client.create_testcase(create_testcase_json)
        except Exception as e:
            return ToolException(f"Unable to retrieve Zephyr entities: {e}")

    def get_test_case_steps(self, testcase_tree_id: str):
        last_version = self.get_last_version(testcase_tree_id)
        return self._client.get_testcase_steps(last_version)

    def get_last_version(self, testcase_tree_id: str):
        # get test case id
        test_case_id = self._client.get_test_case(testcase_tree_id)['testcase']['testcaseId']
        logger.info(f"Test case id: {test_case_id}")
        # get test case version id
        return self._client.get_testcase_versions(test_case_id)[-1]['id']

    def get_test_case_steps_by_version(self, test_case_version_id: str):
        return self._client.get_testcase_steps(test_case_version_id)

    def add_steps(self, testcase_tree_id: str, steps: Optional[List[dict]] = []):

        """
        Adds steps to the last test case version.
        :param testcase_tree_id: The ID of the test case.
        :param steps: List of steps to add ([{"step": "some_step", "data": "test step data", "result": "expected result"}, ...])
        :return: Test case data.
        """
        try:
            if not steps:
                return ToolException("Steps cannot be empty.")

            test_case_version_id = self.get_last_version(testcase_tree_id)
            logger.info(f"Test case version id: {test_case_version_id}")
            # get test case steps
            test_case_steps = self.get_test_case_steps_by_version(test_case_version_id)
            logger.info(f"Test case steps: {test_case_steps}")
            # add steps
            actual_steps = test_case_steps['steps'] if test_case_steps else None
            actual_max_order = max([int(step['orderId']) for step in actual_steps]) if actual_steps else 0
            test_steps_id = test_case_steps['id'] if test_case_steps else None
            added_steps = []
            # add new steps
            for step in steps:
                actual_max_order = actual_max_order + 1
                step_data = step.get('data', '')
                step_result = step.get('result', '')
                step_name = step.get('step', '')

                logger.info(f"Adding step: {step_name}, data: {step_data}, result: {step_result}")
                added_step = self._client.add_subsequent_step(
                    test_case_version_id=test_case_version_id,
                    test_case_zephyr_id=testcase_tree_id,
                    test_steps_id=test_steps_id,
                    max_id=actual_max_order,
                    order_id=actual_max_order,
                    step=step_name,
                    data=step_data,
                    result=step_result
                )
                added_steps.append(f"Step added: {step_name}, data: {step_data}, result: {step_result}")
                test_steps_id = added_step['id']

            return ";".join(added_steps)
        except Exception as e:
            return ToolException(f"Unable to retrieve Zephyr entities: {e}")

    def _index_tool_params(self, **kwargs) -> dict[str, tuple[type, Field]]:
        """
        Returns a list of fields for index_data args schema.
        """
        return {
            "zql": (str, Field(description=zql_description, examples=["folder=\"TestToolkit\"", "name~\"TestToolkit5\""])),
            'chunking_tool': (Literal['json'], Field(description="Name of chunking tool", default='json'))
        }

    def _base_loader(self, zql: str, **kwargs) -> Generator[Document, None, None]:
        test_cases = self.get_testcases_by_zql(zql=zql, return_as_list=True)
        for test_case in test_cases:
            metadata = {
                "updated_on": str(test_case.get("lastModifiedOn")),
                "id": str(test_case.get("id")),
                "name": test_case.get("name"),
                "testcaseId": str(test_case.get("testcaseId")),
                "projectId": test_case.get("projectId"),
                "projectName": test_case.get("projectName"),
                "testcaseType": test_case.get("testcaseType"),
            }
            yield Document(page_content='', metadata=metadata)

    def _extend_data(self, documents: Generator[Document, None, None]) -> Generator[Document, None, None]:
        for document in documents:
            try:
                id = document.metadata['id']
                test_case_content = self.get_test_case_steps(id)
                document.page_content = f"Test case: {document.metadata['name']}\nTest_case_content: {test_case_content}"
            except Exception as e:
                logging.error(f"Failed to process document: {e}")
            yield document

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "get_test_case",
                "description": self.get_test_case.__doc__,
                "args_schema": create_model(
                    "GetTestCasesModel",
                    testcase_id=(str, Field(description="The ID of the testcase"))
                ),
                "ref": self.get_test_case,
            },
            {
                "name": "search_zql",
                "description": self.search_zql.__doc__,
                "args_schema": create_model(
                    "SearchZqlModel",
                    zql_json=(str, Field(description=
                                         """
                                         Search for Zephyr entities using ZQL (Zephyr Query Language).
                                         Supports only search by name and id.
                                         By *Name*:
                                         _entityType_ - The values for the entitytype are testcase, requirement, or execution.
                                         _word_ - If you want to search a testcase by the name ‘untitled’, enter the query as: "name ~ \"untitled\""
                                         Constraints: always escape name if provided with double quotes.
                                         
                                         By *ID*:
                                         _entityType_
                                         _word_ - If you want to search a testcase by the id 2, then you must enter the query as: "testcaseId = 2"
                                         Example:
                                         1. `{"entitytype": "testcase","word": "name ~ \"Desktop.AEM.Booking\""}`
                                         2. `{"entitytype": "testcase","word": "id = 358380"}`
                                         3. `{"entitytype": "testcase","word": "id = 358380", "releaseid": "1", "projectid": ""}`
                                         """))
                ),
                "ref": self.search_zql,
            },
            {
                "name": "create_testcase",
                "description": self.create_testcase.__doc__,
                "args_schema": create_model(
                    "CreateTestcaseModel",
                    create_testcase_json=(str, Field(description=
                                         """
                                         JSON body of create test case query, i.e.
                                         `{ "tcrCatalogTreeId": 137973, "testcase": { "name": "TestToolkit", 
                                         "description": "some description", "projectId": 75 } }`
                                         """))
                ),
                "ref": self.create_testcase,
            },
            {
                "name": "add_steps",
                "description": self.add_steps.__doc__,
                "args_schema": create_model(
                    "AddStepsModel",
                    testcase_tree_id=(str, Field(description="The ID of the testcase")),
                    steps=(Optional[List[dict]], Field(description="""
                    List of steps to add per format:
                    [{"step": "some_step", "data": "test step data", "result": "expected result"}, ...]
                    """))
                ),
                "ref": self.add_steps,
            },
            {
                "name": "get_testcases_by_zql",
                "description": self.get_testcases_by_zql.__doc__,
                "args_schema": create_model(
                    "TestCaseByZqlModel",
                    zql=(str, Field(description=zql_description, examples=["folder=\"TestToolkit\"", "name~\"TestToolkit5\""]))
                ),
                "ref": self.get_testcases_by_zql,
            }
        ]