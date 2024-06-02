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
    "model": "gpt-4-0125-preview",
    "api_key": environ.get("AUTH_TOKEN"),
    "project_id": environ.get("PROJECT_ID"),
    "integration_uid": environ.get("INTEGRATION_UID"),
    
}

print(settings )

## Instantiating AlitaChatModel
llm = AlitaChatModel(**settings)


# print(llm.client.list_artifacts('reports'))
# print(llm.client.create_artifact('reports', 'test.txt', 'Hello World from Alita SDK'))
# print(llm.client.list_artifacts('reports'))
# print(llm.client.download_artifact('reports', 'test.txt'))
# print(llm.client.delete_artifact('reports', 'test.txt'))

# Calling LLM Model
# print(llm.invoke([HumanMessage(content="Hello")]))

## Getting PromptTemplate from Project with version_id 7
# prompt = llm.client.prompt(prompt_id=2, prompt_version_id=7)

# chain = prompt | llm

# print(chain.invoke(
#     {"input": "Hello"}
# ))

## Getting datasource
# datasource = llm.client.datasource(1)

# print(datasource.predict("How EPAM Do performance testing?"))

# print(datasource.search("How EPAM Do performance testing?"))
 