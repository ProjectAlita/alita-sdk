import os
import pytest
from dotenv import load_dotenv

from  ..alita_sdk.community.eda.jiratookit.api_wrapper import (EDAApiWrapper, 
                                                            GetJiraFieldsArgs, 
                                                            GetJiraIssuesArgs)
from ..alita_sdk.clients.client import AlitaClient
from ..alita_sdk.tools.artifact import ArtifactWrapper
from ..alita_sdk.community.eda.jira.jira_connect import connect_to_jira
from ..alita_sdk.community.utils import check_schema

# Load environment variables from .env file
load_dotenv()

@pytest.fixture
def eda_api_wrapper():
    client = AlitaClient(
        base_url=os.getenv("DEPLOYMENT_URL"),
        project_id=int(os.getenv("PROJECT_ID")),
        auth_token=os.getenv("API_KEY")
    )
    jira = connect_to_jira(
        jira_base_url=os.getenv("JIRA_SERVER"),
        jira_username=os.getenv("JIRA_USER"),
        jira_token=os.getenv("JIRA_TOKEN"),
        jira_api_key=os.getenv("JIRA_API_KEY"),
        jira_verify_ssl=False
    )
    artifacts_wrapper = ArtifactWrapper(client=client, bucket=os.getenv("ARTIFACT_BUCKET_PATH"))
    
    check_schema(artifacts_wrapper)
    eda_wrapper = EDAApiWrapper(
        artifacts_wrapper=artifacts_wrapper,
        jira=jira,
        closed_status=os.getenv("JIRA_CLOSED_STATUS"),
        defects_name=os.getenv("JIRA_DEFECTS_NAME"),
        custom_fields={}
    )
    check_schema(eda_wrapper)
    return eda_wrapper

def test_get_number_of_all_issues(eda_api_wrapper):
    args = GetJiraFieldsArgs(project_keys=os.getenv("JIRA_PROJECT"), after_date="2025-01-01")
    result = eda_api_wrapper.get_number_off_all_issues(args.project_keys, args.after_date)
    assert "projects" in result
    assert "projects_summary" in result

def test_get_all_jira_fields(eda_api_wrapper):
    args = GetJiraFieldsArgs(project_keys=os.getenv("JIRA_PROJECT"), after_date="2025-01-01")
    result = eda_api_wrapper.get_all_jira_fields(args.project_keys, args.after_date)
    assert "overall_stat" in result
    assert "issue_types_stat" in result

def test_get_jira_issues(eda_api_wrapper):
    args = GetJiraIssuesArgs(
        project_keys=os.getenv("JIRA_PROJECT"),
        closed_issues_based_on=1,
        resolved_after="2025-01-01",
        updated_after="2025-01-01",
        created_after="2025-01-01",
        add_filter=""
    )
    result = eda_api_wrapper.get_jira_issues(
        args.project_keys,
        args.closed_issues_based_on,
        args.resolved_after,
        args.updated_after,
        args.created_after,
        args.add_filter
    )
    assert "Data has been extracted successfully." in result
