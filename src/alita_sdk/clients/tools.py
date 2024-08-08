import logging
from importlib import import_module

from alita_tools.github import AlitaGitHubToolkit
from alita_tools.gitlab import AlitaGitlabToolkit
from alita_tools.openapi import AlitaOpenAPIToolkit
from alita_tools.jira import JiraToolkit
from alita_tools.confluence import ConfluenceToolkit
from alita_tools.browser import BrowserToolkit
from alita_tools.zephyr import ZephyrToolkit

from ..toolkits.prompt import PromptToolkit
from ..toolkits.datasource import DatasourcesToolkit
from ..toolkits.application import ApplicationToolkit
from ..toolkits.artifact import ArtifactToolkit
from ..tools.echo import EchoTool


logger = logging.getLogger(__name__)

def get_tools(alita, llm, tools_list):
    prompts = []
    tools = []
    tools.append(EchoTool())
    for tool in tools_list:
        if tool['type'] == 'prompt':
            prompts.append([
                int(tool['settings']['prompt_id']),
                int(tool['settings']['prompt_version_id'])
            ])
        elif tool['type'] == 'datasource':
            tools.extend(DatasourcesToolkit.get_toolkit(
                alita,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools']
            ).get_tools())
        elif tool['type'] == 'application':
            tools.extend(ApplicationToolkit.get_toolkit(
                alita,
                application_id=int(tool['settings']['application_id']),
                application_version_id=int(tool['settings']['application_version_id']),
                app_api_key=alita.auth_token,
                selected_tools=[]
            ).get_tools())
        elif tool['type'] == 'artifact':
            tools.extend(ArtifactToolkit.get_toolkit(
                client=alita,
                bucket=tool['settings']['bucket'],
                selected_tools=tool['settings'].get('selected_tools', [])
            ).get_tools())
        elif tool['type'] == 'openapi':
            headers = {}
            if tool['settings'].get('authentication'):
                if tool['settings']['authentication']['type'] == 'api_key':
                    auth_type = tool['settings']['authentication']['settings']['auth_type']
                    auth_key = tool["settings"]["authentication"]["settings"]["api_key"]
                    if auth_type.lower() == 'bearer':
                        headers['Authorization'] = f'Bearer {auth_key}'
                    if auth_type.lower() == 'basic':
                        headers['Authorization'] = f'Basic {auth_key}'
                    if auth_type.lower() == 'custom':
                        headers[
                            tool["settings"]["authentication"]["settings"]["custom_header_name"]] = f'{auth_key}'
            tools.extend(AlitaOpenAPIToolkit.get_toolkit(
                openapi_spec=tool['settings']['schema_settings'],
                selected_tools=tool['settings'].get('selected_tools', []),
                headers={}
            ).get_tools())
        elif tool['type'] == 'github':
            github_toolkit = AlitaGitHubToolkit().get_toolkit(
                selected_tools=tool['settings'].get('selected_tools', []),
                github_repository=tool['settings']['repository'],
                active_branch=tool['settings']['active_branch'],
                github_base_branch=tool['settings']['base_branch'],
                github_access_token=tool['settings'].get('access_token', ''),
                github_username=tool['settings'].get('username', ''),
                github_password=tool['settings'].get('password', '')
            )
            tools.extend(github_toolkit.get_tools())
        elif tool['type'] == 'jira':
            jira_tools = JiraToolkit().get_toolkit(
                selected_tools=tool['settings'].get('selected_tools', []),
                base_url=tool['settings']['base_url'],
                cloud=tool['settings'].get('cloud', True),
                api_key=tool['settings'].get('api_key', None),
                username=tool['settings'].get('username', None),
                token=tool['settings'].get('token', None),
                limit=tool['settings'].get('limit', 5),
                additional_fields=tool['settings'].get('additional_fields', []),
                verify_ssl=tool['settings'].get('verify_ssl', True))
            tools.extend(jira_tools.get_tools())
        elif tool['type'] == 'confluence':
            confluence_tools = ConfluenceToolkit().get_toolkit(
                selected_tools=tool['settings'].get('selected_tools', []),
                base_url=tool['settings']['base_url'],
                cloud=tool['settings'].get('cloud', True),
                api_key=tool['settings'].get('api_key', None),
                username=tool['settings'].get('username', None),
                token=tool['settings'].get('token', None),
                limit=tool['settings'].get('limit', 5),
                additional_fields=tool['settings'].get('additional_fields', []),
                verify_ssl=tool['settings'].get('verify_ssl', True))
            tools.extend(confluence_tools.get_tools())
        elif tool['type'] == 'gitlab':
            gitlab_tools = AlitaGitlabToolkit().get_toolkit(
                selected_tools=tool['settings'].get('selected_tools', []),
                url=tool['settings']['url'],
                repository=tool['settings']['repository'],
                branch=tool['settings']['branch'],
                private_token=tool['settings']['private_token']
            )
            tools.extend(gitlab_tools.get_tools())
        elif tool['type'] == 'zephyr':
            zephyr_tools = ZephyrToolkit().get_toolkit(
                selected_tools=tool['settings'].get('selected_tools', []),
                base_url=tool['settings']['base_url'],
                user_name=tool['settings']['user_name'],
                password=tool['settings']['password'])
            tools.extend(zephyr_tools.get_tools())
        elif tool['type'] == 'browser':
            browser_tools = BrowserToolkit().get_toolkit(
                selected_tools=tool['settings'].get('selected_tools', []),
                google_api_key=tool['settings'].get('google_api_key'),
                google_cse_id=tool['settings'].get("google_cse_id")
            )
            tools.extend(browser_tools.get_tools())
        else:
            if tool.get("settings", {}).get("module"):
                try:
                    settings = tool.get("settings", {})
                    mod = import_module(settings.pop("module"))
                    tkitclass = getattr(mod, settings.pop("class"))
                    toolkit = tkitclass.get_toolkit(**tool["settings"])
                    tools.extend(toolkit.get_tools())
                except Exception as e:
                    logger.error(f"Error in getting toolkit: {e}")
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    return tools