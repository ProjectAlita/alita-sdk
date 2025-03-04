# prompt.py

**Path:** `src/alita_sdk/clients/prompt.py`

## Data Flow

The data flow within the `prompt.py` file revolves around the `AlitaPrompt` class, which is designed to handle prompt templates and predictions using the Alita SDK. The data originates from the initialization of the `AlitaPrompt` class, where various parameters such as `alita`, `prompt`, `name`, `description`, and `llm_settings` are passed. These parameters are stored as instance variables.

When the `predict` method is called, it receives an optional dictionary of variables. If no variables are provided, an empty dictionary is used. The method extracts the `input` key from the variables, which represents the user's input, and processes the remaining variables into a list of dictionaries with `name` and `value` keys. These processed variables are used as input for the Alita prediction.

The `predict` method then combines the prompt messages with the user's input to form a complete message sequence. This sequence is passed to the `alita.predict` method along with the language model settings and the processed variables. The prediction results are collected and concatenated into a single string, which is returned as the output.

Example:
```python
class AlitaPrompt:
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

## Functions Descriptions

### `__init__`

The `__init__` method initializes an instance of the `AlitaPrompt` class. It takes the following parameters:
- `alita`: An instance of the Alita SDK.
- `prompt`: A `ChatPromptTemplate` object that defines the structure of the prompt.
- `name`: A string representing the name of the prompt.
- `description`: A string describing the prompt.
- `llm_settings`: A dictionary containing settings for the language model.

This method assigns the provided parameters to instance variables for later use.

### `create_pydantic_model`

The `create_pydantic_model` method dynamically creates a Pydantic model based on the input variables defined in the prompt template. It iterates over the `input_variables` of the prompt and adds them as fields to the model. If the `input` field is not present, it is added with a default value of `None`.

Example:
```python
class AlitaPrompt:
    def create_pydantic_model(self):
        fields = {}
        for variable in self.prompt.input_variables:
            fields[variable] = (str, None)
        if "input" not in list(fields.keys()):
            fields["input"] = (str, None)
        return create_model("PromptVariables", **fields)
```

### `predict`

The `predict` method generates a prediction based on the provided variables. It takes an optional dictionary of variables as input. The method extracts the `input` key from the variables and processes the remaining variables into a list of dictionaries. It then combines the prompt messages with the user's input and passes the sequence to the `alita.predict` method. The prediction results are concatenated and returned as a single string.

Example:
```python
class AlitaPrompt:
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

## Dependencies Used and Their Descriptions

### `Any` and `Optional` from `typing`

These are used for type hinting. `Any` allows any type, and `Optional` indicates that a value can be of a specified type or `None`.

### `ChatPromptTemplate` from `langchain_core.prompts`

This is used to define the structure of the chat prompt template.

### `HumanMessage` from `langchain_core.messages`

This is used to represent a message from a human user in the chat prompt.

### `create_model` from `pydantic`

This is used to dynamically create Pydantic models based on the input variables of the prompt template.

### `logging`

This is used to set up logging for the module.

## Functional Flow

1. **Initialization**: An instance of the `AlitaPrompt` class is created with the necessary parameters (`alita`, `prompt`, `name`, `description`, `llm_settings`).
2. **Model Creation**: The `create_pydantic_model` method is called to create a Pydantic model based on the input variables of the prompt template.
3. **Prediction**: The `predict` method is called with a dictionary of variables. The method processes the variables, combines the prompt messages with the user's input, and calls the `alita.predict` method to generate predictions. The results are concatenated and returned as a single string.

## Endpoints Used/Created

The `prompt.py` file does not explicitly define or call any endpoints. The primary interaction is with the `alita.predict` method, which is assumed to be part of the Alita SDK and handles the prediction logic internally.