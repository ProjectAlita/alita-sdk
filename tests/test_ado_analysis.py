import pytest; pytest.skip("integration tests", allow_module_level=True)
import os
import pytest
from dotenv import load_dotenv

from elitea_analyse.ado.azure_search import AzureSearch

from ..alita_sdk.community.analysis.ado_analyse.api_wrapper import (
    GetAdoWorkItemsArgs, AdoCommitsArgs, AdoAnalyseWrapper)

from ..alita_sdk.clients.client import AlitaClient
from ..alita_sdk.tools.artifact import ArtifactWrapper
from ..alita_sdk.community.utils import check_schema

# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def ado_api_wrapper():
    base_url = os.getenv("DEPLOYMENT_URL")
    project_id = os.getenv("PROJECT_ID")
    api_key = os.getenv("API_KEY")

    if not base_url or not project_id or not api_key:
        raise ValueError("Environment variables DEPLOYMENT_URL, PROJECT_ID, and API_KEY must be set.")

    client = AlitaClient(
        base_url=base_url,
        project_id=int(project_id),
        auth_token=api_key,
    )

    artifacts_wrapper = ArtifactWrapper(
        client=client, bucket=os.getenv("ARTIFACT_BUCKET_PATH", "analyse-ado")
    )
    check_schema(artifacts_wrapper)
    ado_search = AzureSearch(
        organization=os.getenv("ADO_ORGANIZATION", "john.doe@epam.com"),
        user=os.getenv("ADO_USER", "ado_user"),
        token=os.getenv("ADO_TOKEN", "1111"),
    )

    ado_wrapper = AdoAnalyseWrapper(
        artifacts_wrapper=artifacts_wrapper,
        project_keys=os.getenv("ADO_PROJECTS", "project1,project2"),
        default_branch_name=os.getenv("ADO_DEFAULT_BRANCH", "main"),
        area=os.getenv("ADO_AREA", ""),
        ado_search=ado_search,
    )
    check_schema(ado_wrapper)

    return ado_wrapper

def test_get_projects_list(ado_api_wrapper):
    result = ado_api_wrapper.get_projects_list()
    assert isinstance(result, str)
    assert "You have access to" in result

def test_get_work_items(ado_api_wrapper):
    args = GetAdoWorkItemsArgs(
        resolved_after="2023-01-01",
        updated_after="2023-01-01",
        created_after="2023-01-01",
    )
    result = ado_api_wrapper.get_work_items(
        resolved_after=args.resolved_after,
        updated_after=args.updated_after,
        created_after=args.created_after,
        area=args.area,
        project_keys=args.project_keys
    )
    assert isinstance(result, str)
    assert f"Work items for {ado_api_wrapper.project_keys} have been successfully retrieved and saved to the bucket" in result

@pytest.mark.asyncio
async def test_get_commits(ado_api_wrapper):
    args = AdoCommitsArgs(
        since_date="2023-01-01",
    )

    result = await ado_api_wrapper.get_commits(since_date=args.since_date)
    # breakpoint()
    assert isinstance(result, str)
    assert f"Commits for {ado_api_wrapper.project_keys} have been successfully" in result


def test_get_merge_requests(ado_api_wrapper):
    args = AdoCommitsArgs(
        since_date="2023-01-01",
    )

    result = ado_api_wrapper.get_merge_requests(since_date=args.since_date)
    assert isinstance(result, str)
    assert f"Pull requests for {ado_api_wrapper.project_keys} have been successfully retrieved" in result

def test_get_pipelines_runs(ado_api_wrapper):
    result = ado_api_wrapper.get_pipelines_runs()
    assert isinstance(result, str)
    assert f"Pipeline runs for {ado_api_wrapper.project_keys} have been successfully retrieved " in result
