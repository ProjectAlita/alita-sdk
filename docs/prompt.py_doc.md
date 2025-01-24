# prompt.py

**Path:** `src/alita_sdk/clients/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the `AlitaPrompt` class, which is designed to handle prompt templates and predictions using the Alita SDK. The data originates from the initialization of the `AlitaPrompt` object, where various parameters such as `alita`, `prompt`, `name`, `description`, and `llm_settings` are provided. These parameters are stored as instance variables. The `create_pydantic_model` method generates a Pydantic model based on the input variables of the prompt, ensuring that all necessary fields are included. The `predict` method processes the input variables, constructs a list of messages, and uses the `alita` object to generate predictions. The results are then compiled into a single string output.

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
This snippet shows the initialization of the `AlitaPrompt` class, where the provided parameters are stored as instance variables.

## Functions Descriptions

### `__init__`
The `__init__` method initializes the `AlitaPrompt` object with the provided parameters. It sets up the instance variables `alita`, `prompt`, `name`, `description`, and `llm_settings`.

### `create_pydantic_model`
The `create_pydantic_model` method generates a Pydantic model based on the input variables of the prompt. It ensures that all necessary fields are included, with a default `input` field if not already present.

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
This snippet shows the creation of a Pydantic model with the necessary fields based on the prompt's input variables.

### `predict`
The `predict` method processes the input variables, constructs a list of messages, and uses the `alita` object to generate predictions. The results are compiled into a single string output.

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
This snippet shows the processing of input variables, construction of messages, and generation of predictions using the `alita` object.

## Dependencies Used and Their Descriptions

### `Any` and `Optional` from `typing`
These are used for type hinting, allowing for more readable and maintainable code.

### `ChatPromptTemplate` and `HumanMessage` from `langchain_core`
These are used to define the structure of the prompt and the messages involved in the prediction process.

### `create_model` from `pydantic`
This is used to dynamically create a Pydantic model based on the input variables of the prompt.

### `logging`
This is used for logging purposes, allowing for better debugging and monitoring of the code execution.

## Functional Flow

1. **Initialization**: An `AlitaPrompt` object is created with the provided parameters.
2. **Model Creation**: The `create_pydantic_model` method generates a Pydantic model based on the prompt's input variables.
3. **Prediction**: The `predict` method processes the input variables, constructs messages, and generates predictions using the `alita` object.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file.