import logging

from .rest_client import ZephyrRestAPI

log = logging.getLogger(__name__)


class Zephyr(object):
    """
    Provide permission information for the current user.
    Reference: https://zephyrsquadserver.docs.apiary.io/
    """

    def __init__(self,
                 base_url,
                 username,
                 password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.request_client = ZephyrRestAPI(base_url=self.base_url,
                                            user_name=self.username,
                                            password=self.password)

    def get_test_case_steps(self, issue_id, project_id):
        """
        Returns the steps for a test case
        :param issue_id: int,
        :param project_id: int
        :return:
        """
        relative_path = f"/teststep/{issue_id}?projectId={project_id}"
        return self.request_client.request(method='GET', path=relative_path)

    def add_new_test_case_step(self, issue_id, project_id, step: str, data: str, result: str):
        """
        Adds new step for a test case
        :param issue_id: int,
        :param project_id: int
        :return:
        """
        relative_path = f"/teststep/{issue_id}?projectId={project_id}"
        body = {
            "step": step,
            "data": data,
            "result": result
        }
        return self.request_client.request(method='POST', path=relative_path, json=body)
