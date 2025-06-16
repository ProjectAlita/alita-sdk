import logging
from typing import List, Dict
from pydantic import BaseModel
from googleapiclient.discovery import Resource
from langchain_community.tools import GmailSendMessage
from langchain_community.tools import GmailCreateDraft
from langchain_community.tools import GmailSearch
from langchain_community.tools import GmailGetMessage
from langchain_community.tools import GmailGetThread
from langchain_community.tools.gmail.base import GmailBaseTool

logger = logging.getLogger(__name__)

class GmailWrapper(BaseModel):

    def _get_available_tools(self, api_resource: Resource) -> List[Dict[str, GmailBaseTool]]:
        return [
            {
                "name": "send_message",
                "tool": GmailSendMessage(api_resource=api_resource)
            },
            {
                "name": "create_draft",
                "tool": GmailCreateDraft(api_resource=api_resource)
            },
            {
                "name": "search",
                "tool": GmailSearch(api_resource=api_resource)
            },
            {
                "name": "get_message",
                "tool": GmailGetMessage(api_resource=api_resource)
            },
            {
                "name": "get_thread",
                "tool": GmailGetThread(api_resource=api_resource)
            }
        ]
