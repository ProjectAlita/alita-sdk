from pydantic import BaseModel, Field, create_model
from typing import Optional

SalesforceCreateCase = create_model(
    "SalesforceCreateCase",
    subject=(str, Field(description="Subject of the case")),
    description=(str, Field(description="Description of the case")),
    origin=(str, Field(description="Case Origin (e.g., 'Web', 'Phone')")),
    status=(str, Field(description="Status of the case (e.g., 'New', 'Closed')"))
)

SalesforceCreateLead = create_model(
    "SalesforceCreateLead",
    last_name=(str, Field(description="Last Name of the Lead")),
    company=(str, Field(description="Company Name")),
    email=(str, Field(description="Email Address")),
    phone=(str, Field(description="Phone Number"))
)

SalesforceSearch = create_model(
    "SalesforceSearch",
    object_type=(str, Field(description="Salesforce Object Type (e.g., 'Case', 'Lead')")),
    query=(str, Field(description="SOQL query string"))
)

SalesforceUpdateCase = create_model(
    "SalesforceUpdateCase",
    case_id=(str, Field(description="Salesforce Case ID")),
    status=(str, Field(description="New Status of the Case")),
    description=(Optional[str], Field(description="Updated Description", default=""))
)

SalesforceUpdateLead = create_model(
    "SalesforceUpdateLead",
    lead_id=(str, Field(description="Salesforce Lead ID")),
    email=(Optional[str], Field(description="Updated Email", default="")),
    phone=(Optional[str], Field(description="Updated Phone Number", default=""))
)

SalesforceInput = create_model(
    "SalesforceInput",
    method=(str, Field(description="HTTP method (GET, POST, PATCH, DELETE)")),
    relative_url=(str, Field(description="Salesforce API relative URL (e.g., '/sobjects/Case/')")),
    params=(Optional[str], Field(default="{}", description="Optional JSON parameters for request body or query string"))
)

NoInput = create_model("NoInput")
