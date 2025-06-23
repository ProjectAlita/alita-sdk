Alita SDK
=========

Alita SDK, built on top of Langchain, enables the creation of intelligent agents within the Alita Platform using project-specific prompts and data sources. This SDK is designed for developers looking to integrate advanced AI capabilities into their projects with ease.

Prerequisites
-------------

Before you begin, ensure you have the following requirements met:

*   Python 3.10+
*   An active deployment of Project Alita
*   Access to personal project

Installation
------------

It is recommended to use a Python virtual environment to avoid dependency conflicts and keep your environment isolated.

### 1. Create and activate a virtual environment

For **Unix/macOS**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

For **Windows**:
```bat
python -m venv .venv
venv\Scripts\activate
```

### 2. Install dependencies

Install all required dependencies for the SDK and toolkits:

```bash
pip install -r req_bkup/requirements-all.txt
```

Environment Setup
-----------------

Before running your Alita agents, set up your environment variables. Create a `.env` file in the root directory of your project and include your Project Alita credentials:

```.env
DEPLOYMENT_URL=<your_deployment_url>
API_KEY=<your_api_key>
PROJECT_ID=<your_project_id>
```

NOTE: these variables can be grabbed from your Elitea platform configuration page.
![Platform configuration](docs/readme_imgs/platform_config.png "Platform configuration")



Using SDK with Streamlit for Local Development
----------------------------------------------

To use the SDK with Streamlit for local development, follow these steps:

1. Ensure you have Streamlit installed:
    ```bash
    pip install streamlit
    ```

2. Run the Streamlit app:
    ```bash
    streamlit run alita_local.py
    ```

Note: If **streamlit** throws an error related to **pytorch**, add this `--server.fileWatcherType none` extra arguments.
Sometimes it tries to index **pytorch** modules, and since they are **C** modules it raises an exception.

Example of launch configuration for Streamlit:
Important: Make sure to set the correct path to your `.env` file and streamlit.
![Launch configuration example](docs/readme_imgs/launch_config.png "Launch configuration")

Streamlit Web Application
------------------------

The Alita SDK includes a Streamlit web application that provides a user-friendly interface for interacting with Alita agents. This application is powered by the `streamlit.py` module included in the SDK.

### Key Features

- **Agent Management**: Load and interact with agents created in the Alita Platform
- **Authentication**: Easily connect to your Alita/Elitea deployment using your credentials
- **Chat Interface**: User-friendly chat interface for communicating with your agents
- **Toolkit Integration**: Add and configure toolkits for your agents
- **Session Management**: Maintain conversation history and thread state

### Using the Web Application

1. **Authentication**:
   - Navigate to the "Alita Settings" tab in the sidebar
   - Enter your deployment URL, API key, and project ID
   - Click "Login" to authenticate with the Alita Platform

2. **Loading an Agent**:
   - After authentication, you'll see a list of available agents
   - Select an agent from the dropdown menu
   - Specify a version name (default: 'latest')
   - Optionally, select an agent type and add custom tools
   - Click "Load Agent" to initialize the agent

3. **Interacting with the Agent**:
   - Use the chat input at the bottom of the screen to send messages to the agent
   - The agent's responses will appear in the chat window
   - Your conversation history is maintained until you clear it

4. **Clearing Data**:
   - Use the "Clear Chat" button to reset the conversation history
   - Use the "Clear Config" button to reset toolkit configurations

This web application simplifies the process of testing and interacting with your Alita agents, making development and debugging more efficient.

Using Elitea toolkits and tools with Streamlit for Local Development
----------------------------------------------

Actually, toolkits are part of the Alita SDK (`alita-sdk/tools`), so you can use them in your local development environment as well.
To debug it, you can use the `alita_local.py` file, which is a Streamlit application that allows you 
to interact with your agents and toolkits by setting the breakpoints in the code of corresponding tool.

# Example of agent's debugging with Streamlit:
Assume we try to debug the user's agent called `Questionnaire` with the `Confluence` toolkit and `get_pages_with_label` method.
Pre-requisites:
- Make sure you have set correct variables in your `.env` file
- Set the breakpoints in the `alita_sdk/tools/confluence/api_wrapper.py` file, in the `get_pages_with_label` method

1. Run the Streamlit app (using debug):
    ```bash
    streamlit run alita_local.py
    ```
2. Login into the application with your credentials (populated from .env file)
   - Enter your deployment URL, API key, and project ID (optionally)
   - Click "Login" to authenticate with the Alita Platform

   ![login](docs/readme_imgs/login.png "login")
3. Select `Questionnaire` agent

   ![agent_selection](docs/readme_imgs/agent_selection.png "agent_selection")
4. Query the agent with the required prompt:
   ```
   get pages with label `ai-mb`
   ```
5. Debug the agent's code:
   - The Streamlit app will call the `get_pages_with_label` method of the `Confluence` toolkit
   - The execution will stop at the breakpoint you set in the `alita_sdk/tools/confluence/api_wrapper.py` file
   - You can inspect variables, step through the code, and analyze the flow of execution
![debugging](docs/readme_imgs/debugging.png "debugging")