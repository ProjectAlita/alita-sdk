import logging
import json
from typing import Optional, Any

from pyral import Rally
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator, SecretStr
from pydantic.fields import PrivateAttr
from langchain_core.tools import ToolException

from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

create_entity_field = """JSON of the artifact fields to create in Rally, i.e. for `Defect`
                     {
                       "Name":"Random Defect",
                       "Description":"This is a randomly generated defect for testing purposes.",
                       "Severity":"Major Problem",
                       "Priority":"High Attention",
                       "State":"Open",
                       "Environment":"Production",
                       "FoundInBuild":"1.0.0",
                       "FixedInBuild":"1.0.1",
                       "ScheduleState":"Defined",
                       "Owner":"Engineer"
                       }
                     """

update_entity_field = """JSON of the artifact fields to update in Rally, i.e.
                     {
                        "FormattedID": "DE1234",
                        "Description": "Updated description of the defect",
                        "ScheduleState": "In-Progress"
                     }
                     """

# Input models for Rally operations
RallyGetEntities = create_model(
    "RallyGetStoriesModel",
    entity_type=(Optional[str], Field(description="Artifact type, e.g. 'HierarchicalRequirement', 'Defect', 'UserStory'", default="UserStory")),
    query=(Optional[str], Field(description="Query for searching Rally stories", default=None)),
    fetch=(Optional[bool], Field(description="Whether to fetch the full details of the stories", default=True)),
    limit=(Optional[int], Field(description="Limit the number of results", default=10))
)

RallyGetProject = create_model(
    "RallyGetProjectModel",
    project_name=(Optional[str], Field(
        description="Name of the project to retrieve or default one will be used in case it is not passed",
        default=None))
)

RallyGetWorkspace = create_model(
    "RallyGetWorkspaceModel",
    workspace_name=(Optional[str], Field(
        description="Name of the workspace to retrieve or default one will be used in case it is not passed",
        default=None))
)

RallyGetUser = create_model(
    "RallyGetUserModel",
    user_name=(Optional[str], Field(
        description="Username of the user to retrieve or default one will be used in case it is not passed",
        default=None))
)

RallyNoInputModel = create_model(
    "RallyNoInputModel"
)

RallyCreateArtifact = create_model(
    "RallyCreateArtifactModel",
    entity_json=(str, Field(description=create_entity_field)),
    entity_type=(Optional[str], Field(description="Artifact type, e.g. 'HierarchicalRequirement', 'Defect', 'UserStory'", default='HierarchicalRequirement'))
)

RallyUpdateArtifact = create_model(
    "RallyUpdateArtifactModel",
    entity_json=(str, Field(description=update_entity_field)),
    entity_type=(
        Optional[str], Field(description="Artifact type, e.g. 'HierarchicalRequirement', 'Defect', 'UserStory'", default=None))
)


