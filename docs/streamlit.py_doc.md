# streamlit.py

**Path:** `src/alita_sdk/utils/streamlit.py`

## Data Flow

The data flow within `streamlit.py` begins with the importation of necessary libraries and modules, such as `base64`, `io`, `json`, `Image` from `PIL`, and `logging`. The script sets up logging and loads environment variables from a `.env` file. The primary data flow involves handling image data, converting images to base64 strings, and decoding base64 strings back into images. This is evident in the `img_to_txt` and `decode_img` functions. The `run_streamlit` function orchestrates the main data flow, setting up the Streamlit page configuration, handling user inputs, and managing session states. Data is passed between various Streamlit components, such as forms and buttons, and processed accordingly. For example, user inputs for deployment URL, API key, and project ID are captured and used to authenticate with the AlitaChatModel. The data flow also includes handling chat messages, where user inputs are processed, and responses are generated and displayed.

Example:
```python
with st.form("settings_form", clear_on_submit=False):
    deployment = st.text_input("Deployment URL", placeholder="Enter Deployment URL", value=deployment_value)
    api_key = st.text_input("API Key", placeholder="Enter API Key", value=api_key_value, type="password")
    project_id = st.number_input("Project ID", format="%d", min_value=0, value=project_id_value, placeholder="Enter Project ID")
    deployment_secret = st.text_input("Deployment Secret", placeholder="Enter Deployment Secret", value=deployment_secret)
    submitted = st.form_submit_button("Login")
    if submitted:
        with st.spinner("Logging to Alita..."):
            try:
                st.session_state.llm = AlitaChatModel(**{
                        "deployment": deployment,
                        "api_token": api_key,
                        "project_id": project_id,
                    })
                client = st.session_state.llm.client
                integrations = client.all_models_and_integrations()
                unique_models = set()
                models_list = []
                for entry in integrations:
                    models = entry.get('settings', {}).get('models', [])
                    for model in models:
                        if model.get('capabilities', {}).get('chat_completion') and model['name'] not in unique_models:
                            unique_models.add(model['name'])
                            models_list.append({model['name']: entry['uid']})
                st.session_state.agents = client.get_list_of_apps()
                st.session_state.models = models_list
                clear_chat_history()
            except Exception as e:
                logger.error(f"Error loggin to ELITEA: {format_exc()}")
                st.session_state.agents = None
                st.session_state.models = None
                st.session_state.llm = None
                st.error(f"Error loggin to ELITEA ")
```

## Functions Descriptions

1. **img_to_txt(filename):**
   - **Purpose:** Converts an image file to a base64-encoded string.
   - **Inputs:** `filename` (str) - The path to the image file.
   - **Processing:** Opens the image file in binary mode, reads its content, encodes it in base64, and wraps it with custom tags.
   - **Outputs:** Base64-encoded string of the image.
   - **Example:**
     ```python
     def img_to_txt(filename):
         msg = b"<plain_txt_msg:img>"
         with open(filename, "rb") as imageFile:
             msg = msg + base64.b64encode(imageFile.read())
         msg = msg + b"<!plain_txt_msg>"
         return msg
     ```

2. **decode_img(msg):**
   - **Purpose:** Decodes a base64-encoded image string back into an image object.
   - **Inputs:** `msg` (bytes) - The base64-encoded image string.
   - **Processing:** Extracts the base64 content from the string, decodes it, and opens it as an image using PIL.
   - **Outputs:** Image object.
   - **Example:**
     ```python
     def decode_img(msg):
         msg = msg[msg.find(b"<plain_txt_msg:img>")+len(b"<plain_txt_msg:img>"):
                   msg.find(b"<!plain_txt_msg>")]
         msg = base64.b64decode(msg)
         buf = io.BytesIO(msg)
         img = Image.open(buf)
         return img
     ```

