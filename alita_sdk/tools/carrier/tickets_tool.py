import logging
import json
import traceback
from datetime import datetime
from typing import Type, Optional, List
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel, ValidationError, field_validator
from .api_wrapper import CarrierAPIWrapper


logger = logging.getLogger(__name__)


class TicketData(BaseModel):
    """
    Model describing the structure for creating a ticket.

    Required fields:
      - title
      - description
      - severity
      - type
      - engagement
      - board_id
      - start_date
      - end_date

    Optional fields:
      - external_link
      - assignee
      - tags
    """

    # Required fields
    title: str = Field(..., description="Title of the ticket.")
    description: str = Field(..., description="Detailed description of the ticket.")
    severity: str = Field(..., description="Severity level, e.g., 'Critical', 'High', 'Medium', 'Low'.")
    type: str = Field(..., description="Type of ticket, e.g., 'Activity', 'Bug', 'Task'.")
    engagement: Optional[str] = Field(None, description="Engagement ID (e.g., f09b73a0-c547-426a-aeef-...)")
    board_id: str = Field(..., description="ID of the board where the ticket is created.")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format.")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format.")

    # Optional fields
    external_link: Optional[str] = Field(None, description="External link for added context.")
    assignee: Optional[str] = Field(None, description="User to whom the ticket is assigned, e.g. 'Select'")
    tags: Optional[List[str]] = Field(None, description="List of tags to add to the ticket.")

    # Validate date strings to ensure user is providing them in a correct format
    @field_validator("start_date", "end_date", mode="before")
    def validate_date_format(cls, value, info):
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a string in YYYY-MM-DD format.")
        try:
            # Attempt to parse
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid date format for {info.field_name}. Expected 'YYYY-MM-DD', got '{value}'."
            )
        return value


#
# 2) CREATE TICKET TOOL
#

class CreateTicketTool(BaseTool):
    """
    Tool that expects top-level fields for the ticket (e.g. 'title', 'description'),
    rather than a 'ticket_data' dict. This matches your invocation style:

    {
      "title": "Perf Ticket",
      "description": "DO what you must",
      "severity": "Medium",
      "type": "Task",
      "board_id": "4",
      "start_date": "2023-03-13",
      "end_date": "2025-03-30",
      "assignee": "Karen"
    }
    """
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "create_ticket"
    description: str = (
        "Create a new ticket on Carrier with required fields: "
        "title, description, severity, type, board_id, start_date, end_date. "
        "Optional: external_link, engagement, assignee, tags."
    )

    # We specify TicketData as the schema, telling LangChain each field is top-level:
    args_schema: Type[BaseModel] = TicketData

    def _run(self, **fields):
        """
        Execution logic when this tool is called with top-level fields
        (title, description, severity, etc.) as separate arguments.
        """
        # 1) If no fields at all were provided
        required_fields = ['title', 'description', 'severity', 'type', 'engagement', 'board_id', 'start_date', 'end_date']

        if not fields:
            error_msg = (
                "🚨 It looks like you haven't provided ticket data.\n"
                f"**Required fields**: {', '.join(required_fields)}\n"
                "Optional fields: external_link, engagement, assignee, tags\n"
                "💡 Example usage:\n"
                "{\n"
                "  'title': 'My Example Ticket',\n"
                "  'description': 'Details of the issue...',\n"
                "  'severity': 'High',\n"
                "  'type': 'Bug',\n"
                "  'engagement': 'Carrier',\n"
                "  'board_id': '123'\n"
                "  'start_date': '2025-03-27', 'end_date': '2025-03-29'\n"
                "}\n"
            )
            logger.warning(error_msg)
            raise ToolException(error_msg)

        # Set correct engagement
        engagement_name = fields.get("engagement")
        engagements = self.api_wrapper.get_engagements_list()

        engagement_hash = next(
            (e["hash_id"] for e in engagements if e.get("name") == engagement_name),
            engagement_name  # fallback to original if not found
        )

        fields["engagement"] = engagement_hash

        # 2) Validate using the TicketData Pydantic schema
        try:
            validated_ticket = TicketData.model_validate(fields)
        except ValidationError as ve:
            missing_fields = [err['loc'][0] for err in ve.errors() if err['type'] == 'missing']
            error_msg = (
                f"🚨 Validation error for ticket data.\n"
                f"**Missing or invalid fields**: {', '.join(missing_fields)}\n"
                "Please correct these fields and try again."
            )
            logger.warning(error_msg)
            raise ToolException(error_msg)

        # 3) Attempt to create the ticket
        try:
            payload = validated_ticket.model_dump(exclude_none=True)

            response = self.api_wrapper.create_ticket(payload)

            # Optionally confirm 'item' in the response or status
            if not response or "item" not in response:
                error_msg = (
                    "🚨 The server did not return a valid ticket structure.\n"
                    f"Full response:\n{response}"
                )
                logger.warning(error_msg)
                raise ToolException(error_msg)

            success_msg = (
                "✅ Ticket created successfully!\n"
                f"{json.dumps(response, indent=2)}"
            )
            logger.info(success_msg)
            return success_msg
        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Error creating ticket: {stacktrace}")
            raise ToolException(
                "🚨 Server returned an error while creating the ticket. "
                "Please verify your data, credentials, or engagement permissions.\n"
                f"Original error: {str(e)}"
            )


class FetchTicketsTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_ticket_list"
    description: str = "Fetch tickets from a specific board."
    args_schema: Type[BaseModel] = create_model(
        "FetchTicketsInput",
        board_id=(str, Field(description="Board ID from which tickets will be fetched")),
        tag_name=(str, Field(default="", description="Tag name from which tickets titles will be fetched")),
        status=(str, Field(default="", description="Status for tickets titles will be fetched"))
    )

    def _run(self, board_id: str, tag_name="", status=""):
        try:
            tickets = self.api_wrapper.fetch_tickets(board_id)

            # Filter tickets by status and tag
            if tag_name:
                tickets = [
                    ticket for ticket in tickets
                    if any(tag["tag"] == tag_name.lower() for tag in ticket["tags"])
                ]
            if status:
                tickets = [
                    ticket for ticket in tickets
                    if ticket["status"] == status
                ]

            return f"\n".join(ticket["title"] for ticket in tickets)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error fetching tickets: {stacktrace}")
            raise ToolException(stacktrace)
