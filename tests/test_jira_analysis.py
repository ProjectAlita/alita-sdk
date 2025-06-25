import pytest; pytest.skip("integration tests", allow_module_level=True)
import os
from unittest.mock import patch
import pytest
from dotenv import load_dotenv

from elitea_analyse.jira.jira_connect import connect_to_jira
from ..alita_sdk.community.analysis.jira_analyse.api_wrapper import (
    JiraAnalyseWrapper,
    GetJiraFieldsArgs,
    GetJiraIssuesArgs,
)
from ..alita_sdk.clients.client import AlitaClient
from ..alita_sdk.tools.artifact import ArtifactWrapper
from ..alita_sdk.community.utils import check_schema

# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def jira_api_wrapper():
    base_url = os.getenv("DEPLOYMENT_URL")
    project_id = os.getenv("PROJECT_ID")
    api_key = os.getenv("API_KEY")
    artifact_bucket_path = os.getenv("ARTIFACT_BUCKET_PATH", "analyse-jira")

    if not base_url or not project_id or not api_key:
        raise ValueError("Environment variables DEPLOYMENT_URL, PROJECT_ID, and API_KEY must be set.")

    client = AlitaClient(
        base_url=base_url,
        project_id=int(project_id),
        auth_token=api_key,
    )

    artifacts_wrapper = ArtifactWrapper(client=client, bucket=artifact_bucket_path)
    check_schema(artifacts_wrapper)

    jira_credentials = {
        "username": os.getenv("JIRA_USER"),
        "base_url": os.getenv("JIRA_SERVER"),
        "token": os.getenv("JIRA_TOKEN"),
        "api_key": os.getenv("JIRA_API_KEY"),
        "verify_ssl": False,
    }
    jira = connect_to_jira(credentials=jira_credentials)
    if not jira:
        raise ValueError("Failed to connect to Jira. Please check your credentials.")

    jira_wrapper = JiraAnalyseWrapper(
        artifacts_wrapper=artifacts_wrapper,
        jira=jira,
        closed_status=os.getenv("JIRA_CLOSED_STATUS", "Done"),
        defects_name=os.getenv("JIRA_DEFECTS_NAME", "Defect"),
        custom_fields={"team": "", "defects_environment": ""},
        project_keys=os.getenv("JIRA_PROJECT", "CARRIER"),
    )
    check_schema(jira_wrapper)
    return jira_wrapper


def test_get_number_of_all_issues(jira_api_wrapper):
    with patch(
        "src.alita_sdk.community.analysis.jira_analyse.api_wrapper.dispatch_custom_event",
        return_value=None,
    ):
        args = GetJiraFieldsArgs(
            project_keys=os.getenv("JIRA_PROJECT"), after_date="2025-01-01"
        )
        result = jira_api_wrapper.get_number_off_all_issues(
            args.project_keys, args.after_date
        )
        assert "projects" in result
        assert "projects_summary" in result


def test_get_jira_issues(jira_api_wrapper):
    with patch(
        "src.alita_sdk.community.analysis.jira_analyse.api_wrapper.dispatch_custom_event",
        return_value=None,
    ):
        args = GetJiraIssuesArgs(
            project_keys=os.getenv("JIRA_PROJECT"),
            closed_issues_based_on=1,
            resolved_after="2025-01-01",
            updated_after="2025-01-01",
            created_after="2025-01-01",
            add_filter="",
        )
        result = jira_api_wrapper.get_jira_issues(
            closed_issues_based_on=args.closed_issues_based_on,
            resolved_after=args.resolved_after,
            updated_after=args.updated_after,
            created_after=args.created_after,
            project_keys=args.project_keys,
            add_filter=args.add_filter,
        )
        assert "Data has been extracted successfully." in result
