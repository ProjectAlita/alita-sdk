import pytest; pytest.skip("integration tests", allow_module_level=True)
import os
import pytest
from dotenv import load_dotenv

from elitea_analyse.git.git_search import GitLabV4Search


from ..alita_sdk.community.analysis.gitlab_analyse.api_wrapper import (
    GitLabProjectsListArgs,
    GitLabCommitsArgs, GitLabAnalyseWrapper
)

from ..alita_sdk.clients.client import AlitaClient
from ..alita_sdk.tools.artifact import ArtifactWrapper
from ..alita_sdk.community.utils import check_schema


# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def gitlab_api_wrapper():
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
        client=client, bucket=os.getenv("ARTIFACT_BUCKET_PATH", "analyse-gitlab")
    )
    check_schema(artifacts_wrapper)

    gitlab_url = os.getenv("GITLAB_URL")
    gitlab_token = os.getenv("GITLAB_TOKEN")

    if not gitlab_url or not gitlab_token:
        raise ValueError("Environment variables GITLAB_URL and GITLAB_TOKEN must be set.")

    gitlab_search = GitLabV4Search(
        url=gitlab_url,
        default_branch_name=os.getenv("GITLAB_DEFAULT_BRANCH", "master"),
        token=gitlab_token,
    )

    project_keys = os.getenv("GITLAB_JIRA_PROJECTS", "project1,project2")
    project_ids = os.getenv("GITLAB_PROJECTS_IDS", "123")

    gitlab_analyse_wrapper = GitLabAnalyseWrapper(
        artifacts_wrapper=artifacts_wrapper,
        jira_project_keys=project_keys,
        project_ids=project_ids,
        gitlab_search=gitlab_search,
    )
    check_schema(gitlab_analyse_wrapper)

    return gitlab_analyse_wrapper

def test_get_gitlab_projects_list(gitlab_api_wrapper):
    args = GitLabProjectsListArgs(date="2025-05-01")
    result = gitlab_api_wrapper.get_gitlab_projects_list(date=args.date)
    assert isinstance(result, str)
    assert "You have access to" in result

def test_get_gitlab_projects_that_in_jira(gitlab_api_wrapper):
    result = gitlab_api_wrapper.get_gitlab_projects_that_in_jira()
    assert isinstance(result, str)
    assert "GitLab projects that match Jira project names." in result

def test_get_gitlab_commits(gitlab_api_wrapper):
    project_ids = os.getenv("GITLAB_PROJECTS_IDS")
    if not project_ids:
        raise ValueError("Environment variable GITLAB_PROJECTS_IDS must be set.")

    args = GitLabCommitsArgs(project_ids=project_ids, since_date="2010-01-01")
    result = gitlab_api_wrapper.get_gitlab_commits(
        project_ids=args.project_ids, since_date=args.since_date
    )
    assert isinstance(result, str)
    assert f"Commits data for project {gitlab_api_wrapper.project_ids} has been saved. " in result


def test_get_gitlab_merge_requests(gitlab_api_wrapper):
    since_date = "2010-01-01"
    args = GitLabCommitsArgs(since_date=since_date)
    result = gitlab_api_wrapper.get_gitlab_merge_requests(project_ids=args.project_ids, since_date=args.since_date)
    assert isinstance(result, str)
    assert f"There are no merge requests in the project {gitlab_api_wrapper.project_ids} created after {since_date}"
