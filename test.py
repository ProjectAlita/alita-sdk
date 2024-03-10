import logging
from os import environ
from dotenv import load_dotenv


from src.alita_sdk.llms.alita import AlitaChatModel
from langchain_core.messages import HumanMessage


logging.basicConfig(level=logging.INFO)

load_dotenv('.env')

## Minimal set of setting for AlitaChatModel
settings = {
    "deployment": "https://eye.projectalita.ai",
    "model": "gpt-35-turbo",
    "api_key": environ.get("AUTH_TOKEN"),
    "project_id": environ.get("PROJECT_ID"),
    "integration_uid": environ.get("INTEGRATION_UID"),
    
}

## Instantiating AlitaChatModel
llm = AlitaChatModel(**settings)

# Calling LLM Model
print(llm.invoke([HumanMessage(content="Hello")]))

## Getting PromptTemplate from Project with version_id 7
print(llm.client.get_prompt(prompt_id=7, prompt_version_id=7))