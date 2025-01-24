# prompt.py

**Path:** `src/alita_sdk/clients/prompt.py`

## Data Flow

The data flow within the `prompt.py` file revolves around the `AlitaPrompt` class, which is designed to handle prompt templates and predictions using the Alita SDK. The data originates from the initialization of the `AlitaPrompt` class, where various parameters such as `alita`, `prompt`, `name`, `description`, and `llm_settings` are passed. These parameters are stored as instance variables.

When the `predict` method is called, it receives an optional dictionary of variables. If no variables are provided, an empty dictionary is used. The method extracts the `input` key from the variables, which represents the user's input, and prepares a list of `alita_vars` by iterating over the remaining key-value pairs in the variables dictionary. These `alita_vars` are formatted as dictionaries with `name` and `value` keys.

The method then constructs a list of messages by appending a `HumanMessage` containing the user's input to the existing prompt messages. This list of messages is passed to the `alita.predict` method along with the `llm_settings` and `alita_vars`. The predictions returned by the `alita.predict` method are collected in a result list, and the contents of the messages are joined into a single string, which is returned as the final output.

Example:
```python
# Example of data flow in the predict method
variables = {"input": "Hello, how are you?", "name": "John"}
result = alita_prompt.predict(variables)
```

## Functions Descriptions

### `__init__(self, alita: Any, prompt: ChatPromptTemplate, name: str, description: str, llm_settings: dict)`

The constructor method initializes an instance of the `AlitaPrompt` class. It takes the following parameters:
- `alita`: An instance of the Alita SDK.
- `prompt`: A `ChatPromptTemplate` object that defines the structure of the prompt.
- `name`: A string representing the name of the prompt.
- `description`: A string describing the prompt.
- `llm_settings`: A dictionary containing settings for the language model.

### `create_pydantic_model(self)`

This method creates a Pydantic model based on the input variables defined in the prompt template. It iterates over the input variables and adds them as fields to the model. If the `input` variable is not present, it adds it as a field. The method returns the created Pydantic model.

Example:
```python
# Example of creating a Pydantic model
pydantic_model = alita_prompt.create_pydantic_model()
```

### `predict(self, variables: Optional[dict] = None)`

This method generates predictions based on the provided variables. It takes an optional dictionary of variables as input. If no variables are provided, an empty dictionary is used. The method extracts the `input` key from the variables and prepares a list of `alita_vars` by iterating over the remaining key-value pairs. It constructs a list of messages by appending a `HumanMessage` containing the user's input to the existing prompt messages. The method calls the `alita.predict` method with the messages, `llm_settings`, and `alita_vars`, collects the predictions, and returns them as a single string.

Example:
```python
# Example of generating predictions
variables = {"input": "Tell me a joke.", "category": "humor"}
prediction = alita_prompt.predict(variables)
```

## Dependencies Used and Their Descriptions

### `Any` and `Optional` from `typing`

These are type hinting utilities used to specify the types of variables and function parameters.

### `ChatPromptTemplate` from `langchain_core.prompts`

This is a class used to define the structure and content of chat prompts.

### `HumanMessage` from `langchain_core.messages`

This class represents a message from a human user, used to construct the list of messages for the prompt.

### `create_model` from `pydantic`

This function is used to dynamically create Pydantic models based on the input variables of the prompt.

### `logging`

The logging module is used to configure and use loggers for debugging and information purposes.

## Functional Flow

1. **Initialization**: An instance of the `AlitaPrompt` class is created with the required parameters (`alita`, `prompt`, `name`, `description`, `llm_settings`).
2. **Creating Pydantic Model**: The `create_pydantic_model` method is called to create a Pydantic model based on the input variables of the prompt.
3. **Prediction**: The `predict` method is called with a dictionary of variables. The method extracts the `input` key, prepares `alita_vars`, constructs a list of messages, and calls the `alita.predict` method to generate predictions. The predictions are returned as a single string.

## Endpoints Used/Created

The `prompt.py` file does not explicitly define or call any endpoints. The primary functionality revolves around handling prompt templates and generating predictions using the Alita SDK.