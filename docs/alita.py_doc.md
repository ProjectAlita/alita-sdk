# alita.py

**Path:** `src/alita_sdk/llms/alita.py`

## Data Flow

The data flow within `alita.py` revolves around the `AlitaChatModel` class, which is designed to handle chat-based interactions using a language model. The data originates from user inputs, which are encapsulated in `BaseMessage` objects. These messages are processed by the `AlitaChatModel` methods, such as `_generate`, `_stream`, and `completion_with_retry`. The data undergoes transformations, including tokenization and encoding, before being sent to the `AlitaClient` for prediction. The responses from the client are then decoded and structured into `ChatResult` objects, which are returned to the user. Intermediate variables like `messages`, `response`, and `chunk` are used to temporarily store data during processing.

Example:
```python
response = self.completion_with_retry(messages)
return self._create_chat_result(response)
```
In this snippet, `messages` is the input data, `response` is the intermediate data, and the final output is a `ChatResult` object.

## Functions Descriptions

### `validate_env`

This class method validates the environment by initializing the `AlitaClient` and setting up the encoding based on the model name. It takes a dictionary of values as input and returns a modified dictionary.

### `_generate`

This method generates chat responses. It can handle both streaming and non-streaming responses. It takes a list of `BaseMessage` objects, optional stop words, and a run manager as inputs. It returns a `ChatResult` object.

### `_stream`

This method handles streaming responses. It takes similar inputs as `_generate` and yields `ChatGenerationChunk` objects, which represent chunks of the generated response.

### `completion_with_retry`

This method attempts to get a prediction from the `AlitaClient`, retrying up to a maximum number of times if errors occur. It takes a list of messages and an optional retry count as inputs and returns a list of `BaseMessage` objects.

### `_create_chat_result`

This method creates a `ChatResult` object from a list of `BaseMessage` objects. It calculates token usage and structures the messages into `ChatGeneration` objects.

## Dependencies Used and Their Descriptions

### `requests`

Used for making HTTP requests to the `AlitaClient`.

### `tiktoken`

Used for encoding and decoding messages based on the model's tokenization scheme.

### `langchain_core`

Provides core functionalities like message handling, callback management, and language model interfaces.

### `pydantic`

Used for data validation and settings management.

## Functional Flow

1. **Initialization**: The `AlitaChatModel` is initialized with various parameters like `deployment`, `api_token`, and `model_name`.
2. **Validation**: The `validate_env` method sets up the client and encoding.
3. **Message Processing**: Methods like `_generate` and `_stream` handle the processing of input messages.
4. **Client Interaction**: The `completion_with_retry` method interacts with the `AlitaClient` to get predictions.
5. **Result Creation**: The `_create_chat_result` method structures the final output.

## Endpoints Used/Created

### `AlitaClient.predict`

- **Type**: HTTP POST
- **URL**: Derived from `deployment` parameter
- **Purpose**: Sends input messages to the language model and receives predictions.
- **Request Format**: JSON
- **Response Format**: JSON
- **Authentication**: Uses `api_token` for authentication.
