# evaluate.py

**Path:** `src/alita_sdk/utils/evaluate.py`

## Data Flow

The data flow within `evaluate.py` revolves around the transformation and evaluation of templates using the Jinja2 templating engine. The primary data elements are the template query strings and the context dictionaries that provide the data for rendering these templates. The data flow begins with the instantiation of the `EvaluateTemplate` class, where the template query and context are passed as parameters. These inputs are stored as instance variables. The `extract` method is then called, which sets up the Jinja2 environment and applies a custom filter for JSON string parsing. The template is rendered using the provided context, and the result is returned. The `evaluate` method further processes this result, checking for specific conditions and returning the appropriate output.

Example:
```python
class EvaluateTemplate(metaclass=MyABC):
    def __init__(self, query: str, context: Dict):
        self.query = query
        self.context = context

    def extract(self):
        environment = Environment()

        def json_loads_filter(json_string: str, do_replace: bool = False):
            import json
            if do_replace:
                json_string = json_string.replace("'", "\"")
            return json.loads(json_string)

        environment.filters['json_loads'] = json_loads_filter
        try:
            template = environment.from_string(self.query)
            logger.info(f"Condition context: {self.context}")
            result = template.render(**self.context)
        except (TemplateSyntaxError, UndefinedError):
            logger.critical(format_exc())
            logger.info('Template str: %s', self.query)
            raise Exception("Invalid jinja template in context")
        return result
```
In this example, the `extract` method sets up the Jinja2 environment, adds a custom filter, and renders the template using the provided context.

## Functions Descriptions

### `__new__` method in `MyABC` class
This method is responsible for creating new instances of classes that use `MyABC` as their metaclass. It registers the class in a meta-registry and sets an output format based on the class name.

### `__init__` method in `EvaluateTemplate` class
Initializes an instance of `EvaluateTemplate` with a query string and a context dictionary.

### `extract` method in `EvaluateTemplate` class
Sets up the Jinja2 environment, adds a custom filter for JSON string parsing, and renders the template using the provided context. It handles exceptions related to template syntax and undefined variables.

### `evaluate` method in `EvaluateTemplate` class
Calls the `extract` method to render the template and processes the result. It checks for specific conditions in the result and returns the appropriate output.

## Dependencies Used and Their Descriptions

### `format_exc` from `traceback`
Used for formatting exception tracebacks, which is helpful for logging detailed error information.

### `List` and `Dict` from `typing`
Used for type hinting to specify that certain variables are lists or dictionaries.

### `ABCMeta` from `abc`
Used as a metaclass for creating abstract base classes.

### `Environment`, `TemplateSyntaxError`, and `UndefinedError` from `jinja2`
`Environment` is used to set up the Jinja2 templating environment. `TemplateSyntaxError` and `UndefinedError` are exceptions that are caught and handled during template rendering.

### `logging`
Used for logging information, warnings, and errors.

### `END` from `langgraph.graph`
Used as a special marker in the `evaluate` method to signify the end of processing.

## Functional Flow

1. **Class Instantiation**: An instance of `EvaluateTemplate` is created with a query string and a context dictionary.
2. **Template Extraction**: The `extract` method is called, which sets up the Jinja2 environment, adds a custom filter, and renders the template using the provided context.
3. **Error Handling**: If there are any syntax errors or undefined variables in the template, exceptions are logged and raised.
4. **Evaluation**: The `evaluate` method processes the result from `extract`, checks for specific conditions, and returns the appropriate output.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on template evaluation and transformation using the Jinja2 templating engine.