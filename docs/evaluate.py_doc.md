# evaluate.py

**Path:** `src/alita_sdk/utils/evaluate.py`

## Data Flow

The data flow within `evaluate.py` revolves around the transformation and evaluation of templates using the Jinja2 templating engine. The primary data elements are the `query` and `context` provided to the `EvaluateTemplate` class. The `query` is a string representing the template, and the `context` is a dictionary containing the data to be rendered into the template. The data flow can be summarized as follows:

1. **Initialization:** The `EvaluateTemplate` class is instantiated with the `query` and `context`.
2. **Extraction:** The `extract` method processes the `query` using the Jinja2 environment, applying the `context` to render the template.
3. **Evaluation:** The `evaluate` method calls the `extract` method and processes the result to determine if it contains the `END` marker or other values.

Example:
```python
class EvaluateTemplate(metaclass=MyABC):
    def __init__(self, query: str, context: Dict):
        self.query = query
        self.context = context

    def extract(self):
        environment = Environment()
        # Define a custom filter for JSON loading
        def json_loads_filter(json_string: str, do_replace: bool = False):
            import json
            if do_replace:
                json_string = json_string.replace("'", "\"")
            return json.loads(json_string)
        environment.filters['json_loads'] = json_loads_filter
        try:
            template = environment.from_string(self.query)
            result = template.render(**self.context)
        except (TemplateSyntaxError, UndefinedError):
            raise Exception("Invalid jinja template in context")
        return result
```

## Functions Descriptions

### `__new__` in `MyABC`

This function is responsible for creating new instances of classes that use `MyABC` as their metaclass. It registers the class in the `meta_registry` and sets the `_output_format` attribute based on the class name.

### `__init__` in `EvaluateTemplate`

The constructor initializes the `EvaluateTemplate` instance with the provided `query` and `context`.

### `extract` in `EvaluateTemplate`

This method processes the `query` using the Jinja2 environment, applying the `context` to render the template. It also defines a custom filter for JSON loading.

### `evaluate` in `EvaluateTemplate`

This method calls the `extract` method and processes the result to determine if it contains the `END` marker or other values.

## Dependencies Used and Their Descriptions

### `jinja2`

- **Purpose:** Used for template rendering.
- **Usage:** The `Environment` class from Jinja2 is used to create a template environment, and templates are rendered using the `from_string` method.

### `logging`

- **Purpose:** Used for logging information, warnings, and errors.
- **Usage:** The `logger` object is used to log messages at various levels (info, critical).

### `langgraph.graph`

- **Purpose:** Provides the `END` constant used in the evaluation process.
- **Usage:** The `END` constant is checked in the `evaluate` method to determine the end of processing.

## Functional Flow

The functional flow of `evaluate.py` involves the following steps:

1. **Class Definition:** The `MyABC` metaclass and `EvaluateTemplate` class are defined.
2. **Initialization:** An instance of `EvaluateTemplate` is created with a `query` and `context`.
3. **Extraction:** The `extract` method processes the `query` using the Jinja2 environment and the provided `context`.
4. **Evaluation:** The `evaluate` method calls the `extract` method and checks the result for the `END` marker or other values.

Example:
```python
eval_template = EvaluateTemplate(query="{{ name }}", context={"name": "Alita"})
result = eval_template.evaluate()
```

## Endpoints Used/Created

No explicit endpoints are defined or used within `evaluate.py`. The functionality is focused on template evaluation and does not involve network communication or API calls.
