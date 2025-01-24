# streamlit.py

**Path:** `src/alita_sdk/utils/streamlit.py`

## Data Flow

The data flow within `streamlit.py` revolves around the interaction between the Streamlit UI components and the backend logic that processes user inputs and displays outputs. The primary data elements include user inputs (such as text and selections), configuration settings, and responses from the AlitaChatModel. The data originates from user interactions with the Streamlit interface, which are captured and processed by various functions within the file.

For example, when a user submits a login form, the input data (deployment URL, API key, project ID) is captured and used to instantiate an `AlitaChatModel` object. This object then interacts with the backend to authenticate the user and retrieve available agents and models. The data flow can be visualized as follows:

1. User inputs data into the Streamlit form.
2. The form data is captured and used to create an `AlitaChatModel` instance.
3. The `AlitaChatModel` interacts with the backend to authenticate the user and retrieve data.
4. The retrieved data (agents, models) is stored in the session state and displayed in the UI.

```python
with st.form("settings_form", clear_on_submit=False):
    deployment = st.text_input("Deployment URL", placeholder="Enter Deployment URL", value=deployment_value)
    api_key = st.text_input("API Key", placeholder="Enter API Key", value=api_key_value, type="password")
    project_id = st.number_input("Project ID", format="%d", min_value=0, value=project_id_value, placeholder="Enter Project ID")
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

### `img_to_txt(filename)`

This function converts an image file to a base64-encoded string. It reads the image file in binary mode, encodes it using base64, and returns the encoded string wrapped in custom tags.

- **Parameters:**
  - `filename` (str): The path to the image file.
- **Returns:**
  - `msg` (bytes): The base64-encoded string of the image.

### `decode_img(msg)`

This function decodes a base64-encoded image string back into an image object. It extracts the base64 string from the custom tags, decodes it, and returns the image object.

- **Parameters:**
  - `msg` (bytes): The base64-encoded string of the image.
- **Returns:**
  - `img` (PIL.Image.Image): The decoded image object.

### `run_streamlit(st, ai_icon=decode_img(ai_icon), user_icon=decode_img(user_icon))`

This is the main function that sets up and runs the Streamlit application. It configures the page, handles user inputs, manages session states, and interacts with the AlitaChatModel to provide chat functionalities.

- **Parameters:**
  - `st` (module): The Streamlit module.
  - `ai_icon` (PIL.Image.Image): The AI icon image.
  - `user_icon` (PIL.Image.Image): The user icon image.

## Dependencies Used and Their Descriptions

### `base64`

Used for encoding and decoding image files to and from base64 strings.

### `io`

Provides the `BytesIO` class for handling binary data in memory.

### `PIL (Pillow)`

Used for image processing tasks such as opening and manipulating image files.

### `logging`

Used for logging error messages and other information.

### `traceback`

Provides utilities for extracting, formatting, and printing stack traces of Python programs.

### `os.environ`

Used for accessing environment variables.

### `dotenv`

Used for loading environment variables from a `.env` file.

### `AlitaChatModel`

A custom class from `src.alita_sdk.llms.alita` used for interacting with the Alita backend.

### `AlitaStreamlitCallback`

A custom callback class from `src.alita_sdk.utils.AlitaCallback` used for handling Streamlit-specific callbacks.

### `get_toolkits`

A function from `src.alita_sdk.toolkits.tools` used for retrieving available toolkits.

## Functional Flow

The functional flow of `streamlit.py` involves setting up the Streamlit page, handling user inputs, managing session states, and interacting with the Alita backend to provide chat functionalities. The sequence of operations is as follows:

1. The page is configured using `st.set_page_config`.
2. User inputs are captured through various forms and input fields.
3. The captured inputs are used to instantiate and configure the `AlitaChatModel`.
4. The `AlitaChatModel` interacts with the backend to authenticate the user and retrieve data.
5. The retrieved data is stored in the session state and displayed in the UI.
6. User messages are processed and responses are generated using the `AlitaChatModel`.
7. The chat history is managed and displayed in the Streamlit interface.

## Endpoints Used/Created

The file does not explicitly define or call any external endpoints. However, it interacts with the Alita backend through the `AlitaChatModel` class, which likely makes API calls to authenticate the user and retrieve data. The specifics of these interactions are abstracted away by the `AlitaChatModel` class.