import pytest; pytest.skip("integration tests", allow_module_level=True)
import os
from unittest.mock import patch
import pytest
from dotenv import load_dotenv

from elitea_analyse.github.github_org import GitHubGetOrgLvl
from ..alita_sdk.community.analysis.github_analyse.api_wrapper import (
  GetGithubCommitsFromReposArgs, GetGithubRepositoriesListArgs, GitHubAnalyseWrapper
)

from ..alita_sdk.clients.client import AlitaClient
from ..alita_sdk.tools.artifact import ArtifactWrapper
from ..alita_sdk.community.utils import check_schema


# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def github_api_wrapper():
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

    owner = os.getenv("GITHUB_OWNER")
    token = os.getenv("GITHUB_TOKEN")
    if not owner or not token:
        raise ValueError("GitHub owner and token are required")

    git = GitHubGetOrgLvl(owner, token)

    github_wrapper = GitHubAnalyseWrapper(
        artifacts_wrapper=artifacts_wrapper,
        repos=os.getenv("GITHUB_REPOS", ""),
        git=git
    )

    check_schema(github_wrapper)

    return github_wrapper

def test_get_commits_from_repos(github_api_wrapper):
    args = GetGithubCommitsFromReposArgs(since_after="2025-06-01")
    result = github_api_wrapper.get_commits_from_repos(since_after=args.since_after)
    assert isinstance(result, str)
    assert f"GitHub commits data for {github_api_wrapper.repos} saved" in result

def test_get_pull_requests_from_repos(github_api_wrapper):
    args = GetGithubCommitsFromReposArgs(since_after="2025-06-01")
    result = github_api_wrapper.get_pull_requests_from_repos(since_after=args.since_after)
    assert isinstance(result, str)
    assert "GitHub pull requests data saved" in result

def test_get_repositories_list(github_api_wrapper):
    with patch(
        "src.alita_sdk.community.analysis.github_analyse.api_wrapper.dispatch_custom_event",
        return_value=None,
    ):
        args = GetGithubRepositoriesListArgs(pushed_after="2025-06-01")
        result = github_api_wrapper.get_repositories_list(pushed_after=args.pushed_after)
        assert isinstance(result, str)
        assert "GitHub repositories list saved" in result

def test_get_repositories_extended_data(github_api_wrapper):
    with patch(
        "src.alita_sdk.community.analysis.github_analyse.api_wrapper.dispatch_custom_event",
        return_value=None,
    ):
        args = GetGithubRepositoriesListArgs(pushed_after="2025-06-01")
        result = github_api_wrapper.get_repositories_extended_data(pushed_after=args.pushed_after)
        assert isinstance(result, str)
        assert "Extended repository info that you have access saved" in result