# Toolkit API wrapper
class RallyApiWrapper(BaseToolApiWrapper):
    server: str
    api_key: Optional[SecretStr] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    workspace: Optional[str] = None
    project: Optional[str] = None
    _client: Optional[Rally] = PrivateAttr()  # Private attribute for the Rally client

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow arbitrary types (e.g., Rally)

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        """Validate and set up the Rally client."""
        try:
            if (not values.get('username') or not values.get('password')) and not values.get('api_key'):
                raise ToolException(
                    "Either user and password or api_key must be defined to establish connection with Rally.")
            # Set up connection to Rally
            cls._client = Rally(server=values['server'], user=values.get('username'), password=values.get('password'),
                                apikey=values.get('api_key'), workspace=values.get('workspace'),
                                project=values.get('project'))
        except Exception as e:
            raise ToolException(f"Failed to connect to Rally: {e}")

        return values

    # Tool declaration
    def get_types(self):
        """Get available entity types from Rally."""
        try:
            names = []
            for item in self._client.get("TypeDefinition", fetch='ElementName').content['QueryResult']['Results']:
                name = item.get('ElementName', "")
                if name:
                    names.append(name)
            return f"Extracted entities: {names}"
        except Exception as e:
            logger.error(f"Error getting stories: {e}")
            return ToolException(f"Error getting stories: {e}")

    def get_entities(self, entity_type: str = "UserStory", query=None, fetch=True, limit=10):
        """Get user stories from Rally."""
        try:
            response = self._client.get(entity_type, query=query, fetch=fetch, limit=limit)
            # extra limit since API doesn't limit the results output
            return f"Extracted entities: {response.content['QueryResult']['Results'][:limit]}"
        except Exception as e:
            logger.error(f"Error getting stories: {e}")
            return ToolException(f"Error getting stories: {e}")

    def get_project(self, project_name=None):
        """Get a project from Rally by name."""
        try:
            if not project_name:
                # undefined project name
                project_name = self.project
            response = self._client.get('Project', query=f'Name = "{project_name}"')
            return str(response.content['QueryResult']['Results'])
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return ToolException(f"Error getting project: {e}")

    def get_workspace(self, workspace_name=None):
        """Get a workspace from Rally by name."""
        try:
            if not workspace_name:
                # undefined ws name
                workspace_name = self.workspace
            response = self._client.get('Workspace', query=f'Name = "{workspace_name}"')
            return str(response.content['QueryResult']['Results'])
        except Exception as e:
            logger.error(f"Error getting workspace: {e}")
            return ToolException(f"Error getting workspace: {e}")

    def get_user(self, user_name=None):
        """Get a user from Rally by username."""
        try:
            if not user_name:
                user_name_query = None
            else:
                user_name_query = f'UserName = "{user_name}"'
            response = self._client.get('User', query=user_name_query)
            if response.content is not None:
                if 'User' in response.content:
                    return str(response.content['User'])
                else:
                    return str(response.content)
            else:
                return "Undefined"
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return ToolException(f"Error getting user: {e}")

    def get_context(self):
        """Get a user from Rally by username."""
        try:
            return f"Project: {self.get_project()}\nWorkspace: {self.get_workspace()}\nUser: {self.get_user()}"
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return ToolException(f"Error getting user: {e}")

    def create_entity(self, entity_json: str, entity_type="HierarchicalRequirement"):
        """Create an artifact in Rally."""
        try:
            # Convert the input JSON to a Python dictionary
            params = json.loads(entity_json)
        except (json.JSONDecodeError, ValueError) as e:
            return ToolException(f"Issues during attempt to parse artifact_json: {e}")

        try:
            # Validate that the Rally client is initialized
            if not self._client:
                return ToolException("Rally client not initialized.")

            # Use the params to create the artifact
            artifact = self._client.create(entity_type, params)
            return f"Entity {artifact.FormattedID} created successfully."
        except Exception as e:
            logger.error(f"Error creating artifact: {e}")
            return ToolException(f"Error creating artifact: {e}")

    def update_entity(self, entity_json: str, entity_type: str = None):
        """Update an artifact in Rally."""
        try:
            # Convert the input JSON to a Python dictionary
            params = json.loads(entity_json)
        except (json.JSONDecodeError, ValueError) as e:
            return ToolException(f"Issues during attempt to parse artifact_json: {e}")

        if not entity_type:
            return ToolException(
                "Please define entity type ('Story', 'UserStory', 'User Story', etc.). Or you can call tool get_types to get available types.")

        try:
            # Validate that the Rally client is initialized
            if not self._client:
                return ToolException("Rally client not initialized.")

            # Use the params to update the artifact
            artifact = self._client.update(entity_type, params)
            return f"Artifact {artifact.FormattedID} updated successfully."
        except Exception as e:
            logger.error(f"Error updating artifact: {e}")
            return ToolException(f"Error updating artifact: {e}")

    # list of available tools for a toolkit
    def get_available_tools(self):
        """Return a list of available tools."""
        return [
            {
                "name": "get_types",
                "description": self.get_types.__doc__,
                "args_schema": RallyNoInputModel,
                "ref": self.get_types,
            },
            {
                "name": "get_entities",
                "description": self.get_entities.__doc__,
                "args_schema": RallyGetEntities,
                "ref": self.get_entities,
            },
            {
                "name": "get_project",
                "description": self.get_project.__doc__,
                "args_schema": RallyGetProject,
                "ref": self.get_project,
            },
            {
                "name": "get_workspace",
                "description": self.get_workspace.__doc__,
                "args_schema": RallyGetWorkspace,
                "ref": self.get_workspace,
            },
            {
                "name": "get_user",
                "description": self.get_user.__doc__,
                "args_schema": RallyGetUser,
                "ref": self.get_user,
            },
            {
                "name": "get_context",
                "description": self.get_context.__doc__,
                "args_schema": RallyNoInputModel,
                "ref": self.get_context,
            },
            {
                "name": "create_artifact",
                "description": self.create_entity.__doc__,
                "args_schema": RallyCreateArtifact,
                "ref": self.create_entity,
            },
            {
                "name": "update_artifact",
                "description": self.update_entity.__doc__,
                "args_schema": RallyUpdateArtifact,
                "ref": self.update_entity,
            }
        ]