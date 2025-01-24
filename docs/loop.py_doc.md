# loop.py

**Path:** `src/alita_sdk/tools/loop.py`

## Data Flow

The data flow within `loop.py` revolves around the `LoopNode` class, which is designed to handle tool invocations in a loop. The data originates from the `invoke` method, which receives the state and configuration as inputs. The method processes these inputs to generate a list of JSON objects representing the tool's arguments. These JSON objects are then used to invoke the tool in a loop, accumulating the responses. The accumulated responses are processed and returned as the final output. The data flow can be summarized as follows:

1. **Input:** The `invoke` method receives the state and configuration.
2. **Processing:** The method generates a list of JSON objects representing the tool's arguments.
3. **Tool Invocation:** The tool is invoked in a loop using the generated JSON objects.
4. **Accumulation:** The responses from the tool invocations are accumulated.
5. **Output:** The accumulated responses are processed and returned.

Example:
```python
params = convert_to_openai_tool(self.tool).get(
    'function', {'parameters': {}}).get(
    'parameters', {'properties': {}}).get('properties', {})
parameters = ''
for key in params.keys():
    parameters += f"{key} [{params[key].get('type', 'str')}]: {params[key].get('description', '')}\n"
```
In this example, the parameters for the tool are extracted and formatted into a string.

## Functions Descriptions

### `process_response`

This function processes the response from the tool invocation and accumulates it. It takes three arguments: `response`, `return_type`, and `accumulated_response`. The function appends the response to the accumulated response based on the return type.

### `invoke`

The `invoke` method is the main function of the `LoopNode` class. It takes the state and configuration as inputs and generates a list of JSON objects representing the tool's arguments. The method then invokes the tool in a loop using these JSON objects and accumulates the responses. The accumulated responses are processed and returned as the final output.

### `_run`

The `_run` method is a wrapper for the `invoke` method. It simply calls the `invoke` method with the provided arguments.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging information, debugging messages, and errors.

### `json`

The `json` module is used for serializing and deserializing JSON data.

### `langchain_core`

The `langchain_core` module provides various utilities and classes used in the `LoopNode` class, such as `dispatch_custom_event`, `RunnableConfig`, `BaseTool`, `HumanMessage`, and `ToolCall`.

### `pydantic`

The `pydantic` module is used for data validation and settings management using Python type annotations.

### `openai`

The `openai` module is used for interacting with the OpenAI API.

## Functional Flow

The functional flow of `loop.py` involves the following steps:

1. **Initialization:** The `LoopNode` class is initialized with the necessary attributes, such as `name`, `description`, `client`, `tool`, `task`, `output_variables`, `input_variables`, `return_type`, and `prompt`.
2. **Invocation:** The `invoke` method is called with the state and configuration as inputs. It generates a list of JSON objects representing the tool's arguments and invokes the tool in a loop using these JSON objects.
3. **Accumulation:** The responses from the tool invocations are accumulated and processed.
4. **Output:** The accumulated responses are returned as the final output.

Example:
```python
completion = self.client.invoke(predict_input, config=config)
loop_data = _old_extract_json(completion.content.strip())
```
In this example, the client invokes the tool with the generated input, and the response is extracted and processed.

## Endpoints Used/Created

The `loop.py` file does not explicitly define or call any endpoints. However, it interacts with the OpenAI API through the `openai` module to invoke the tool and process the responses.