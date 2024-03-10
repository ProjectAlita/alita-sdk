# You would need to install langchain before you can run this code.

import logging
from os import environ
from dotenv import load_dotenv

from src.alita_sdk.llms.alita import AlitaChatModel
from langchain_core.messages import HumanMessage


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

load_dotenv('.env')

## Minimal set of setting for AlitaChatModel
settings = {
    "deployment": "https://eye.projectalita.ai",
    "model": "gpt-4",
    "api_key": environ.get("AUTH_TOKEN"),
    "project_id": environ.get("PROJECT_ID"),
    "integration_uid": environ.get("INTEGRATION_UID"),
    "max_tokens": 2048,
    "stream": True
}


## Instantiating AlitaChatModel
llm = AlitaChatModel(**settings)


## Defining tools
from demo.demo_react_agent.tools.getRepoTree import getRepoTreeTool
from demo.demo_react_agent.tools.func_tools import getRawFileTool, storeSpecFile, getFolderContent, getFileContentTool


tools = [
    getRepoTreeTool(), 
    getRawFileTool, 
    storeSpecFile
]

# Construct Agents
from langchain.agents import  AgentExecutor
from langchain.memory import ConversationBufferMemory

# Construct the Alita agent
prompt = llm.client.prompt(prompt_id=5, prompt_version_id=9)

from langchain_community.chat_models.azure_openai import AzureChatOpenAI

llm = AzureChatOpenAI(
    azure_endpoint=environ.get("DIAL_ENDPOINT"),
    deployment_name="gpt-4-1106-preview",
    openai_api_version="2023-03-15-preview",
    openai_api_key=environ.get('DIAL_AUTH_TOKEN')
)


from src.alita_sdk.agents import create_mixed_agent
agent = create_mixed_agent(llm, tools, prompt)

agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools,
    verbose=True, handle_parsing_errors=True, max_execution_time=None,
    return_intermediate_steps=True)

agent_executor.invoke({"input": """Use repository spring-petclinic/spring-framework-petclinic with branch main 
It is Java Spring application, please create swagger spec. 
Deployment URL is https://petclinic.example.com"""}, include_run_info=True)