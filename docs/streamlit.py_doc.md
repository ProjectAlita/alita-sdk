# streamlit.py

**Path:** `src/alita_sdk/utils/streamlit.py`

## Data Flow

The data flow within `streamlit.py` is centered around the interaction between the user and the Streamlit interface, which is used to manage and display AI agents and their configurations. The data originates from user inputs, such as text fields and buttons, and is processed through various functions to update the session state and interact with the AlitaChatModel. The data is then displayed back to the user through the Streamlit interface.

For example, the `run_streamlit` function initializes the Streamlit page and handles user inputs to configure and load AI agents. The data flow can be illustrated with the following code snippet:

```python
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

In this example, user inputs are captured through the Streamlit interface and processed to update the session state and display the results back to the user.

## Functions Descriptions

### `img_to_txt(filename)`

This function converts an image file to a base64-encoded string. It reads the image file in binary mode, encodes it using base64, and returns the encoded string wrapped in custom tags.

**Inputs:**
- `filename`: The path to the image file to be encoded.

**Outputs:**
- A base64-encoded string representing the image.

**Example:**
```python
def img_to_txt(filename):
    msg = b"<plain_txt_msg:img>"
    with open(filename, "rb") as imageFile:
        msg = msg + base64.b64encode(imageFile.read())
    msg = msg + b"<!plain_txt_msg>"
    return msg
```

### `decode_img(msg)`

This function decodes a base64-encoded image string back into an image object. It extracts the base64-encoded part of the string, decodes it, and loads it into a PIL Image object.

**Inputs:**
- `msg`: The base64-encoded image string.

**Outputs:**
- A PIL Image object.

**Example:**
```python
def decode_img(msg):
    msg = msg[msg.find(b"<plain_txt_msg:img>")+len(b"<plain_txt_msg:img>"):
              msg.find(b"<!plain_txt_msg>")]
    msg = base64.b64decode(msg)
    buf = io.BytesIO(msg)
    img = Image.open(buf)
    return img
```

### `run_streamlit(st, ai_icon=decode_img(ai_icon), user_icon=decode_img(user_icon))`

This function sets up and runs the Streamlit interface for managing and interacting with AI agents. It initializes the page configuration, handles user inputs for configuring and loading agents, and manages the chat interface.

**Inputs:**
- `st`: The Streamlit module.
- `ai_icon`: The AI icon image (default is decoded from `ai_icon` string).
- `user_icon`: The user icon image (default is decoded from `user_icon` string).

**Outputs:**
- None (updates the Streamlit interface and session state).

**Example:**
```python
def run_streamlit(st, ai_icon=decode_img(ai_icon), user_icon=decode_img(user_icon)):
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
    # Additional setup and user input handling...
```

## Dependencies Used and Their Descriptions

### `base64`

Used for encoding and decoding image files to and from base64 strings.

### `io`

Provides the `BytesIO` class for handling binary data in memory.

### `PIL.Image`

Part of the Pillow library, used for opening and manipulating image files.

### `logging`

Used for logging error messages and other information.

### `os.environ`

Provides access to environment variables.

### `dotenv.load_dotenv`

Loads environment variables from a `.env` file.

### `src.alita_sdk.llms.alita.AlitaChatModel`

The main class for interacting with the Alita chat model.

### `src.alita_sdk.utils.AlitaCallback.AlitaStreamlitCallback`

A callback class for handling Streamlit-specific interactions with the Alita chat model.

### `src.alita_sdk.toolkits.tools.get_toolkits`

A function that retrieves available toolkits for the Alita chat model.

## Functional Flow

The functional flow of `streamlit.py` begins with the `run_streamlit` function, which sets up the Streamlit interface and handles user inputs. The function initializes the page configuration, loads toolkits, and sets up the sidebar with options for clearing the chat history and configuring the Alita chat model. User inputs are processed through forms and buttons, updating the session state and interacting with the Alita chat model as needed.

For example, the following code snippet shows how the `run_streamlit` function handles user inputs for logging into the Alita chat model:

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

## Endpoints Used/Created

The `streamlit.py` file does not explicitly define or call any endpoints. Instead, it interacts with the Alita chat model and other components through the Alita SDK and Streamlit interface. The interactions are primarily focused on configuring and managing AI agents, handling user inputs, and updating the session state.