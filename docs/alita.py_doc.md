# alita.py

**Path:** `src/alita_sdk/llms/alita.py`

## Data Flow

The data flow within the `alita.py` file revolves around the `AlitaChatModel` class, which is designed to interact with the Alita API for generating chat responses. The data flow can be summarized as follows:

1. **Initialization:** The `AlitaChatModel` class is initialized with various parameters such as `deployment`, `api_token`, `project_id`, `model_name`, and others. These parameters are used to configure the Alita client and the encoding settings.
2. **Message Handling:** The `_generate` method is responsible for handling incoming messages. It takes a list of `BaseMessage` objects and processes them to generate a chat response. If streaming is enabled, it uses the `_stream` method to handle the streaming of responses.
3. **Response Generation:** The `completion_with_retry` method is used to send the messages to the Alita API and handle retries in case of errors. The response from the API is then processed to create a `ChatResult` object, which contains the generated messages and other relevant information.
4. **Token Usage Calculation:** The `_create_chat_result` method calculates the token usage for the generated messages and constructs the final `ChatResult` object.

Example:
```python
class AlitaChatModel(BaseChatModel):
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.stream_response:
            stream_iter = self._stream(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
            return generate_from_stream(stream_iter)
        self.stream_response = False
        response = self.completion_with_retry(messages)
        return self._create_chat_result(response)
```

## Functions Descriptions

### `validate_env`

This class method is a model validator that initializes the Alita client and sets up the encoding based on the provided parameters. It ensures that the necessary configurations are in place before the model is used.

### `_generate`

This method handles the generation of chat responses. It takes a list of messages and processes them to generate a response. If streaming is enabled, it uses the `_stream` method to handle the streaming of responses.

### `_stream`

This method handles the streaming of chat responses. It takes a list of messages and yields `ChatGenerationChunk` objects as the responses are generated. It uses the `completion_with_retry` method to send the messages to the Alita API and handle retries in case of errors.

### `_create_chat_result`

This method constructs a `ChatResult` object from the generated messages. It calculates the token usage and includes it in the `ChatResult` object.

### `completion_with_retry`

This method sends the messages to the Alita API and handles retries in case of errors. It raises a `MaxRetriesExceededError` if the maximum number of retries is exceeded.

### `_llm_type`

This property returns the type of the language model.

### `_get_model_default_parameters`

This property returns the default parameters for the language model, including temperature, top_k, top_p, max_tokens, and stream settings.

### `_identifying_params`

This property returns a dictionary of identifying parameters for the language model, including deployment, api_token, project_id, integration_id, and model settings.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging error messages and debugging information.

### `requests`

Used for making HTTP requests to the Alita API.

### `time.sleep`

Used for adding delays between retries in the `completion_with_retry` method.

### `traceback.format_exc`

Used for formatting exception tracebacks in error messages.

### `tiktoken`

Used for encoding messages and calculating token usage.

### `langchain_core`

Provides various core components for language models, including base classes, message types, and callback managers.

### `AlitaClient`

A custom client for interacting with the Alita API.

### `pydantic`

Used for data validation and settings management.

## Functional Flow

1. **Initialization:** The `AlitaChatModel` class is initialized with various parameters, which are validated and used to configure the Alita client and encoding settings.
2. **Message Handling:** The `_generate` method processes incoming messages and generates chat responses. If streaming is enabled, it uses the `_stream` method to handle the streaming of responses.
3. **Response Generation:** The `completion_with_retry` method sends the messages to the Alita API and handles retries in case of errors. The response is processed to create a `ChatResult` object.
4. **Token Usage Calculation:** The `_create_chat_result` method calculates the token usage for the generated messages and constructs the final `ChatResult` object.

## Endpoints Used/Created

### Alita API

The `AlitaChatModel` class interacts with the Alita API to generate chat responses. The base URL for the API is specified by the `deployment` parameter, and the API token is provided by the `api_token` parameter. The `completion_with_retry` method sends messages to the API and handles retries in case of errors.
