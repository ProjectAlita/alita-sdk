# evaluate.py

**Path:** `src/alita_sdk/utils/evaluate.py`

## Data Flow

The data flow within `evaluate.py` revolves around the transformation and evaluation of templates using the Jinja2 templating engine. The primary data elements are the template query and the context dictionary. The `EvaluateTemplate` class is initialized with these elements, and the `extract` method processes the template query using the context. The data flow can be summarized as follows:

1. **Initialization:** The `EvaluateTemplate` class is instantiated with a template query and a context dictionary.
2. **Template Processing:** The `extract` method uses the Jinja2 `Environment` to process the template query with the provided context.
3. **Error Handling:** If there are any syntax errors or undefined variables in the template, appropriate exceptions are raised and logged.
4. **Result Extraction:** The processed template result is returned and further evaluated in the `evaluate` method.

Example:
```python
class EvaluateTemplate(metaclass=MyABC):
    def __init__(self, query: str, context: Dict):
        self.query = query
        self.context = context

    def extract(self):
        environment = Environment()
        try:
            template = environment.from_string(self.query)
            result = template.render(**self.context)
        except (TemplateSyntaxError, UndefinedError):
            raise Exception("Invalid jinja template in context")
        return result
```

## Functions Descriptions

### `__new__` in `MyABC`

This function is responsible for creating new instances of classes that use `MyABC` as their metaclass. It registers the class in a meta-registry and sets an output format based on the class name.

- **Inputs:**
  - `mcs`: The metaclass.
  - `name`: The name of the class being created.
  - `bases`: The base classes of the class being created.
  - `attrs`: The attributes of the class being created.
- **Outputs:**
  - The newly created class.

### `__init__` in `EvaluateTemplate`

This function initializes an instance of the `EvaluateTemplate` class with a template query and a context dictionary.

- **Inputs:**
  - `query`: The template query string.
  - `context`: The context dictionary for rendering the template.
- **Outputs:**
  - None.

### `extract` in `EvaluateTemplate`

This function processes the template query using the Jinja2 `Environment` and the provided context. It handles errors and returns the rendered template result.

- **Inputs:**
  - None (uses instance variables `query` and `context`).
- **Outputs:**
  - The rendered template result.

### `evaluate` in `EvaluateTemplate`

This function evaluates the rendered template result. If the result contains the string 'END', it returns a special `END` value; otherwise, it returns the stripped result.

- **Inputs:**
  - None (uses the result from `extract`).
- **Outputs:**
  - The evaluated result.

## Dependencies Used and Their Descriptions

### `traceback`

- **Purpose:** Used for formatting exception tracebacks.
- **Usage:** `from traceback import format_exc`

### `typing`

- **Purpose:** Provides type hints for function signatures.
- **Usage:** `from typing import List, Dict`

### `abc`

- **Purpose:** Provides the `ABCMeta` metaclass for defining abstract base classes.
- **Usage:** `from abc import ABCMeta`

### `jinja2`

- **Purpose:** Provides the templating engine for rendering templates.
- **Usage:** `from jinja2 import Environment, TemplateSyntaxError, UndefinedError`

### `logging`

- **Purpose:** Used for logging messages and errors.
- **Usage:** `import logging`

### `langgraph.graph`

- **Purpose:** Provides the `END` constant used in the `evaluate` method.
- **Usage:** `from langgraph.graph import END`

## Functional Flow

The functional flow of `evaluate.py` involves the following steps:

1. **Class Definition:** The `MyABC` metaclass and `EvaluateTemplate` class are defined.
2. **Initialization:** An instance of `EvaluateTemplate` is created with a template query and context.
3. **Template Extraction:** The `extract` method processes the template query using the context and handles any errors.
4. **Evaluation:** The `evaluate` method evaluates the rendered template result and returns the appropriate value.

Example:
```python
eval_template = EvaluateTemplate(query="{{ name }}", context={"name": "Alita"})
result = eval_template.evaluate()
```

## Endpoints Used/Created

There are no explicit endpoints used or created in `evaluate.py`. The functionality is focused on template processing and evaluation within the code itself.