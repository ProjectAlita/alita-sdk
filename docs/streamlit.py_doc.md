# streamlit.py

**Path:** `src/alita_sdk/utils/streamlit.py`

## Data Flow

The data flow within `streamlit.py` is centered around the interaction between the user and the Streamlit interface, which is used to configure and run AI agents. The data originates from user inputs in the Streamlit web interface, such as text inputs, button clicks, and form submissions. These inputs are processed and stored in the Streamlit session state. For example, user credentials and configuration settings are captured through forms and stored in session state variables like `st.session_state.llm` and `st.session_state.agent_executor`.

Data transformations occur when user inputs are validated and used to instantiate objects like `AlitaChatModel` and `agent_executor`. These objects interact with external services and APIs to fetch data, such as available agents and models. The data is then displayed back to the user through the Streamlit interface, providing real-time feedback and updates.

A key data transformation example is the encoding and decoding of images for display in the Streamlit interface:

```python
from PIL import Image
import io
import base64

def decode_img(msg):
    msg = msg[msg.find(b"<plain_txt_msg:img>")+len(b"<plain_txt_msg:img>"):
              msg.find(b"<!plain_txt_msg>")]
    msg = base64.b64decode(msg)
    buf = io.BytesIO(msg)
    img = Image.open(buf)
    return img
```

In this example, the `decode_img` function extracts and decodes a base64-encoded image from a message, transforming it into an image object that can be displayed in the Streamlit interface.

## Functions Descriptions

### `img_to_txt(filename)`

This function converts an image file to a base64-encoded text message. It reads the image file in binary mode, encodes it using base64, and wraps it in custom tags for plain text messages.

**Inputs:**
- `filename`: The path to the image file.

**Outputs:**
- A base64-encoded text message representing the image.

### `decode_img(msg)`

This function decodes a base64-encoded image message back into an image object. It extracts the base64 content from the message, decodes it, and opens it as an image using the PIL library.

**Inputs:**
- `msg`: The base64-encoded image message.

**Outputs:**
- An image object.

### `run_streamlit(st, ai_icon, user_icon)`

This is the main function that sets up and runs the Streamlit interface. It configures the page, handles user inputs, and manages the session state. It includes nested functions for clearing chat history, creating toolkit schemas, and handling form submissions for login and agent loading.

**Inputs:**
- `st`: The Streamlit module.
- `ai_icon`: The AI icon image.
- `user_icon`: The user icon image.

**Outputs:**
- None directly, but it updates the Streamlit interface and session state.

## Dependencies Used and Their Descriptions

### `base64`

Used for encoding and decoding images to and from base64 format.

### `io`

Provides the `BytesIO` class for handling binary data in memory.

### `json`

Used for parsing and generating JSON data, particularly for handling custom tools and configurations.

### `PIL (Pillow)`

The Python Imaging Library, used for opening, manipulating, and saving image files.

### `logging`

Used for logging error messages and other information.

### `os.environ`

Accesses environment variables for configuration settings.

### `dotenv`

Loads environment variables from a `.env` file.

### `AlitaChatModel`, `AlitaStreamlitCallback`, `get_toolkits`

Custom modules and functions from the `alita_sdk` package, used for interacting with the Alita AI models and toolkits.

## Functional Flow

1. **Page Configuration:** The `run_streamlit` function sets up the Streamlit page configuration, including the title, icon, layout, and menu items.
2. **Session State Initialization:** It checks and initializes the session state for toolkit configurations and names.
3. **Sidebar Setup:** The sidebar is configured with buttons and forms for clearing chat history, logging in, and loading agents.
4. **Login Form:** The login form captures user credentials and initializes the `AlitaChatModel` object upon submission.
5. **Agent Loading:** The agent loading form allows users to select and load an agent, initializing the `agent_executor` object.
6. **Main Interface:** The main interface displays chat messages and handles user inputs for interacting with the loaded agent.

## Endpoints Used/Created

The file does not explicitly define or call any external endpoints directly. However, it interacts with the Alita AI services through the `AlitaChatModel` and `agent_executor` objects, which likely make API calls to fetch data and perform actions based on user inputs.