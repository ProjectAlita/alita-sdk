import requests

class ZephyrEssentialAPI:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _do_request(self, method: str, api_path: str, json: dict = None, params: dict = None, headers: dict = None, files=None):
        url = f"{self.base_url}{api_path}"
        headers = headers or {}
        headers.update({
            "Authorization": f"Bearer {self.token}",
            **({"Content-Type": "application/json"} if json else {})
        })
        try:
            resp = requests.request(method=method, url=url, headers=headers, json=json, params=params, files=files)
            resp.raise_for_status()
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                return resp.json()
            return resp.text
        except requests.RequestException as e:
            raise Exception(f"Error performing request {method} {api_path}: {str(e)}")

    # Test Cases
    def list_test_cases(self, project_key=None, folder_id=None, max_results=10, start_at=0):
        params = {
            "projectKey": project_key,
            "folderId": folder_id,
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", "/testcases", params=params)

    def create_test_case(self, test_case_data):
        return self._do_request("POST", "/testcases", json=test_case_data)

    def get_test_case(self, test_case_key):
        return self._do_request("GET", f"/testcases/{test_case_key}")

    def update_test_case(self, test_case_key, test_case_data):
        return self._do_request("PUT", f"/testcases/{test_case_key}", json=test_case_data)

    def get_test_case_links(self, test_case_key):
        return self._do_request("GET", f"/testcases/{test_case_key}/links")

    def create_test_case_issue_link(self, test_case_key, issue_link_data):
        return self._do_request("POST", f"/testcases/{test_case_key}/links/issues", json=issue_link_data)

    def create_test_case_web_link(self, test_case_key, web_link_data):
        return self._do_request("POST", f"/testcases/{test_case_key}/links/weblinks", json=web_link_data)

    def list_test_case_versions(self, test_case_key, max_results=10, start_at=0):
        params = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", f"/testcases/{test_case_key}/versions", params=params)

    def get_test_case_version(self, test_case_key, version):
        return self._do_request("GET", f"/testcases/{test_case_key}/versions/{version}")

    def get_test_case_test_script(self, test_case_key):
        return self._do_request("GET", f"/testcases/{test_case_key}/testscript")

    def create_test_case_test_script(self, test_case_key, test_script_data):
        return self._do_request("POST", f"/testcases/{test_case_key}/testscript", json=test_script_data)

    def get_test_case_test_steps(self, test_case_key, max_results=10, start_at=0):
        params = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", f"/testcases/{test_case_key}/teststeps", params=params)

    def create_test_case_test_steps(self, test_case_key, test_steps_data):
        return self._do_request("POST", f"/testcases/{test_case_key}/teststeps", json=test_steps_data)

    # Test Cycles
    def list_test_cycles(self, project_key=None, folder_id=None, jira_project_version_id=None, max_results=10, start_at=0):
        params = {
            "projectKey": project_key,
            "folderId": folder_id,
            "jiraProjectVersionId": jira_project_version_id,
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", "/testcycles", params=params)

    def create_test_cycle(self, test_cycle_data):
        return self._do_request("POST", "/testcycles", json=test_cycle_data)

    def get_test_cycle(self, test_cycle_id_or_key):
        return self._do_request("GET", f"/testcycles/{test_cycle_id_or_key}")

    def update_test_cycle(self, test_cycle_id_or_key, test_cycle_data):
        return self._do_request("PUT", f"/testcycles/{test_cycle_id_or_key}", json=test_cycle_data)

    def get_test_cycle_links(self, test_cycle_id_or_key):
        return self._do_request("GET", f"/testcycles/{test_cycle_id_or_key}/links")

    def create_test_cycle_issue_link(self, test_cycle_id_or_key, issue_link_data):
        return self._do_request("POST", f"/testcycles/{test_cycle_id_or_key}/links/issues", json=issue_link_data)

    def create_test_cycle_web_link(self, test_cycle_id_or_key, web_link_data):
        return self._do_request("POST", f"/testcycles/{test_cycle_id_or_key}/links/weblinks", json=web_link_data)

    # Test Executions
    def list_test_executions(self, project_key=None, test_cycle=None, test_case=None, max_results=10, start_at=0):
        params = {
            "projectKey": project_key,
            "testCycle": test_cycle,
            "testCase": test_case,
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", "/testexecutions", params=params)

    def create_test_execution(self, test_execution_data):
        return self._do_request("POST", "/testexecutions", json=test_execution_data)

    def get_test_execution(self, test_execution_id_or_key):
        return self._do_request("GET", f"/testexecutions/{test_execution_id_or_key}")

    def update_test_execution(self, test_execution_id_or_key, test_execution_data):
        return self._do_request("PUT", f"/testexecutions/{test_execution_id_or_key}", json=test_execution_data)

    def get_test_execution_test_steps(self, test_execution_id_or_key, max_results=10, start_at=0):
        params = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", f"/testexecutions/{test_execution_id_or_key}/teststeps", params=params)

    def update_test_execution_test_steps(self, test_execution_id_or_key, test_steps_data):
        return self._do_request("PUT", f"/testexecutions/{test_execution_id_or_key}/teststeps", json=test_steps_data)

    def sync_test_execution_script(self, test_execution_id_or_key):
        return self._do_request("POST", f"/testexecutions/{test_execution_id_or_key}/teststeps/sync")

    def list_test_execution_links(self, test_execution_id_or_key):
        return self._do_request("GET", f"/testexecutions/{test_execution_id_or_key}/links")

    def create_test_execution_issue_link(self, test_execution_id_or_key, issue_link_data):
        return self._do_request("POST", f"/testexecutions/{test_execution_id_or_key}/links/issues", json=issue_link_data)

    # Projects
    def list_projects(self, max_results=10, start_at=0):
        params = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", "/projects", params=params)

    def get_project(self, project_id_or_key):
        return self._do_request("GET", f"/projects/{project_id_or_key}")

    # Folders
    def list_folders(self, project_key=None, folder_type=None, max_results=10, start_at=0):
        params = {
            "projectKey": project_key,
            "folderType": folder_type,
            "maxResults": max_results,
            "startAt": start_at,
        }
        return self._do_request("GET", "/folders", params=params)

    def create_folder(self, folder_data):
        return self._do_request("POST", "/folders", json=folder_data)

    def get_folder(self, folder_id):
        return self._do_request("GET", f"/folders/{folder_id}")

    # Links
    def delete_link(self, link_id):
        return self._do_request("DELETE", f"/links/{link_id}")

    # Issue Links
    def get_issue_link_test_cases(self, issue_key):
        return self._do_request("GET", f"/issuelinks/{issue_key}/testcases")

    def get_issue_link_test_cycles(self, issue_key):
        return self._do_request("GET", f"/issuelinks/{issue_key}/testcycles")

    def get_issue_link_test_plans(self, issue_key):
        return self._do_request("GET", f"/issuelinks/{issue_key}/testplans")

    def get_issue_link_test_executions(self, issue_key):
        return self._do_request("GET", f"/issuelinks/{issue_key}/executions")

    # Automations
    def create_custom_executions(self, project_key, files, auto_create_test_cases=False):
        params = {
            "projectKey": project_key,
            "autoCreateTestCases": auto_create_test_cases,
        }
        return self._do_request("POST", "/automations/executions/custom", params=params, files=files)

    def create_cucumber_executions(self, project_key, files, auto_create_test_cases=False):
        params = {
            "projectKey": project_key,
            "autoCreateTestCases": auto_create_test_cases,
        }
        return self._do_request("POST", "/automations/executions/cucumber", params=params, files=files)

    def create_junit_executions(self, project_key, files, auto_create_test_cases=False):
        params = {
            "projectKey": project_key,
            "autoCreateTestCases": auto_create_test_cases,
        }
        return self._do_request("POST", "/automations/executions/junit", params=params, files=files)

    def retrieve_bdd_test_cases(self, project_key):
        headers = {"Accept": "application/zip"}
        params = {"projectKey": project_key}
        return self._do_request("GET", "/automations/testcases", params=params, headers=headers)

    # Healthcheck
    def healthcheck(self):
        return self._do_request("GET", "/healthcheck")