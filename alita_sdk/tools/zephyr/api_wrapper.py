import json
import logging
from typing import List, Optional

from pydantic import model_validator, create_model, Field, SecretStr
from pydantic.fields import PrivateAttr

from .Zephyr import Zephyr
from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

ZephyrGetTestSteps = create_model(
    "ZephyrGetTestSteps",
    issue_id=(int, Field(description="Jira ticket id for which test steps are required.")),
    project_id=(int, Field(description="Jira project id which test case is belong to."))
)

ZephyrAddNewTestStep = create_model(
    "ZephyrAddNewTestStep",
    issue_id=(int, Field(description="Jira ticket id for which test steps are required.")),
    project_id=(int, Field(description="Jira project id which test case is belong to.")),
    step=(str, Field(description="Test step description with flow what should be done in this step. e.g. 'Click search button.'")),
    data=(str, Field(description="Any test data which is used in this specific test. Can be empty if no specific data is used for the step. e.g. 'program languages: 'Java', 'Kotlin', 'Python'")),
    result=(str, Field(description="Verification what should be checked after test step is executed. Can be empty if no specific verifications is needed for the step. e.g. 'Search results page is loaded'"))
)

ZephyrAddTestCase = create_model(
    "ZephyrAddTestCase",
    issue_id=(int, Field(description="Jira ticket id for where test case should be created.")),
    project_id=(int, Field(description="Jira project id which test case is belong to.")),
    steps_data=(str, Field(description="""JSON list of steps need to be added to Jira ticket in format { "steps":[ { "step":"click something", "data":"expected data", "result":"expected result" }, { "step":"click something2", "data":"expected data2", "result":"expected result" } ] }"""))
)

ZephyrAddTestCases = create_model(
    "ZephyrAddTestCases",
    create_test_cases_data=(str, Field(description="""JSON array in format [{issue_id: int, project_id: int, steps: [ { "step":"click something", "data":"expected data", "result":"expected result" }, ...]}, ...],
    where issue_id - Jira ticket id for where test case should be created,
    project_id - Jira project id which test case is belong to,
    steps -  list of steps need to be added to Jira ticket"""))
)

class ZephyrV1ApiWrapper(BaseToolApiWrapper):
    base_url: str
    username: str
    password: SecretStr
    _client: Optional[Zephyr] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        base_url = values['base_url']
        username = values['username']
        password = values['password']
        cls._client = Zephyr(base_url=base_url,
                                  username=username,
                                  password=password)
        return values

    def _parse_test_steps(self, test_steps) -> List[dict]:
        parsed = []
        step_bean = test_steps["stepBeanCollection"]
        for test_step in step_bean:
            order_id = test_step["orderId"]
            step = test_step["step"]
            data = test_step["data"]
            result = test_step["result"]

            parsed_step = {
                "order_id": order_id,
                "step": step,
                "data": data,
                "result": result
            }
            parsed.append(parsed_step)
        return parsed

    def get_test_case_steps(self, issue_id: int, project_id: int):
        """ Get test case steps by issue_id."""
        parsed = self._parse_test_steps(self._client.get_test_case_steps(issue_id, project_id).json())
        if len(parsed) == 0:
            return "No Zephyr test steps found"
        return "Found " + str(len(parsed)) + " test steps:\n" + str(parsed)

    def add_new_test_case_step(self, issue_id: int, project_id: int, step: str, data: str, result: str):
        """ Adds new test case step by issue_id."""
        return "New test step created: " + self._client.add_new_test_case_step(issue_id, project_id, step, data,
                                                                              result).text

    def add_test_case(self, issue_id: int, project_id: int, steps_data: str):
        """ Adds test case's steps to corresponding jira ticket"""
        logger.info(f"Issue id: {issue_id}, project_id: {project_id}, Steps: {steps_data}")
        steps = json.loads(steps_data)
        return self.add_steps(issue_id, project_id, steps["steps"])

    def add_test_cases(self, create_test_cases_data: str):
        """ Adds test case's steps to corresponding jira tickets"""
        test_cases = json.loads(create_test_cases_data)
        return ",\n".join(self.add_steps(test_case['issue_id'], test_case['project_id'], test_case['steps']) for test_case in test_cases)

    def add_steps(self, issue_id: int, project_id: int, steps: list[dict[str, str]]):
        for step in steps:
            logger.info(f"Addition step: {step}")
            self.add_new_test_case_step(issue_id=issue_id, project_id=project_id, step=step["step"],
                                        data=step["data"], result=step["result"])
        return f"Done. Test issue was update with steps: {steps}"

    def get_available_tools(self):
        return [
            {
                "name": "get_test_case_steps",
                "description": self.get_test_case_steps.__doc__,
                "args_schema": ZephyrGetTestSteps,
                "ref": self.get_test_case_steps,
            },
            {
                "name": "add_new_test_case_step",
                "description": self.add_new_test_case_step.__doc__,
                "args_schema": ZephyrAddNewTestStep,
                "ref": self.add_new_test_case_step,
            },
            {
                "name": "add_test_case",
                "description": self.add_test_case.__doc__,
                "args_schema": ZephyrAddTestCase,
                "ref": self.add_test_case,
            },
            {
                "name": "add_test_cases",
                "description": self.add_test_cases.__doc__,
                "args_schema": ZephyrAddTestCases,
                "ref": self.add_test_cases,
            }
        ]
