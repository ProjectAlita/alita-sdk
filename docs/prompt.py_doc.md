# prompt.py

**Path:** `src/alita_sdk/clients/prompt.py`

## Data Flow

The data flow within `prompt.py` begins with the initialization of the `AlitaPrompt` class, which takes in several parameters including `alita`, `prompt`, `name`, `description`, and `llm_settings`. These parameters are stored as instance variables. The `create_pydantic_model` method generates a Pydantic model based on the input variables defined in the `ChatPromptTemplate`. This model is used to validate and structure the input data.

When the `predict` method is called, it processes the input variables, constructs a list of messages by appending a `HumanMessage` with the user input to the existing prompt messages, and then calls the `alita.predict` method. The results from the prediction are collected and returned as a concatenated string.

Example:
```python
class AlitaPrompt:
    def __init__(self, alita: Any, prompt: ChatPromptTemplate, name: str, description: str, llm_settings: dict):
        self.alita = alita
        self.prompt = prompt
        self.name = name
        self.llm_settings = llm_settings
        self.description = description
```
This snippet shows the initialization of the `AlitaPrompt` class, where the input parameters are stored as instance variables.

## Functions Descriptions

### `__init__`
The `__init__` method initializes the `AlitaPrompt` class with the provided parameters. It sets up the instance variables for `alita`, `prompt`, `name`, `description`, and `llm_settings`.

### `create_pydantic_model`
This method creates a Pydantic model named `PromptVariables` based on the input variables defined in the `ChatPromptTemplate`. It ensures that each input variable is a string and adds an additional `input` field if it is not already present.

Example:
```python
def create_pydantic_model(self):
    fields = {}
    for variable in self.prompt.input_variables:
        fields[variable] = (str, None)
    if "input" not in list(fields.keys()):
        fields["input"] = (str, None)
    return create_model("PromptVariables", **fields)
```
This snippet shows the creation of the Pydantic model with the necessary fields.

### `predict`
The `predict` method processes the input variables, constructs the messages for the prompt, and calls the `alita.predict` method to get the predictions. It returns the concatenated results as a string.

Example:
```python
def predict(self, variables: Optional[dict] = None):
    if variables is None:
        variables = {}
    user_input = variables.pop("input", '')
    alita_vars = []
    for key, value in variables.items():
        alita_vars.append({
            "name": key,
            "value": value
        })
        
    messages = self.prompt.messages + [HumanMessage(content=user_input)]
    result = []
    for message in self.alita.predict(messages, self.llm_settings, variables=alita_vars):
        result.append(message.content)
    return "\n\n".join(result)
```
This snippet shows the processing of input variables and the construction of messages for prediction.

## Dependencies Used and Their Descriptions

### `Any` and `Optional` from `typing`
These are used for type hinting to indicate that a variable can be of any type or optional.

### `ChatPromptTemplate` from `langchain_core.prompts`
This is used to define the structure and content of the chat prompt.

### `HumanMessage` from `langchain_core.messages`
This is used to represent a message from a human user in the chat prompt.

### `create_model` from `pydantic`
This is used to dynamically create a Pydantic model for validating and structuring input data.

### `logging`
This is used to set up logging for the module.

## Functional Flow

1. **Initialization**: The `AlitaPrompt` class is initialized with the provided parameters.
2. **Model Creation**: The `create_pydantic_model` method generates a Pydantic model based on the input variables.
3. **Prediction**: The `predict` method processes the input variables, constructs the messages, and calls the `alita.predict` method to get the predictions.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file.