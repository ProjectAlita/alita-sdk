# prompt.py

**Path:** `src/alita_sdk/tools/prompt.py`

## Data Flow

The data flow within `prompt.py` revolves around the `Prompt` class, which inherits from `BaseTool`. The primary data elements include the `name`, `description`, `prompt`, and `return_type` attributes of the `Prompt` class. The `prompt` attribute is particularly significant as it holds the predictive model or function that generates responses based on input variables. The data flow can be summarized as follows:

1. **Initialization:** When an instance of the `Prompt` class is created, it initializes its attributes with the provided values.
2. **Validation:** The `name` attribute undergoes validation through the `remove_spaces` method, which cleans the string by removing spaces.
3. **Execution:** The `_run` method is called with keyword arguments (`kwargs`). This method invokes the `prompt`'s `predict` method, passing the `kwargs` as input variables.
4. **Response Processing:** The `process_response` function processes the output of the `predict` method based on the `return_type`. If the `return_type` is `