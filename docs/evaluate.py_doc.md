# evaluate.py

**Path:** `src/alita_sdk/utils/evaluate.py`

## Data Flow

The data flow within `evaluate.py` begins with the instantiation of the `EvaluateTemplate` class, which requires a query string and a context dictionary as inputs. The primary data transformation occurs within the `extract` method, where the Jinja2 template engine processes the query string using the provided context. The `json_loads_filter` is applied to handle JSON string manipulations. The final output of the `extract` method is either a rendered string or an exception if the template is invalid. This output is then used in the `evaluate` method to determine if the string contains the keyword 'END', which would trigger a specific return value.

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
            result = template.render(**self.context)
        except (TemplateSyntaxError, UndefinedError):
            raise Exception("Invalid jinja template in context")
        return result
```

## Functions Descriptions

### `__new__` in `MyABC`
This function is responsible for creating new instances of classes that use `MyABC` as their metaclass. It registers the class in a meta-registry and sets an output format based on the class name.

### `__init__` in `EvaluateTemplate`
Initializes an instance of `EvaluateTemplate` with a query string and a context dictionary.

### `extract`
Processes the query string using the Jinja2 template engine and the provided context. It includes a custom filter `json_loads_filter` to handle JSON string manipulations. If the template is invalid, it raises an exception.

### `evaluate`
Calls the `extract` method and checks if the resulting string contains the keyword 'END'. If it does, it returns a specific value; otherwise, it returns the stripped result.

Example:
```python
def evaluate(self):
    value: List[Dict] = self.extract()
    if 'END' in value.strip():
        return END
    else:
        return value.strip()
```

## Dependencies Used and Their Descriptions

### `jinja2`
Used for template rendering. The `Environment` class and `TemplateSyntaxError`, `UndefinedError` exceptions are used to process and handle Jinja2 templates.

### `logging`
Used for logging information, errors, and critical issues. The `logger` object is configured to log messages at different levels.

### `langgraph.graph`
The `END` constant is imported from this module and is used as a special return value in the `evaluate` method.

### `json`
Used within the `json_loads_filter` to parse JSON strings.

## Functional Flow

1. **Class Instantiation**: An instance of `EvaluateTemplate` is created with a query string and a context dictionary.
2. **Template Extraction**: The `extract` method processes the query string using the Jinja2 template engine and the provided context.
3. **Error Handling**: If the template is invalid, an exception is raised, and a critical log is recorded.
4. **Evaluation**: The `evaluate` method checks if the extracted string contains the keyword 'END' and returns the appropriate value.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary focus is on template processing and evaluation using the Jinja2 engine.