from typing import List

from langchain_core.tools import BaseToolkit
from langchain_core.tools import BaseTool
from langchain_community.tools.gmail.utils import build_resource_service

from .gmail_wrapper import GmailWrapper
from .utils import get_gmail_credentials

# disabled
class AlitaGmailToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    def get_toolkit(self, credentials_json, selected_tools: List[str]):
        credentials = get_gmail_credentials(credentials_json)
        api_resource = build_resource_service(credentials=credentials)
        gmail_wrapper = GmailWrapper()
        available_tools = gmail_wrapper._get_available_tools(api_resource)
        for tool in available_tools:
            if selected_tools.__contains__(tool['name']):
                self.tools.append(tool.get('tool'))
        return self

    def get_tools(self):
        return self.tools
