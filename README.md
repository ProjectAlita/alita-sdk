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
DEPLOYMENT_URL=<your_deployment_url>
API_KEY=<your_api_key>
PROJECT_ID=<your_project_id>
INTEGRATION_UID=<your_integration_uid>
MODEL_NAME=<your_model_name>
```


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

Note: If **streamlite** throws an error related to **pytorch**, add this `--server.fileWatcherType none` extra arguments.   
Sometimes it try to index **pytorch** modules and since they are **C** modules it raises an exception. 

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
   - Optionally select an agent type and add custom tools
   - Click "Load Agent" to initialize the agent

3. **Interacting with the Agent**:
   - Use the chat input at the bottom of the screen to send messages to the agent
   - The agent's responses will appear in the chat window
   - Your conversation history is maintained until you clear it

4. **Clearing Data**:
   - Use the "Clear Chat" button to reset the conversation history
   - Use the "Clear Config" button to reset toolkit configurations

This web application simplifies the process of testing and interacting with your Alita agents, making development and debugging more efficient.

Adding Alita-Tools to PYTHONPATH
--------------------------------

If you have another repository containing Alita tools, you can add it to your PYTHONPATH to make the tools available to your project. For example:

1. Clone the repository containing the Alita tools:
    ```bash
    git clone https://github.com/yourusername/alita-tools.git
    ```

2. Add the repository to your PYTHONPATH:
    ```bash
    export PYTHONPATH=$PYTHONPATH:/path/to/alita-tools
    ```

3. Verify that the tools are accessible in your project:
    ```python
    import sys
    print(sys.path)
    ```