3. **run_streamlit(st, ai_icon=decode_img(ai_icon), user_icon=decode_img(user_icon)):**
   - **Purpose:** Main function to run the Streamlit application.
   - **Inputs:** `st` (Streamlit module), `ai_icon` (image), `user_icon` (image).
   - **Processing:** Sets up the Streamlit page, handles user inputs, manages session states, and processes chat messages.
   - **Outputs:** None (directly interacts with Streamlit UI).
   - **Example:**
     ```python
     def run_streamlit(st, ai_icon=decode_img(ai_icon), user_icon=decode_img(user_icon)):
         def clear_chat_history():
             st.session_state.messages = []
             st.session_state.thread_id = None
         def create_tooklit_schema(tkit_schema):
             schema = {}
             for key, value in tkit_schema.get('properties', {}).items():
                 if value.get('autopopulate'):
                     continue
                 schema[key] = value
             return schema
         st.set_page_config(
             page_title='Alita Assistants',
             page_icon = ai_icon,
             layout = 'wide',
             initial_sidebar_state = 'auto',
             menu_items={
                 "Get help" : "https://elitea.ai",
                 "About": "https://elitea.ai/docs"
             }
         )
         if not(st.session_state.tooklit_configs and len(st.session_state.tooklit_configs) > 0):
             for tkit_pd in get_toolkits():
                 ktit_sch = tkit_pd.schema()
                 st.session_state.tooklit_configs.append(ktit_sch)
                 st.session_state.tooklit_names.append(ktit_sch['title'])
         st.markdown(
             r"""
             <style>
             [data-testid="stStatusWidget"] { display: none; }
             .stDeployButton { display: none; }
             section[data-testid="stSidebarContent"] { width: 400px !important; }
             </style>
             """, unsafe_allow_html=True
         )
         with st.sidebar:
             clear_chat = st.button("Clear Chat")
             if clear_chat:
                 clear_chat_history()
             llmconfig, agentconfig = st.tabs(["Alita Settings", "Local Runtime"])
             with llmconfig:
                 st.title("Elitea Login Form")
                 deployment_value = environ.get('DEPLOYMENT_URL', None)
                 deployment_secret = environ.get('XSECRET', 'secret')
                 api_key_value = environ.get('API_KEY', None)
                 project_id_value = int(environ.get('PROJECT_ID', 0))
                 if st.session_state.llm:
                     deployment_value = st.session_state.llm.deployment
                     api_key_value = st.session_state.llm.api_token
                     project_id_value = st.session_state.llm.project_id
                 with st.form("settings_form", clear_on_submit=False):
                     deployment = st.text_input("Deployment URL", placeholder="Enter Deployment URL", value=deployment_value)
                     api_key = st.text_input("API Key", placeholder="Enter API Key", value=api_key_value, type="password")
                     project_id = st.number_input("Project ID", format="%d", min_value=0, value=project_id_value, placeholder="Enter Project ID")
                     deployment_secret = st.text_input("Deployment Secret", placeholder="Enter Deployment Secret", value=deployment_secret)
                     submitted = st.form_submit_button("Login")
                     if submitted:
                         with st.spinner("Logging to Alita..."):
                             try:
                                 st.session_state.llm = AlitaChatModel(**{
                                         "deployment": deployment,
                                         "api_token": api_key,
                                         "project_id": project_id,
                                     })
                                 client = st.session_state.llm.client
                                 integrations = client.all_models_and_integrations()
                                 unique_models = set()
                                 models_list = []
                                 for entry in integrations:
                                     models = entry.get('settings', {}).get('models', [])
                                     for model in models:
                                         if model.get('capabilities', {}).get('chat_completion') and model['name'] not in unique_models:
                                             unique_models.add(model['name'])
                                             models_list.append({model['name']: entry['uid']})
                                 st.session_state.agents = client.get_list_of_apps()
                                 st.session_state.models = models_list
                                 clear_chat_history()
                             except Exception as e:
                                 logger.error(f"Error loggin to ELITEA: {format_exc()}")
                                 st.session_state.agents = None
                                 st.session_state.models = None
                                 st.session_state.llm = None
                                 st.error(f"Error loggin to ELITEA ")
                 if st.session_state.llm:
                     st.title("Available Agents")
                     st.write("This one will load latest version of agent")
                     with st.form("agents_form", clear_on_submit=False):
                         options = st.selectbox("Select an agent to load", (agent['name'] for agent in st.session_state.agents))
                         agent_version_name = st.text_input("Agent Version Name", value='latest', placeholder="Enter Version ID")
                         agent_type = st.selectbox("Agent Type (leave brank for default)", [""] + agent_types)
                         custom_tools = st.text_area("Custom Tools", placeholder="Enter Custom Tools in List Dict format")
                         submitted = st.form_submit_button("Load Agent")
                         if submitted:
                             with st.spinner("Loading Agent..."):
                                 agent = next((a for a in st.session_state.agents if a['name'] == options), None)
                                 if agent:
                                     agent_id = agent['id']
                                     agent_details = st.session_state.llm.client.get_app_details(agent_id)
                                     latest_version = next((v for v in agent_details['versions'] if v['name'] == agent_version_name), None)
                                     if latest_version:
                                         agent_version_id = latest_version['id']
                                         import sqlite3
                                         from langgraph.checkpoint.sqlite import SqliteSaver
                                         memory = SqliteSaver(
                                             sqlite3.connect("memory.db", check_same_thread=False)
                                         )
                                         try:
                                             custom_tools_json = json.loads(custom_tools)
                                             if not isinstance(custom_tools_json, list):
                                                 raise ValueError("Custom tools should be a list of dictionaries")
                                         except:
                                             custom_tools_json = []
                                         st.session_state.agent_executor = st.session_state.llm.client.application(
                                             client=st.session_state.llm,
                                             application_id=agent_id,
                                             application_version_id=agent_version_id,
                                             app_type=agent_type if agent_type else None,
                                             tools=custom_tools_json,
                                             memory=memory,
                                         )
                                         st.session_state.agent_name = options
                                         clear_chat_history()
                                     else:
                                         st.session_state.agent_executor = None
                                         st.session_state.agent_name = None
                                         clear_chat_history()
                                         st.error("Agent version not found")
             with agentconfig:
                 st.title("Local Agent")
                 clear_agent = st.button("Clear Config")
                 if clear_agent:
                     st.session_state.toolkits = []
                 with st.form("add_tkit", clear_on_submit=False):
                     options = st.selectbox("Add toolkit", st.session_state.tooklit_names)
                     submitted = st.form_submit_button("Add Toolkit")
                     if submitted:
                         tkit_schema = st.session_state.tooklit_configs[st.session_state.tooklit_names.index(options)]
                         schema = create_tooklit_schema(tkit_schema)
                         st.session_state.toolkits.append(schema)
                 with st.form("agent_config", clear_on_submit=False):
                     context = st.text_area("Context", placeholder="Enter Context")
                     tools = st.text_area("Tools", placeholder="Enter Tools in JSON format", value=json.dumps(st.session_state.toolkits, indent=2))
                     submitted = st.form_submit_button("Submit")
                     if submitted:
                         pass
         if st.session_state.llm and st.session_state.agent_executor:
             try:
                 st.title(st.session_state.agent_name)
             except:
                 st.title("Login to Elitea to load an agent")
             for message in st.session_state.messages:
                 with st.chat_message(message["role"], avatar=ai_icon if message["role"] == "assistant" else user_icon):
                     st.markdown(message["content"])
             if prompt := st.chat_input():
                 st.chat_message("user", avatar=user_icon).write(prompt)
                 st.session_state.messages.append({"role": "user", "content": prompt})
                 with st.chat_message("assistant", avatar=ai_icon):
                     st_cb = AlitaStreamlitCallback(st)
                     response = st.session_state.agent_executor.invoke(
                         {"input": prompt, "chat_history": st.session_state.messages[:-1]},
                         { 'callbacks': [st_cb], 'configurable': {"thread_id": st.session_state.thread_id}}
                     )
                     st.write(response["output"])
                     st.session_state.thread_id = response.get("thread_id", None)
                     st.session_state.messages.append({"role": "assistant", "content": response["output"]})
         else:
             st.title("Please Load an Agent to Start Chatting")
     ```

