import hashlib
import json
import time

import jwt
import requests
from langchain_core.tools import ToolException


class ZephyrSquadCloud(object):
    """
    Reference: https://zephyrsquad.docs.apiary.io//
    """

    def __init__(self, account_id, access_key, secret_key):
        self.account_id = account_id
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = "https://prod-api.zephyr4jiracloud.com/connect"

    def get_test_step(self, issue_id, step_id, project_id):
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}/{step_id}?projectId={project_id}"
        return self._do_request(method="GET", api_path=api_path)

    def update_test_step(self, issue_id, step_id, project_id, json):
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}/{step_id}?projectId={project_id}"
        return self._do_request(method="PUT", api_path=api_path, json=json)

    def delete_test_step(self, issue_id, step_id, project_id):
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}/{step_id}?projectId={project_id}"
        return self._do_request(method="DELETE", api_path=api_path)

    def create_new_test_step(self, issue_id, project_id, json):
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}?projectId={project_id}"
        return self._do_request(method="POST", api_path=api_path, json=json)

    def get_all_test_steps(self, issue_id, project_id):
        api_path = f"/public/rest/api/2.0/teststep/{issue_id}?projectId={project_id}"
        return self._do_request(method='GET', api_path=api_path)

    def get_all_test_step_statuses(self):
        api_path = "/public/rest/api/1.0/teststep/statuses"
        return self._do_request(method='GET', api_path=api_path)

    def get_bdd_content(self, issue_id):
        api_path = f"/public/rest/api/1.0/integration/bddcontent/{issue_id}"
        return self._do_request(method='GET', api_path=api_path)

    def update_bdd_content(self, issue_id, new_content: str):
        api_path = f"/public/rest/api/1.0/integration/bddcontent/{issue_id}"
        return self._do_request(method='POST', api_path=api_path, json=json.dumps({"content": new_content}))

    def delete_bdd_content(self, issue_id):
        api_path = f"/public/rest/api/1.0/integration/bddcontent/{issue_id}"
        return self._do_request(method='DELETE', api_path=api_path, json="[]")

    def create_new_cycle(self, json):
        api_path = f"public/rest/api/1.0/cycle"
        return self._do_request(method='POST', api_path=api_path, json=json)

    def create_folder(self, json):
        api_path = f"/public/rest/api/1.0/folder"
        return self._do_request(method='POST', api_path=api_path, json=json)

    def add_test_to_cycle(self, cycle_id, json):
        api_path = f"/public/rest/api/1.0/executions/add/cycle/{cycle_id}"
        return self._do_request(method='POST', api_path=api_path, json=json)

    def add_test_to_folder(self, folder_id, json):
        api_path = f"/public/rest/api/1.0/executions/add/folder/{folder_id}"
        return self._do_request(method='POST', api_path=api_path, json=json)

    def create_execution(self, json):
        api_path = f"/public/rest/api/1.0/execution"
        return self._do_request(method='POST', api_path=api_path, json=json)

    def get_execution(self, execution_id, issue_id, project_id):
        api_path = f"/public/rest/api/1.0/execution/{execution_id}?issueId={issue_id}&projectId={project_id}"
        return self._do_request(method='GET', api_path=api_path)

    def _do_request(self, method, api_path, json=None):
        url = f"{self.base_url}{api_path}"
        headers = {
            "Authorization": f"JWT {self._generate_jwt_token(method, api_path)}",
            "zapiAccessKey": self.access_key
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        params = {"method": method, "url": url, "headers": headers}
        if json is not None:
            params["data"] = json

        try:
            resp = requests.request(**params)

            if resp.ok:
                if resp.headers.get("Content-Type", "").startswith("application/json"):
                    return str(resp.json())
                else:
                    return resp.text
            else:
                raise ToolException(f"Request failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            raise ToolException(f"Error performing request {method}:{api_path}: {e}")

    def _generate_jwt_token(self, method, path):
        canonical_path = f"{method}&{path}".replace('?', '&')

        if '&' not in path and '?' not in path:
            canonical_path += '&'

        payload_token = {
            'sub': self.account_id,
            'qsh': hashlib.sha256(canonical_path.encode('utf-8')).hexdigest(),
            'iss': self.access_key,
            'exp': int(time.time()) + 300,
            'iat': int(time.time())
        }
        return jwt.encode(payload_token, self.secret_key, algorithm='HS256').strip()
