import json
import logging
import re
import urllib.parse
from typing import Dict, List, Generator, Optional

from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v7_1.core import CoreClient
from azure.devops.v7_1.wiki import WikiClient
from azure.devops.v7_1.work_item_tracking import TeamContext, Wiql, WorkItemTrackingClient
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from msrest.authentication import BasicAuthentication
from pydantic import create_model, PrivateAttr, SecretStr
from pydantic import model_validator
from pydantic.fields import Field

from alita_sdk.tools.non_code_indexer_toolkit import NonCodeIndexerToolkit
from ...utils.content_parser import parse_file_content
from ....runtime.utils.utils import IndexerKeywords

logger = logging.getLogger(__name__)

create_wi_field = """JSON of the work item fields to create in Azure DevOps, i.e.
                    {
                       "fields":{
                          "System.Title":"Implement Registration Form Validation",
                          "field2":"Value 2",
                       }
                    }
                    """

# Input models for Azure DevOps operations
ADOWorkItemsSearch = create_model(
    "AzureDevOpsSearchModel",
    query=(str, Field(description="WIQL query for searching Azure DevOps work items")),
    limit=(Optional[int], Field(description="Number of items to return. IMPORTANT: Tool returns all items if limit=-1. If parameter is not provided then the value will be taken from tool configuration.", default=None)),
    fields=(Optional[list[str]], Field(description="Comma-separated list of requested fields", default=None))
)

ADOCreateWorkItem = create_model(
    "AzureDevOpsCreateWorkItemModel",
    work_item_json=(str, Field(description=create_wi_field)),
    wi_type=(Optional[str], Field(description="Work item type, e.g. 'Task', 'Issue' or  'EPIC'", default="Task"))
)

ADOUpdateWorkItem = create_model(
    "AzureDevOpsUpdateWorkItemModel",
    id=(str, Field(description="ID of work item required to be updated")),
    work_item_json=(str, Field(description=create_wi_field))
)

ADOGetWorkItem = create_model(
    "AzureDevOpsGetWorkItemModel",
    id=(int, Field(description="The work item id")),
    fields=(Optional[list[str]], Field(description="Comma-separated list of requested fields", default=None)),
    as_of=(Optional[str], Field(description="AsOf UTC date time string", default=None)),
    expand=(Optional[str], Field(description="The expand parameters for work item attributes. Possible options are { None, Relations, Fields, Links, All }.", default=None)),
    parse_attachments=(Optional[bool], Field(description="Value that defines is attachment should be parsed.", default=False)),
    image_description_prompt=(Optional[str],
                     Field(description="Prompt which is used for image description", default=None)),

)

ADOLinkWorkItem = create_model(
    "ADOLinkWorkItem",
    source_id=(int, Field(description="ID of the work item you plan to add link to")),
    target_id=(int, Field(description="ID of the work item linked to source one")),
    link_type=(str, Field(description="Link type: System.LinkTypes.Dependency-forward, etc.")),
    attributes=(Optional[dict], Field(description="Dict with attributes used for work items linking. Example: `comment`, etc. and syntax 'comment': 'Some linking comment'", default=None))
)

ADOGetLinkType = create_model(
    "ADOGetLinkType",
)

ADOGetComments = create_model(
    "ADOGetComments",
    work_item_id=(int, Field(description="The work item id")),
    limit_total=(Optional[int], Field(description="Max number of total comments to return", default=None)),
    include_deleted=(Optional[bool], Field(description="Specify if the deleted comments should be retrieved", default=False)),
    expand=(Optional[str], Field(description="The expand parameters for comments. Possible options are { all, none, reactions, renderedText, renderedTextOnly }.", default="none")),
    order=(Optional[str], Field(description="Order in which the comments should be returned. Possible options are { asc, desc }", default=None))
)

ADOLinkWorkItemsToWikiPage = create_model(
    "ADOLinkWorkItemsToWikiPage",
    work_item_ids=(List[int], Field(description="List of work item IDs to link to the wiki page")),
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    page_name=(str, Field(description="Wiki page path to link the work items to", examples=["/TargetPage"]))
)

ADOUnlinkWorkItemsFromWikiPage = create_model(
    "ADOUnlinkWorkItemsFromWikiPage",
    work_item_ids=(List[int], Field(description="List of work item IDs to unlink from the wiki page")),
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    page_name=(str, Field(description="Wiki page path to unlink the work items from", examples=["/TargetPage"]))
)

ADOGetWorkItemTypeFields = create_model(
    "ADOGetWorkItemTypeFields",
    work_item_type=(Optional[str], Field(description="Work item type to get fields for (e.g., 'Task', 'Bug', 'Test Case', 'Epic'). Default is 'Task'.", default="Task")),
    force_refresh=(Optional[bool], Field(description="If True, reload field definitions from Azure DevOps. Use this if project configuration has changed.", default=False))
)