## Dependencies Used and Their Descriptions

1. **base64:**
   - **Purpose:** Encoding and decoding of binary data to and from base64.
   - **Usage:** Used in `img_to_txt` to encode image files and in `decode_img` to decode base64 strings back to images.
   - **Example:**
     ```python
     import base64
     base64.b64encode(imageFile.read())
     base64.b64decode(msg)
     ```

2. **io:**
   - **Purpose:** Core tools for working with streams.
   - **Usage:** Used in `decode_img` to handle byte streams when converting base64 strings to images.
   - **Example:**
     ```python
     import io
     buf = io.BytesIO(msg)
     ```

3. **json:**
   - **Purpose:** Parsing JSON data.
   - **Usage:** Used to handle JSON data for custom tools and toolkit configurations.
   - **Example:**
     ```python
     import json
     custom_tools_json = json.loads(custom_tools)
     ```

4. **PIL (Pillow):**
   - **Purpose:** Image processing capabilities.
   - **Usage:** Used in `decode_img` to open and manipulate image files.
   - **Example:**
     ```python
     from PIL import Image
     img = Image.open(buf)
     ```

5. **logging:**
   - **Purpose:** Logging events for debugging and monitoring.
   - **Usage:** Used throughout the script to log errors and information.
   - **Example:**
     ```python
     import logging
     logging.basicConfig(level=logging.INFO)
     logger = logging.getLogger(__name__)
     logger.error(f"Error loggin to ELITEA: {format_exc()}")
     ```

