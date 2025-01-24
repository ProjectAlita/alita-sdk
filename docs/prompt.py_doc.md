# prompt.py

**Path:** `src/alita_sdk/clients/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the `AlitaPrompt` class, which is designed to handle prompt templates and predictions using the Alita SDK. The data originates from the initialization of the `AlitaPrompt` object, where various parameters such as `alita`, `prompt`, `name`, `description`, and `llm_settings` are provided. These parameters are stored as instance variables.

When the `predict` method is called, it receives an optional dictionary of variables. If no variables are provided, an empty dictionary is used. The method extracts the `input` key from the variables, which represents the user's input, and prepares a list of `alita_vars` containing the remaining variables. These variables are formatted as dictionaries with `name` and `value` keys.

The method then constructs a list of messages by appending the user's input as a `HumanMessage` to the existing prompt messages. This list of messages is passed to the `alita.predict` method, along with the `llm_settings` and `alita_vars`. The predictions returned by the `alita.predict` method are collected and concatenated into a single string, which is returned as the result.

Example:
```python
# Example of data flow in the predict method
variables = {'input': 'Hello, world!', 'context': 'Greeting'}
result = alita_prompt.predict(variables)
```

## Functions Descriptions

### `__init__(self, alita: Any, prompt: ChatPromptTemplate, name: str, description: str, llm_settings: dict)`

The constructor initializes the `AlitaPrompt` object with the provided parameters. It sets up the instance variables `alita`, `prompt`, `name`, `description`, and `llm_settings`.

### `create_pydantic_model(self)`

This method creates a Pydantic model based on the input variables of the prompt. It iterates over the `input_variables` of the prompt and adds them as fields to the model. If the `input` field is not present, it adds it as well. The method returns the created Pydantic model.

### `predict(self, variables: Optional[dict] = None)`

The `predict` method generates predictions based on the provided variables. It extracts the `input` key from the variables and prepares a list of `alita_vars` containing the remaining variables. It constructs a list of messages by appending the user's input as a `HumanMessage` to the existing prompt messages. The method calls `alita.predict` with the messages, `llm_settings`, and `alita_vars`, and returns the concatenated predictions as a single string.

Example:
```python
# Example of predict method
variables = {'input': 'Tell me a joke.', 'category': 'humor'}
result = alita_prompt.predict(variables)
```

## Dependencies Used and Their Descriptions

### `Any` and `Optional` from `typing`

These are used for type hinting. `Any` allows any type, and `Optional` indicates that a value can be of a specified type or `None`.

### `ChatPromptTemplate` from `langchain_core.prompts`

This is used to define the structure of the prompt template that the `AlitaPrompt` class will use.

### `HumanMessage` from `langchain_core.messages`

This is used to represent the user's input message in the list of messages passed to the `alita.predict` method.

### `create_model` from `pydantic`

This is used to dynamically create a Pydantic model based on the input variables of the prompt.

### `logging`

The logging module is used to set up a logger for the module, which can be used to log messages for debugging and monitoring purposes.

## Functional Flow

1. **Initialization**: An `AlitaPrompt` object is created with the necessary parameters.
2. **Model Creation**: The `create_pydantic_model` method is called to create a Pydantic model based on the prompt's input variables.
3. **Prediction**: The `predict` method is called with a dictionary of variables. The method processes the variables, constructs a list of messages, and calls `alita.predict` to generate predictions. The predictions are concatenated and returned as a single string.

## Endpoints Used/Created

The `prompt.py` file does not explicitly define or call any endpoints. The primary interaction is with the `alita.predict` method, which is assumed to be part of the Alita SDK and handles the prediction logic internally.