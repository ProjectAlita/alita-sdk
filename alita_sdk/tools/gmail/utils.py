from google.oauth2.credentials import Credentials
from langchain_community.tools.gmail.utils import import_installed_app_flow

def get_gmail_credentials(creds_json: dict) -> Credentials:
    """Get credentials."""
    InstalledAppFlow = import_installed_app_flow()
    DEFAULT_SCOPES = ["https://mail.google.com/"]
    flow = InstalledAppFlow.from_client_config(creds_json, DEFAULT_SCOPES)
    creds = flow.run_local_server(port=0)
    return creds