class AzureDevOpsApiWrapper(NonCodeIndexerToolkit):
    # TODO use ado_configuration instead of organization_url, project and token
    organization_url: str
    project: str
    token: SecretStr
    limit: Optional[int] = 5
    _client: Optional[WorkItemTrackingClient] = PrivateAttr()
    _wiki_client: Optional[WikiClient] = PrivateAttr() # Add WikiClient instance
    _core_client: Optional[CoreClient] = PrivateAttr() # Add CoreClient instance
    _relation_types: Dict = PrivateAttr(default_factory=dict) # track actual relation types for instance
    _work_item_type_fields_cache: Dict[str, Dict] = PrivateAttr(default_factory=dict)  # Cache for work item type field definitions

    class Config:
        arbitrary_types_allowed = True  # Allow arbitrary types (e.g., WorkItemTrackingClient, WikiClient, CoreClient)

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        """Validate and set up the Azure DevOps client."""
        try:
            # Set up connection to Azure DevOps using Personal Access Token (PAT)
            credentials = BasicAuthentication('', values['token'])
            connection = Connection(base_url=values['organization_url'], creds=credentials)

            # Retrieve the work item tracking client and assign it to the private _client attribute
            cls._client = connection.clients_v7_1.get_work_item_tracking_client()
            cls._wiki_client = connection.clients_v7_1.get_wiki_client()
            cls._core_client = connection.clients_v7_1.get_core_client()

        except Exception as e:
            error_msg = str(e).lower()
            if "expired" in error_msg or "token" in error_msg and ("invalid" in error_msg or "unauthorized" in error_msg):
                raise ValueError(
                    "Azure DevOps connection failed: Your access token has expired or is invalid. "
                    "Please refresh your token in the toolkit configuration."
                )
            elif "401" in error_msg or "unauthorized" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Authentication failed. "
                    "Please check your credentials in the toolkit configuration."
                )
            elif "404" in error_msg or "not found" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Organization or project not found. "
                    "Please verify your organization URL and project name."
                )
            elif "timeout" in error_msg or "timed out" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Connection timed out. "
                    "Please check your network connection and try again."
                )
            else:
                raise ValueError(f"Azure DevOps connection failed: {e}")

        return super().validate_toolkit(values)

    def _parse_work_items(self, work_items, fields=None):
        """Parse work items dynamically based on the fields requested."""
        parsed_items = []

        # If no specific fields are provided, default to the basic ones
        if fields is None:
            fields = ["System.Title", "System.State", "System.AssignedTo", "System.WorkItemType", "System.CreatedDate",
                      "System.ChangedDate"]

        # Remove 'System.Id' from the fields list, as it's not a field you request, it's metadata
        fields = [field for field in fields if "System.Id" not in field]
        fields = [field for field in fields if "System.WorkItemType" not in field]
        for item in work_items:
            # Fetch full details of the work item, including the requested fields
            full_item = self._client.get_work_item(id=item.id, project=self.project, fields=fields)
            fields_data = full_item.fields

            # Parse the fields dynamically
            parsed_item = {"id": full_item.id, "url": f"{self.organization_url}/_workitems/edit/{full_item.id}"}

            # Iterate through the requested fields and add them to the parsed result
            for field in fields:
                parsed_item[field] = fields_data.get(field, "N/A")

            parsed_items.append(parsed_item)

        return parsed_items

    def _parse_validation_error(self, error_message: str) -> str:
        """
        Parse Azure DevOps validation errors and return a human-readable message.

        Args:
            error_message: The raw error message from Azure DevOps

        Returns:
            A formatted, human-readable error message
        """
        error_str = str(error_message)

        # Extract error code (e.g., TF401320)
        error_code_match = re.search(r'(TF\d+)', error_str)
        error_code = error_code_match.group(1) if error_code_match else "Validation Error"

        # Extract field name
        field_match = re.search(r'field\s+([^\s.]+(?:\s+[^\s.]+)*?)[\s.]', error_str, re.IGNORECASE)
        field_name = field_match.group(1) if field_match else "Unknown field"

        # Extract validation rule violations
        rule_violations = []
        if "Required" in error_str or "InvalidEmpty" in error_str:
            rule_violations.append("This field is required and cannot be empty")
        if "LimitedToValues" in error_str or "HasValues" in error_str:
            rule_violations.append("The value must be from the predefined allowed list")
        if "InvalidValue" in error_str:
            rule_violations.append("The provided value is invalid")
        if "InvalidFormat" in error_str:
            rule_violations.append("The value format is incorrect")
        if "InvalidType" in error_str:
            rule_violations.append("The value type is incorrect")

        # Count additional errors
        additional_errors_match = re.search(r'(\d+)\s+additional\s+errors?', error_str, re.IGNORECASE)
        additional_errors = int(additional_errors_match.group(1)) if additional_errors_match else 0

        # Build human-readable message
        message_parts = [
            f"❌ Work item validation failed ({error_code})",
            f"\n\n📋 Field: '{field_name}'"
        ]

        if rule_violations:
            message_parts.append("\n\n⚠️  Validation issues:")
            for i, violation in enumerate(rule_violations, 1):
                message_parts.append(f"\n  {i}. {violation}")

        if additional_errors > 0:
            message_parts.append(f"\n\n❗ {additional_errors} additional field(s) also have validation errors")

        message_parts.append("\n\n💡 Suggestions:")
        message_parts.append("\n  • Check that all required fields for this work item type are provided")
        message_parts.append("\n  • Ensure field values match the allowed values defined in your Azure DevOps process template")
        message_parts.append("\n  • Verify field names are correct (including custom fields)")
        message_parts.append(f"\n\n🔍 Original error: {error_str}")

        return "".join(message_parts)

    def _transform_work_item(self, work_item_json):
        try:
            # Convert the input JSON to a Python dictionary
            if isinstance(work_item_json, str):
                work_item_json = json.loads(work_item_json)
        except (json.JSONDecodeError, ValueError) as e:
            raise ToolException(f"Issues during attempt to parse work_item_json: {e}")

        if 'fields' not in work_item_json:
            raise ToolException("The 'fields' property is missing from the work_item_json.")

            # Transform the dictionary into a list of JsonPatchOperation objects
        patch_document = [
            {
                "op": "add",
                "path": f"/fields/{field}",
                "value": value
            }
            for field, value in work_item_json["fields"].items()
        ]
        return patch_document

    def create_work_item(self, work_item_json, wi_type="Task"):
        """Create a work item in Azure DevOps."""
        try:
            patch_document = self._transform_work_item(work_item_json)
        except Exception as e:
            return ToolException(f"Issues during attempt to parse work_item_json: {str(e)}")

        try:
            # Use the transformed patch_document to create the work item
            work_item = self._client.create_work_item(
                document=patch_document,
                project=self.project,
                type=wi_type
            )
            return {
                "id": work_item.id,
                "message": f"Work item {work_item.id} created successfully. View it at {work_item.url}."
            }
        except AzureDevOpsServiceError as e:
            error_str = str(e).lower()

            # Handle validation errors (TF401320, TF401316, etc.)
            if "rule error" in error_str or "validation" in error_str or any(code in str(e) for code in ["TF401320", "TF401316", "TF401319"]):
                readable_error = self._parse_validation_error(str(e))
                logger.error(f"Work item validation failed: {e}")
                return ToolException(readable_error)

            # Handle incorrect assignee errors
            if "unknown value" in error_str or "assigned to" in error_str:
                logger.error(f"Unable to create work item due to incorrect assignee: {e}")
                return ToolException(
                    f"❌ Unable to create work item: Invalid assignee specified.\n\n"
                    f"💡 Please verify the assignee email or display name exists in your Azure DevOps organization.\n\n"
                    f"🔍 Original error: {e}"
                )

            # Handle work item type errors
            if "type" in error_str and ("not found" in error_str or "does not exist" in error_str):
                logger.error(f"Unable to create work item: Invalid work item type: {e}")
                return ToolException(
                    f"❌ Unable to create work item: Work item type '{wi_type}' does not exist in project '{self.project}'.\n\n"
                    f"💡 Please use a valid work item type (e.g., 'Task', 'Bug', 'User Story', 'Epic').\n\n"
                    f"🔍 Original error: {e}"
                )

            # Generic Azure DevOps service error
            logger.error(f"Error creating work item: {e}")
            return ToolException(
                f"❌ Failed to create work item in Azure DevOps.\n\n"
                f"🔍 Error details: {e}\n\n"
                f"💡 Please check your work item fields and try again."
            )
        except Exception as e:
            logger.error(f"Unexpected error creating work item: {e}")
            return ToolException(f"Unexpected error creating work item: {e}")

    def update_work_item(self, id: str, work_item_json: str):
        """Updates existing work item per defined data"""

        try:
            patch_document = self._transform_work_item(work_item_json)
            work_item = self._client.update_work_item(id=id, document=patch_document, project=self.project)
            return f"Work item ({work_item.id}) was updated."
        except AzureDevOpsServiceError as e:
            error_str = str(e).lower()

            # Handle validation errors
            if "rule error" in error_str or "validation" in error_str or any(code in str(e) for code in ["TF401320", "TF401316", "TF401319"]):
                readable_error = self._parse_validation_error(str(e))
                logger.error(f"Work item validation failed: {e}")
                raise ToolException(readable_error)

            # Handle work item not found errors
            if "404" in error_str or "not found" in error_str or "does not exist" in error_str:
                logger.error(f"Work item not found: {e}")
                return ToolException(
                    f"❌ Work item with ID '{id}' not found in project '{self.project}'.\n\n"
                    f"💡 Please verify the work item ID exists and you have permission to access it.\n\n"
                    f"🔍 Original error: {e}"
                )

            # Handle incorrect assignee errors
            if "unknown value" in error_str or "assigned to" in error_str:
                logger.error(f"Unable to update work item due to incorrect assignee: {e}")
                return ToolException(
                    f"❌ Unable to update work item: Invalid assignee specified.\n\n"
                    f"💡 Please verify the assignee email or display name exists in your Azure DevOps organization.\n\n"
                    f"🔍 Original error: {e}"
                )

            # Generic Azure DevOps service error
            logger.error(f"Error updating work item: {e}")
            return ToolException(
                f"❌ Failed to update work item {id} in Azure DevOps.\n\n"
                f"🔍 Error details: {e}\n\n"
                f"💡 Please check your work item fields and try again."
            )
        except ToolException:
            # Re-raise ToolException as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating work item: {e}")
            return ToolException(f"Issues during attempt to update work item: {str(e)}")

    def get_relation_types(self) -> dict:
        """Returns dict of possible relation types per syntax: 'relation name': 'relation reference name'.
        NOTE: reference name is used for adding links to the work item"""

        if not self._relation_types:
            # have to be called only once for session
            relations = self._client.get_relation_types()
            for relation in relations:
                self._relation_types.update({relation.name: relation.reference_name})
        return self._relation_types

    def _get_work_item_type_fields(self, work_item_type: str) -> Dict:
        """
        Get field definitions for a specific work item type using the Azure DevOps client.

        Args:
            work_item_type: The work item type (e.g., 'Task', 'Bug', 'Test Case')

        Returns:
            dict: Mapping of field reference names to their metadata (name, type, required, allowed values)
        """
        try:
            # Use the WorkItemTrackingClient to get work item type fields
            work_item_type_obj = self._client.get_work_item_type(self.project, work_item_type)

            # Get fields for this work item type
            fields = work_item_type_obj.fields

            field_definitions = {}
            for field in fields:
                field_ref_name = field.reference_name
                field_definitions[field_ref_name] = {
                    'name': field.name,
                    'type': field.type if hasattr(field, 'type') else 'Unknown',
                    'required': field.always_required if hasattr(field, 'always_required') else False,
                    'allowed_values': field.allowed_values if hasattr(field, 'allowed_values') else [],
                    'description': field.help_text if hasattr(field, 'help_text') else ''
                }

            return field_definitions

        except Exception as e:
            logger.warning(f"Failed to fetch field definitions for work item type '{work_item_type}' using client: {e}")
            return {}

    def _format_work_item_type_fields_for_display(self, work_item_type: str, field_definitions: Dict) -> str:
        """
        Format field definitions in human-readable format for LLM.

        Args:
            work_item_type: The work item type name
            field_definitions: Output from _get_work_item_type_fields()

        Returns:
            Formatted string with field information
        """
        if not field_definitions:
            return f"Unable to retrieve field definitions for work item type '{work_item_type}'. Please check your Azure DevOps connection and permissions."

        output = [f"Available Fields for Work Item Type '{work_item_type}' in Project '{self.project}':\n"]
        output.append("=" * 80)

        # Separate required and optional fields
        required_fields = []
        optional_fields = []

        for ref_name, field_info in sorted(field_definitions.items()):
            field_entry = {
                'ref_name': ref_name,
                'name': field_info.get('name', ref_name),
                'type': field_info.get('type', 'Unknown'),
                'required': field_info.get('required', False),
                'allowed_values': field_info.get('allowed_values', [])
            }

            if field_entry['required']:
                required_fields.append(field_entry)
            else:
                optional_fields.append(field_entry)

        # Display required fields first
        if required_fields:
            output.append("\n📋 REQUIRED FIELDS:")
            output.append("-" * 80)
            for field in required_fields:
                output.append(f"\n✓ {field['name']} (Reference: {field['ref_name']})")
                output.append(f"  Type: {field['type']}")
                if field['allowed_values']:
                    output.append(f"  Allowed Values: {', '.join(str(v) for v in field['allowed_values'])}")

        # Display optional fields (common ones only)
        if optional_fields:
            output.append("\n\n📝 OPTIONAL FIELDS (Common):")
            output.append("-" * 80)
            # Show only commonly used optional fields
            common_fields = ['System.AssignedTo', 'System.AreaPath', 'System.IterationPath',
                           'Microsoft.VSTS.Common.Priority', 'System.Tags', 'System.State']
            for field in optional_fields:
                if field['ref_name'] in common_fields:
                    output.append(f"\n  {field['name']} (Reference: {field['ref_name']})")
                    output.append(f"    Type: {field['type']}")
                    if field['allowed_values']:
                        output.append(f"    Allowed Values: {', '.join(str(v) for v in field['allowed_values'])}")

        output.append("\n\n" + "=" * 80)
        output.append("\n💡 Usage Instructions:")
        output.append("  • Use the 'Reference' name (e.g., 'System.Title') as the field key in work_item_json")
        output.append("  • Provide all required fields when creating work items")
        output.append("  • For fields with allowed values, use exact value from the list")
        output.append(f"  • Example for {work_item_type}: " + '{"fields": {"System.Title": "My title", "CustomField": "Value"}}')

        return '\n'.join(output)

    def get_work_item_type_fields(self, work_item_type: str = "Task", force_refresh: bool = False) -> str:
        """
        Get formatted information about available fields for a specific work item type.
        This method helps discover which fields are required for work item creation.

        Args:
            work_item_type: The work item type to get fields for (e.g., 'Task', 'Bug', 'Test Case', 'Epic').
                           Default is 'Task'.
            force_refresh: If True, reload field definitions from Azure DevOps instead of using cache.
                          Use this if project configuration has changed (new fields added, etc.).

        Returns:
            Formatted string with field names, types, and requirements
        """
        cache_key = work_item_type

        if force_refresh or cache_key not in self._work_item_type_fields_cache:
            self._work_item_type_fields_cache[cache_key] = self._get_work_item_type_fields(work_item_type)

        return self._format_work_item_type_fields_for_display(work_item_type, self._work_item_type_fields_cache[cache_key])

    def link_work_items(self, source_id, target_id, link_type, attributes: dict = None):
        """Add the relation to the source work item with an appropriate attributes if any. User may pass attributes like name, etc."""

        if not self._relation_types:
            # check cached relation types and trigger its collection if it is empty by that moment
            self.get_relation_types()
        if link_type not in self._relation_types.values():
            return ToolException(f"Link type is incorrect. You have to use proper relation's reference name NOT relation's name: {self._relation_types}")

        relation = {
            "rel": link_type,
            "url": f"{self.organization_url}/_apis/wit/workItems/{target_id}"
        }

        if attributes:
            relation.update({"attributes": attributes})

        try:
            self._client.update_work_item(
                document=[
                    {
                        "op": "add",
                        "path": "/relations/-",
                        "value": relation
                    }
                ],
                id=source_id
            )
        except Exception as e:
            logger.error(f"Error linking work items: {e}")
            return ToolException(f"Error linking work items: {e}")

        return f"Work item {source_id} linked to {target_id} with link type {link_type}"

    def search_work_items(self, query: str, limit: int = None, fields=None):
        """Search for work items using a WIQL query and dynamically fetch fields based on the query."""
        try:
            # Create a Wiql object with the query
            wiql = Wiql(query=query)

            # Validate that the Azure DevOps client is initialized
            if not self._client:
                raise ToolException("Azure DevOps client not initialized.")
            logger.info(f"Search for work items using {query}")
            # Execute the WIQL query
            if not limit:
                limit = self.limit
            work_items = self._client.query_by_wiql(wiql, top=None if limit < 0 else limit, team_context=TeamContext(project=self.project)).work_items

            if not work_items:
                return "No work items found."

            # Parse the work items and fetch the fields dynamically
            parsed_work_items = self._parse_work_items(work_items, fields)

            # Return the parsed work items
            return parsed_work_items
        except ValueError as ve:
            logger.error(f"Invalid WIQL query: {ve}")
            return ToolException(f"Invalid WIQL query: {ve}")
        except Exception as e:
            logger.error(f"Error searching work items: {e}")
            return ToolException(f"Error searching work items: {e}")

    def parse_attachment_by_url(self, attachment_url, file_name=None, image_description_prompt=None):
        match = re.search(r'attachments/([\w-]+)(?:\?fileName=([^&]+))?', attachment_url)
        if match:
            attachment_id = match.group(1)
            if not file_name:
                file_name = match.group(2)
            if not file_name:
                raise ToolException("File name must be provided either in the URL or as a parameter.")
            return self.parse_attachment_by_id(attachment_id, file_name, image_description_prompt)
        raise ToolException(f"Attachment '{attachment_url}' was not found.")

    def parse_attachment_by_id(self, attachment_id, file_name, image_description_prompt):
        file_content = self.get_attachment_content(attachment_id)
        return parse_file_content(file_content=file_content, file_name=file_name,
                                            llm=self.llm, prompt=image_description_prompt)

    def get_work_item(self, id: int, fields: Optional[list[str]] = None, as_of: Optional[str] = None, expand: Optional[str] = None, parse_attachments=False, image_description_prompt=None):
        """Get a single work item by ID."""
        try:
            # Validate that the Azure DevOps client is initialized
            if not self._client:
                raise ToolException("Azure DevOps client not initialized.")

            # Fetch the work item
            work_item = self._client.get_work_item(id=id, project=self.project, fields=fields, as_of=as_of, expand=expand)

            # Parse the fields dynamically
            fields_data = work_item.fields
            parsed_item = {"id": work_item.id, "url": f"{self.organization_url}/_workitems/edit/{work_item.id}"}

            # Iterate through the requested fields and add them to the parsed result
            if fields:
                for field in fields:
                    parsed_item[field] = fields_data.get(field, "N/A")
            else:
                parsed_item.update(fields_data)

            # extract relations if any
            relations_data = None
            if expand and str(expand).lower() in ("relations", "all"):
                try:
                    relations_data = getattr(work_item, 'relations', None)
                except KeyError:
                    relations_data = None
            if relations_data:
                parsed_item['relations'] = [relation.as_dict() for relation in relations_data]

            if parse_attachments:
                # describe images in work item fields if present
                for field_name, field_value in fields_data.items():
                    if isinstance(field_value, str):
                        soup = BeautifulSoup(field_value, 'html.parser')
                        images = soup.find_all('img')
                        for img in images:
                            src = img.get('src')
                            if src:
                                description = self.parse_attachment_by_url(src, image_description_prompt=image_description_prompt)
                                img['image-description'] = description
                        parsed_item[field_name] = str(soup)
                # parse attached documents if present
                for relation in parsed_item.get('relations', []):
                    # Only process actual file attachments
                    if relation.get('rel') == 'AttachedFile':
                        file_name = relation.get('attributes', {}).get('name')
                        if file_name:
                            try:
                                relation['content'] = self.parse_attachment_by_url(relation['url'], file_name, image_description_prompt=image_description_prompt)
                            except Exception as att_e:
                                logger.warning(f"Failed to parse attachment {file_name}: {att_e}")


            return parsed_item
        except Exception as e:
            logger.error(f"Error getting work item: {e}")
            return ToolException(f"Error getting work item: {e}")


    def get_comments(self, work_item_id: int, limit_total: Optional[int] = None, include_deleted: Optional[bool] = None, expand: Optional[str] = None, order: Optional[str] = None):
        """Get comments for work item by ID."""
        try:
            # Validate that the Azure DevOps client is initialized
            if not self._client:
                raise ToolException("Azure DevOps client not initialized.")

            # Resolve limits to extract in single portion and for whole set of comment
            limit_portion = self.limit
            limit_all = limit_total if limit_total else self.limit

            # Fetch the work item comments
            comments_portion = self._client.get_comments(project=self.project, work_item_id=work_item_id, top=limit_portion, include_deleted=include_deleted, expand=expand, order=order)
            comments_all = []

            while True:
                comments_all += [comment.as_dict() for comment in comments_portion.comments]

                if not comments_portion.continuation_token or len(comments_all) >= limit_all:
                    return comments_all[:limit_all]
                else:
                    comments_portion = self._client.get_comments(continuation_token=comments_portion.continuation_token, project=self.project, work_item_id=int(work_item_id), top=3, include_deleted=include_deleted, expand=expand, order=order)
        except Exception as e:
            logger.error(f"Error getting work item comments: {e}")
            return ToolException(f"Error getting work item comments: {e}")

    def _get_wiki_artifact_uri(self, wiki_identified: str, page_name: str) -> str:
        """Helper method to construct the artifact URI for a wiki page."""
        if not self._wiki_client:
            raise ToolException("Wiki client not initialized.")
        if not self._core_client:
            raise ToolException("Core client not initialized.")

        # 1. Get Project ID
        project_details = self._core_client.get_project(self.project)
        if not project_details or not project_details.id:
            raise ToolException(f"Could not retrieve project details or ID for project '{self.project}'.")
        project_id = project_details.id
        # logger.info(f"Found project ID: {project_id}")

        # 2. Get Wiki ID
        wiki_details = self._wiki_client.get_wiki(project=self.project, wiki_identifier=wiki_identified)
        if not wiki_details or not wiki_details.id:
            raise ToolException(f"Could not retrieve wiki details or ID for wiki '{wiki_identified}'.")
        wiki_id = wiki_details.id
        # logger.info(f"Found wiki ID: {wiki_id}")

        # 3. Get Wiki Page
        wiki_page = self._wiki_client.get_page(project=self.project, wiki_identifier=wiki_identified, path=page_name)

        # 4. Construct the Artifact URI
        url = f"{project_id}/{wiki_id}{wiki_page.page.path}"
        encoded_url = urllib.parse.quote(url, safe="")
        artifact_uri = f"vstfs:///Wiki/WikiPage/{encoded_url}"
        # logger.info(f"Constructed Artifact URI: {artifact_uri}")
        return artifact_uri

    def link_work_items_to_wiki_page(self, work_item_ids: List[int], wiki_identified: str, page_name: str):
        """Links one or more work items to a specific wiki page using an ArtifactLink."""
        if not work_item_ids:
            return "No work item IDs provided. No links created."
        if not self._client:
            return ToolException("Work item client not initialized.")

        try:
            # 1. Get Artifact URI using helper method
            artifact_uri = self._get_wiki_artifact_uri(wiki_identified, page_name)

            # 2. Define the relation payload using the Artifact URI
            relation = {
                "rel": "ArtifactLink",
                "url": artifact_uri,
                "attributes": {"name": "Wiki Page"} # Standard attribute for wiki links
            }

            patch_document = [
                {
                    "op": 0,
                    "path": "/relations/-",
                    "value": relation
                }
            ]

            # 3. Update each work item
            successful_links = []
            failed_links = {}
            for work_item_id in work_item_ids:
                try:
                    self._client.update_work_item(
                        document=patch_document,
                        id=work_item_id,
                        project=self.project # Assuming work items are in the same project
                    )
                    successful_links.append(str(work_item_id))
                    # logger.info(f"Successfully linked work item {work_item_id} to wiki page '{page_name}'.")
                except Exception as update_e:
                    error_msg = f"Failed to link work item {work_item_id}: {str(update_e)}"
                    logger.error(error_msg)
                    failed_links[str(work_item_id)] = str(update_e)

            # 4. Construct response message
            response = ""
            if successful_links:
                response += f"Successfully linked work items [{', '.join(successful_links)}] to wiki page '{page_name}' in wiki '{wiki_identified}'.\n"
            if failed_links:
                response += f"Failed to link work items: {json.dumps(failed_links)}"

            return response.strip()

        except Exception as e:
            logger.error(f"Error linking work items to wiki page '{page_name}': {str(e)}")
            return ToolException(f"An unexpected error occurred while linking work items to wiki page '{page_name}': {str(e)}")

    def unlink_work_items_from_wiki_page(self, work_item_ids: List[int], wiki_identified: str, page_name: str):
        """Unlinks one or more work items from a specific wiki page by removing the ArtifactLink."""
        if not work_item_ids:
            return "No work item IDs provided. No links removed."
        if not self._client:
            return ToolException("Work item client not initialized.")

        try:
            # 1. Get Artifact URI using helper method
            artifact_uri = self._get_wiki_artifact_uri(wiki_identified, page_name)

            # 2. Process each work item to remove the link
            successful_unlinks = []
            failed_unlinks = {}
            no_link_found = []

            for work_item_id in work_item_ids:
                try:
                    # Get the work item with its relations
                    work_item = self._client.get_work_item(id=work_item_id, project=self.project, expand='Relations')
                    if not work_item or not work_item.relations:
                        no_link_found.append(str(work_item_id))
                        logger.info(f"Work item {work_item_id} has no relations. Skipping unlink.")
                        continue

                    # Find the index of the relation to remove
                    relation_index_to_remove = -1
                    for i, relation in enumerate(work_item.relations):
                        if relation.rel == "ArtifactLink" and relation.url == artifact_uri:
                            relation_index_to_remove = i
                            break

                    if relation_index_to_remove == -1:
                        no_link_found.append(str(work_item_id))
                        # logger.info(f"No link to wiki page '{page_name}' found on work item {work_item_id}.")
                        continue

                    # Create the patch document to remove the relation by index
                    patch_document = [
                        {
                            "op": "remove", # Use "remove" operation
                            "path": f"/relations/{relation_index_to_remove}"
                        }
                    ]

                    # Update the work item
                    self._client.update_work_item(
                        document=patch_document,
                        id=work_item_id,
                        project=self.project
                    )
                    successful_unlinks.append(str(work_item_id))
                    logger.info(f"Successfully unlinked work item {work_item_id} from wiki page '{page_name}'.")

                except Exception as update_e:
                    error_msg = f"Failed to unlink work item {work_item_id}: {str(update_e)}"
                    logger.error(error_msg)
                    failed_unlinks[str(work_item_id)] = str(update_e)

            # 5. Construct response message
            response = ""
            if successful_unlinks:
                response += f"Successfully unlinked work items [{', '.join(successful_unlinks)}] from wiki page '{page_name}' in wiki '{wiki_identified}'.\n"
            if no_link_found:
                 response += f"No link to wiki page '{page_name}' found for work items [{', '.join(no_link_found)}].\n"
            if failed_unlinks:
                response += f"Failed to unlink work items: {json.dumps(failed_unlinks)}"

            return response.strip() if response else "No action taken or required."

        except Exception as e:
            logger.error(f"Error unlinking work items from wiki page '{page_name}': {str(e)}")
            return ToolException(f"An unexpected error occurred while unlinking work items from wiki page '{page_name}': {str(e)}")

    def _base_loader(self, wiql: str, **kwargs) -> Generator[Document, None, None]:
        ref_items = self._client.query_by_wiql(Wiql(query=wiql)).work_items
        for ref in ref_items:
            wi = self._client.get_work_item(id=ref.id, project=self.project, expand='all')
            yield Document(page_content=json.dumps(wi.fields), metadata={
                'id': str(wi.id),
                'type': wi.fields.get('System.WorkItemType', ''),
                'title': wi.fields.get('System.Title', ''),
                'state': wi.fields.get('System.State', ''),
                'area': wi.fields.get('System.AreaPath', ''),
                'reason': wi.fields.get('System.Reason', ''),
                'iteration': wi.fields.get('System.IterationPath', ''),
                'updated_on': wi.fields.get('System.ChangedDate', ''),
                'attachment_ids': {rel.url.split('/')[-1]:rel.attributes.get('name', '') for rel in wi.relations or [] if rel.rel == 'AttachedFile'}
            })

    def get_attachment_content(self, attachment_id):
        content_generator = self._client.get_attachment_content(id=attachment_id, download=True)
        return b"".join(content_generator)

    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        raw_attachment_ids = document.metadata.get('attachment_ids', {})

        # Normalize attachment_ids: accept dict or JSON string, raise otherwise
        if isinstance(raw_attachment_ids, str):
            try:
                loaded = json.loads(raw_attachment_ids)
            except json.JSONDecodeError:
                raise TypeError(
                    f"Expected dict or JSON string for 'attachment_ids', got non-JSON string for id="
                    f"{document.metadata.get('id')}: {raw_attachment_ids!r}"
                )
            if not isinstance(loaded, dict):
                raise TypeError(
                    f"'attachment_ids' JSON did not decode to dict for id={document.metadata.get('id')}: {loaded!r}"
                )
            attachment_ids = loaded
        elif isinstance(raw_attachment_ids, dict):
            attachment_ids = raw_attachment_ids
        else:
            raise TypeError(
                f"Expected 'attachment_ids' to be dict or JSON string, got {type(raw_attachment_ids)} "
                f"for id={document.metadata.get('id')}: {raw_attachment_ids!r}"
            )

        for attachment_id, file_name in attachment_ids.items():
            content = self.get_attachment_content(attachment_id=attachment_id)
            yield Document(
                page_content="",
                metadata={
                    'id': attachment_id,
                    IndexerKeywords.CONTENT_FILE_NAME.value: file_name,
                    IndexerKeywords.CONTENT_IN_BYTES.value: content,
                },
            )

    def _index_tool_params(self):
        """Return the parameters for indexing data."""
        return {
            "wiql": (str, Field(description="WIQL (Work Item Query Language) query string to select and filter Azure DevOps work items."))
        }

    def get_available_tools(self):
        """Return a list of available tools."""
        return super().get_available_tools() + [
            {
                "name": "search_work_items",
                "description": self.search_work_items.__doc__,
                "args_schema": ADOWorkItemsSearch,
                "ref": self.search_work_items,
            },
            {
                "name": "create_work_item",
                "description": self.create_work_item.__doc__,
                "args_schema": ADOCreateWorkItem,
                "ref": self.create_work_item,
            },
            {
                "name": "update_work_item",
                "description": self.update_work_item.__doc__,
                "args_schema": ADOUpdateWorkItem,
                "ref": self.update_work_item,
            },
            {
                "name": "get_work_item",
                "description": self.get_work_item.__doc__,
                "args_schema": ADOGetWorkItem,
                "ref": self.get_work_item,
            },
            {
                "name": "link_work_items",
                "description": self.link_work_items.__doc__,
                "args_schema": ADOLinkWorkItem,
                "ref": self.link_work_items,
            },
            {
                "name": "get_relation_types",
                "description": self.get_relation_types.__doc__,
                "args_schema": ADOGetLinkType,
                "ref": self.get_relation_types,
            },
            {
                "name": "get_comments",
                "description": self.get_comments.__doc__,
                "args_schema": ADOGetComments,
                "ref": self.get_comments,
            },
            {
                "name": "link_work_items_to_wiki_page",
                "description": self.link_work_items_to_wiki_page.__doc__,
                "args_schema": ADOLinkWorkItemsToWikiPage,
                "ref": self.link_work_items_to_wiki_page,
            },
            {
                "name": "unlink_work_items_from_wiki_page",
                "description": self.unlink_work_items_from_wiki_page.__doc__,
                "args_schema": ADOUnlinkWorkItemsFromWikiPage,
                "ref": self.unlink_work_items_from_wiki_page,
            },
            {
                "name": "get_work_item_type_fields",
                "description": self.get_work_item_type_fields.__doc__,
                "args_schema": ADOGetWorkItemTypeFields,
                "ref": self.get_work_item_type_fields,
            }
        ]
