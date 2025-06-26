import hashlib
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
        canonical_path = "/public/rest/api/1.0/teststep/issueId/id?projectId="
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}/{step_id}?projectId={project_id}"
        return self._do_request(method="GET", api_path=api_path, canonical_path=canonical_path)

    def update_test_step(self, issue_id, step_id, project_id, json):
        canonical_path = "/public/rest/api/1.0/teststep/issueId/id?projectId="
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}/{step_id}?projectId={project_id}"
        return self._do_request(method="PUT", api_path=api_path, canonical_path=canonical_path, json=json)

    def delete_test_step(self, issue_id, step_id, project_id):
        canonical_path = "/public/rest/api/1.0/teststep/issueId/id?projectId="
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}/{step_id}?projectId={project_id}"
        return self._do_request(method="DELETE", api_path=api_path, canonical_path=canonical_path)

    def create_new_test_step(self, issue_id, project_id, json):
        canonical_path = "/public/rest/api/1.0/teststep/issueId?projectId="
        api_path = f"/public/rest/api/1.0/teststep/{issue_id}?projectId={project_id}"
        return self._do_request(method="POST", api_path=api_path, canonical_path=canonical_path, json=json)

    def get_all_test_steps(self, issue_id, project_id):
        canonical_path = "/public/rest/api/2.0/teststep/issueId?projectId="
        api_path = f"/public/rest/api/2.0/teststep/{issue_id}?projectId={project_id}"
        return self._do_request(method='GET', api_path=api_path, canonical_path=canonical_path)

    def get_all_test_step_statuses(self):
        api_path = "/public/rest/api/1.0/teststep/statuses"
        return self._do_request(method='GET', api_path=api_path)

    def _do_request(self, method, api_path, canonical_path=None, json=None):
        url = f"{self.base_url}{api_path}"
        headers = {
            "Authorization": f"JWT {self._generate_jwt_token(method, canonical_path or api_path)}",
            "zapiAccessKey": self.access_key,
            "Content-Type": "application/json"
        }

        try:
            resp = requests.request(method=method, url=url, json=json, headers=headers)

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
        canonical_path = f"{method}&{path}&"
        payload_token = {
            'sub': self.account_id,
            'qsh': hashlib.sha256(canonical_path.encode('utf-8')).hexdigest(),
            'iss': self.access_key,
            'exp': int(time.time()) + 3600,
            'iat': int(time.time())
        }
        return jwt.encode(payload_token, self.secret_key, algorithm='HS256').strip()
