import requests


class RPClient():
    def __init__(self, endpoint: str, project: str, api_key: str):
        # strip endpoint from trailing slash
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.api_key = api_key
        self.project = project
        self._create_session_headers()

    def _create_session_headers(self):
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def export_specified_launch(self, launch_id: str, export_format: str):
        url = f"{self.endpoint}/api/v1/{self.project}/launch/{launch_id}/report"
        if export_format:
            url += f"?view={export_format}"

        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response

    def get_launch_details(self, launch_id):
        url = f"{self.endpoint}/api/v1/{self.project}/launch/{launch_id}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_all_launches(self, page_number: int):
        url = f"{self.endpoint}/api/v1/{self.project}/launch?page.page={page_number}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def find_test_item_by_id(self, item_id: str):
        url = f"{self.endpoint}/api/v1/{self.project}/item/{item_id}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_test_items_for_launch(self, launch_id: str, page_number: int):
        url = f"{self.endpoint}/api/v1/{self.project}/item?filter.eq.launchId={launch_id}&page.page={page_number}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_logs_for_test_items(self, item_id: str, page_number: int):
        url = f"{self.endpoint}/api/v1/{self.project}/log?filter.eq.item={item_id}&page.page={page_number}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_user_information(self, username: str):
        url = f"{self.endpoint}/api/users/{username}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_dashboard_data(self, dashboard_id: str):
        url = f"{self.endpoint}/api/v1/{self.project}/dashboard/{dashboard_id}"
        response = requests.request("GET", url, headers=self.headers)
        response.raise_for_status()

        return response.json()
