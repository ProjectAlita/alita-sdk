# prompt.py

**Path:** `src/alita_sdk/tools/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the `Prompt` class, which inherits from `BaseTool`. The primary data elements include the `name`, `description`, `prompt`, and `return_type` attributes of the `Prompt` class. The `prompt` attribute is expected to be an object that can generate predictions based on input variables. The data flow can be summarized as follows:

1. **Initialization:** When an instance of the `Prompt` class is created, it initializes its attributes, including `name`, `description`, `prompt`, and `return_type`.
2. **Input Processing:** The `_run` method receives keyword arguments (`kwargs`) which are passed to the `predict` method of the `prompt` object.
3. **Prediction:** The `predict` method of the `prompt` object generates a response based on the input variables.
4. **Response Processing:** The `process_response` function processes the generated response based on the `return_type`. If the `return_type` is `