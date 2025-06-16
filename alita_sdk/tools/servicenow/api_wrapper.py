import logging

import json
from typing import Optional, Dict, Any

from pydantic import Field, model_validator, create_model, SecretStr
from pysnc import ServiceNowClient
from pysnc.record import GlideElement, GlideRecord

from langchain_core.tools import ToolException
from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

getIncidents = create_model(
    "getIncidents",
    data=(Optional[Dict[str, Any]], Field(
        description=(
            "A dictionary containing filters to retrieve incidents. Can be empty to retrieve all incidents. "
            "Possible keys include: category, description, number_of_entries (int), "
            "creation_date (YYYY-MM-DD), sys_id, number"
        ),
        default={},
        examples=[{"description": "Network issue", "category": "network"}]
    ))
)

createIncident = create_model(
    "createIncident",
    data=(Optional[Dict[str, Any]], Field(
        description=(
            "The dictionary of fields used to create an incident. Can be empty to create a default incident."
            "Possible fields include: category, description, short_description, impact, incident_state, urgency, "
            "and assignment_group."
        ),
        default={}
    ))
)

updateIncident = create_model(
    "updateIncident",
    sys_id=(str, Field(description="Sys ID of the incident")),
    update_fields=(str, Field(description="JSON string of fields to update. Possible fields include: "
                                                    "category, description, short_description, impact, incident_state, "
                                                    "urgency, and assignment_group.")
                   )
)

class ServiceNowAPIWrapper(BaseToolApiWrapper):
    base_url: str
    password: SecretStr
    username: str

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        base_url = values['base_url']
        password = SecretStr(values['password'])
        username = values['username']
        cls.fields = values.get('fields', ['sys_id', 'number', 'state', 'short_description', 'description', 'priority', 'category', 'urgency', 'impact', 'creation_date'])
        cls.client = ServiceNowClient(base_url, (username, password.get_secret_value()))
        return values

    def get_incidents(self, data: Optional[Dict[str, Any]] = None) -> ToolException | str:
        """Retrieves incidents from the ServiceNow database based on the provided filters."""

        try:
            data = data or {}
            gr = self.client.GlideRecord('incident')
            gr.limit = data.get('number_of_entries', 100)
            gr.fields = self.fields
            for filter, value in data.items():
                if value is not None:
                    if filter == 'description':
                        gr.add_query('description', 'CONTAINS', value)
                    else:
                        gr.add_query(filter, value)
            gr.query()
            incidents = self.parse_glide_results(gr._GlideRecord__results)
            return json.dumps(incidents)
        except Exception as e:
            return ToolException(f"ServiceNow tool exception. {e}")

    def parse_glide_results(self, results):
        parsed = []
        for item in results:
            parsed_item = {k: (v.get_value() if isinstance(v, GlideElement) else v)
                           for k, v in item.items()}
            parsed.append(parsed_item)
        return parsed

    def create_incident(self, data: Optional[Dict[str, str]] = {}) -> ToolException | str:
        """Creates a new incident on the ServiceNow database."""
        try:
            gr = self.client.GlideRecord('incident')
            gr.initialize()
            self._update_record(gr, data)

            gr.insert()
            incidents = self.parse_glide_results(gr._GlideRecord__results)
            return json.dumps(incidents)
        except Exception as e:
            return ToolException(f"ServiceNow tool exception. {e}")

    def update_incident(self, sys_id: str, update_fields: str) -> ToolException | str:
        """Updates an existing incident on the ServiceNow database per the provided sys_id and
         data describing the fields to update.

        Args:
            sys_id (str): The sys_id of the incident to update.
            update_fields (str): A JSON string containing the fields to update. Possible fields include:
            category, description, short_description, impact, incident_state, urgency, and assignment_group.
         """
        try:
            gr = self.client.GlideRecord('incident')
            if not gr.get(sys_id):
                return ToolException(f"Incident with sys_id '{sys_id}' not found")
            self._update_record(gr, json.loads(update_fields))
            gr.update()
            incidents = self.parse_glide_results(gr._GlideRecord__results)
            return json.dumps(incidents)
        except Exception as e:
            return ToolException(f"ServiceNow tool exception. {e}")

    def _update_record(self, gr: GlideRecord, data: dict):
        for field, value in data.items():
            if value is not None:
                try:
                    gr.set_value(field, value)
                except AttributeError as e:
                    raise ToolException(f"Warning: Cannot set field '{field}': {e}")

    def get_available_tools(self):
        return [
            {
                "name": "get_incidents",
                "ref": self.get_incidents,
                "description": self.get_incidents.__doc__,
                "args_schema": getIncidents,
            },
            {
                "name": "create_incident",
                "ref": self.create_incident,
                "description": self.create_incident.__doc__,
                "args_schema": createIncident,
            },
            {
                "name": "update_incident",
                "ref": self.update_incident,
                "description": self.update_incident.__doc__,
                "args_schema": updateIncident,
            }
        ]