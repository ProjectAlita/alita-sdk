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

```bash
pip install alita-sdk
```

```python
import logging
from os import environ
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv('.env')
logger = logging.getLogger(__name__)

from alita_sdk.utils.streamlit import run_streamlit

try:
    import streamlit as st
except ImportError:
    logger.error("Streamlit not found, please install it using `pip install streamlit`")
    exit(1)

from alita_sdk.llms.alita import AlitaChatModel
            
# Minimal set of setting for AlitaChatModel
settings = {
    "deployment": "https://eye.projectalita.ai",
    "model": "gpt-4-0125-preview",
    "api_key": environ.get("AUTH_TOKEN"),
    "project_id": environ.get("PROJECT_ID"),
    "integration_uid": environ.get("INTEGRATION_UID"),
    
}

agent_id = 1  # Created Agent ID in Alita Platform
agent_version_id = 1

print(settings)
if 'messages' not in st.session_state:
    llm = AlitaChatModel(**settings)
    st.session_state.messages = []
    st.session_state.agent_executor = llm.client.application(llm, agent_id, agent_version_id)


run_streamlit(st)

```
