import requests
from pydantic import SecretStr

# TODO: Minimal client to perform calls, needed features for full functionality:
#  create_incident, update_incident

class ServiceNowClient(object):
    username: str
    password: SecretStr
    base_url: str
    def __init__(self, username: str, password: SecretStr, base_url: str):
        self.username = username
        self.password = password
        self.base_url = base_url

        # Start of general urls used by ServiceNow API
        self.incidents_url = f"{self.base_url}/api/now/table/incident"

    def get_incidents(self, args: dict):
        """Retrieve incidents from ServiceNow by category"""
        # TODO: The query parameters generation should be delegated to a separate function.
        #  Code meant to be refactored.
        # ^ operator at the end of a query without a following condition gets ignored, this enables us to not worry about
        # ending a query with an ^ operator without any follow-up.
        # This same rule applies to sysparam_query and & operators.
        category = args.get("category")
        description = args.get("description")
        creation_date = args.get("creation_date")
        number_of_entries = args.get("number_of_entries")

        endpoint_url = f"{self.incidents_url}"
        endpoint_url += f"?sysparm_query="

        if category:
            endpoint_url += f"category={category}^"

        if description:
            endpoint_url += f"descriptionLIKE{description}^"

        if creation_date:
            endpoint_url += f"sys_created_onLIKE{creation_date}^"

        if number_of_entries:
            endpoint_url += f"&sysparm_limit={number_of_entries}"
        response = requests.get(
            url=endpoint_url,
            auth=(self.username, self.password.get_secret_value()),
            headers={"Content-Type": "application/json", "Accept": "application/json"}
        )
        return response

    def create_incident(self, args: dict):
        """Creates new incidents in ServiceNow"""
        endpoint_url = f"{self.incidents_url}"
        update_dict = {}
        for key, value in args.items():
            if value is not None:
                update_dict[key] = value
        response = requests.post(
            url=endpoint_url,
            auth=(self.username, self.password.get_secret_value()),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            data=f'{update_dict}'
        )
        return response

    def update_incident(self, args: dict):
        """Updates an incident in ServiceNow"""
        endpoint_url = f"{self.incidents_url}"
        update_dict = {}
        incident_id = args.get("sys_id")
        if not incident_id:
            raise ValueError("incident_id is required")
        endpoint_url += f"/{incident_id}"
        args.pop("sys_id")
        for key, value in args.items():
            if value is not None:
                update_dict[key] = value
        response = requests.patch(
            url=endpoint_url,
            auth=(self.username, self.password.get_secret_value()),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            data=f'{update_dict}'
        )
        return response