6. **os.environ:**
   - **Purpose:** Accessing environment variables.
   - **Usage:** Used to retrieve deployment configurations and secrets.
   - **Example:**
     ```python
     from os import environ
     deployment_value = environ.get('DEPLOYMENT_URL', None)
     ```

7. **dotenv:**
   - **Purpose:** Loading environment variables from a `.env` file.
   - **Usage:** Used at the beginning of the script to load environment variables.
   - **Example:**
     ```python
     from dotenv import load_dotenv
     load_dotenv('.env')
     ```

8. **AlitaChatModel:**
   - **Purpose:** Interacting with the Alita chat model.
   - **Usage:** Used to authenticate and interact with the Alita API.
   - **Example:**
     ```python
     from src.alita_sdk.llms.alita import AlitaChatModel
     st.session_state.llm = AlitaChatModel(**{
             "deployment": deployment,
             "api_token": api_key,
             "project_id": project_id,
         })
     ```

9. **AlitaStreamlitCallback:**
   - **Purpose:** Handling Streamlit-specific callbacks.
   - **Usage:** Used to manage callbacks during chat interactions.
   - **Example:**
     ```python
     from src.alita_sdk.utils.AlitaCallback import AlitaStreamlitCallback
     st_cb = AlitaStreamlitCallback(st)
     ```

10. **get_toolkits:**
    - **Purpose:** Retrieving available toolkits.
    - **Usage:** Used to get and configure toolkits for the application.
    - **Example:**
      ```python
      from src.alita_sdk.toolkits.tools import get_toolkits
      for tkit_pd in get_toolkits():
          ktit_sch = tkit_pd.schema()
          st.session_state.tooklit_configs.append(ktit_sch)
          st.session_state.tooklit_names.append(ktit_sch['title'])
      ```

## Functional Flow

The functional flow of `streamlit.py` starts with setting up the environment and logging configurations. The