Alita SDK
=========

Alita SDK, built on top of Langchain, enables the creation of intelligent agents within the Alita Platform using project-specific prompts and data sources. This SDK is designed for developers looking to integrate advanced AI capabilities into their projects with ease.

Prerequisites
-------------

Before you begin, ensure you have the following requirements met:

*   Python 3.10
*   An active deployment of Project Alita
*   Access to personal project

Installation
------------

First, you need to install the Langchain library. Alita SDK depends on Langchain for its core functionalities. You can install Langchain using pip:

```bash
pip install langchain
```

Next, clone the Alita SDK repository (assuming it's available on GitHub or another source):


```bash
git clone https://github.com/ProjectAlita/alita-sdk.git
cd alita-sdk
```

Install the SDK along with its dependencies:

```bash
pip install -r requirements.txt
```

Environment Setup
-----------------

Before running your Alita agents, set up your environment variables. Create a `.env` file in the root directory of your project and include your Project Alita credentials:

```.env
AUTH_TOKEN=<your_api_token>
PROJECT_ID=<your_project_id> 
INTEGRATION_UID=<your_integration_uid>
```

Ensure you load these variables in your application:


```python
from dotenv import load_dotenv 
load_dotenv('.env')
```

Basic Usage
-----------

The Alita SDK allows you to create and execute agents with ease. Here's a simple example to get you started:


```python
import logging 
from src.alita_sdk.llms.alita import AlitaChatModel 
from langchain_core.messages import HumanMessage  
# Set up 
logging logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)  

# Load environment variables 
from os import environ 
load_dotenv('.env')  

# Configuration settings for AlitaChatModel 
settings = {
    "deployment": "https://eye.projectalita.ai",
    "model": "gpt-4-1106-preview",
    "api_key": environ.get("AUTH_TOKEN"),
    "project_id": environ.get("PROJECT_ID"),
    "integration_uid": environ.get("INTEGRATION_UID"),
    "max_tokens": 2048,
    "stream": True 
}  
# Instantiate AlitaChatModel 
llm = AlitaChatModel(**settings)  

# Define tools for agent operations 
from demo.demo_react_agent.tools import getRepoTreeTool, getRawFileTool, storeSpecFile  t
ools = [getRepoTreeTool(), getRawFileTool, storeSpecFile]  

# Construct the agent with mixed capabilities 

from src.alita_sdk.agents import create_mixed_agent 
from langchain.agents import AgentExecutor 

prompt = llm.client.prompt(prompt_id=<prompt_id>, prompt_version_id=<prompt_version_id>) 
agent = create_mixed_agent(llm, tools, prompt)  

# Execute the agent 
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_execution_time=None, return_intermediate_steps=True)  

input_data = {"input": """Use repository spring-petclinic/spring-framework-petclinic with branch main. 
It is a Java Spring application, please create a swagger spec. 
Deployment URL is https://petclinic.example.com"""}  

agent_executor.invoke(input_data, include_run_info=True)
```