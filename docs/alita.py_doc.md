# alita.py

**Path:** `src/alita_sdk/llms/alita.py`

## Data Flow

The data flow within `alita.py` revolves around the `AlitaChatModel` class, which is designed to handle chat-based interactions using a language model. The data originates from user inputs, which are encapsulated in `BaseMessage` objects. These messages are processed by various methods within the `AlitaChatModel` class, such as `_generate`, `_stream`, and `completion_with_retry`. The data undergoes transformations, including tokenization, encoding, and chunking, before being sent to the `AlitaClient` for prediction. The responses from the client are then decoded, chunked, and returned as `ChatResult` objects. Intermediate variables like `token_usage`, `generations`, and `chunk` are used to temporarily store data during processing.

Example:
```python
response = self.completion_with_retry(messages)
return self._create_chat_result(response)
```
In this snippet, `messages` are processed by `completion_with_retry`, and the response is transformed into a `ChatResult` object.

## Functions Descriptions

### `validate_env`

This class method validates the environment and initializes the `AlitaClient` and encoding settings. It takes a dictionary of values as input and returns an updated dictionary with initialized client and encoding.

### `_generate`

This method generates chat responses based on input messages. It supports both streaming and non-streaming responses. It takes `messages`, `stop`, and `run_manager` as inputs and returns a `ChatResult` object.

### `_stream`

This method handles streaming responses. It takes `messages`, `stop`, and `run_manager` as inputs and returns an iterator of `ChatGenerationChunk` objects.

### `_create_chat_result`

This method creates a `ChatResult` object from a list of `BaseMessage` objects. It calculates token usage and organizes the messages into `ChatGeneration` objects.

### `completion_with_retry`

This method handles the completion of messages with retry logic. It takes `messages` and `retry_count` as inputs and returns a list of `BaseMessage` objects. It retries the request in case of exceptions, up to a maximum number of retries.

## Dependencies Used and Their Descriptions

- `logging`: Used for logging error and debug messages.
- `requests`: Used for making HTTP requests to the Alita API.
- `time.sleep`: Used to introduce delays between retries.
- `traceback.format_exc`: Used to format exception tracebacks.
- `tiktoken`: Used for tokenization and encoding of messages.
- `langchain_core`: Provides various core functionalities like callbacks, language models, messages, outputs, and runnables.
- `AlitaClient`: Custom client for interacting with the Alita API.
- `pydantic`: Used for data validation and settings management.

## Functional Flow

1. **Initialization**: The `AlitaChatModel` class is initialized with various parameters like `deployment`, `api_token`, `project_id`, etc.
2. **Validation**: The `validate_env` method validates the environment and initializes the `AlitaClient` and encoding settings.
3. **Message Processing**: Methods like `_generate`, `_stream`, and `completion_with_retry` handle the processing of input messages.
4. **Response Generation**: The `_create_chat_result` method organizes the processed messages into a `ChatResult` object.
5. **Retry Logic**: The `completion_with_retry` method implements retry logic for handling exceptions during message completion.

## Endpoints Used/Created

- **Alita API**: The `AlitaClient` interacts with the Alita API for generating chat responses. The base URL is `https://eye.projectalita.ai`, and the API token is used for authentication.
