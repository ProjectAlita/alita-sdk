# utils.py

**Path:** `src/alita_sdk/community/utils.py`

## Data Flow

The data flow within `utils.py` is straightforward and revolves around the validation of a Pydantic model's schema. The primary function, `check_schema`, takes a Pydantic `BaseModel` instance as input. It then creates a `SchemaValidator` using the model's core schema and validates the model's data dictionary against this schema. The data originates from the `BaseModel` instance, is transformed into a schema validator, and is finally validated. This process ensures that the data adheres to the defined schema, catching any discrepancies early.

Example:
```python
from pydantic import BaseModel
from pydantic_core import SchemaValidator

def check_schema(model: BaseModel) -> None:
    schema_validator = SchemaValidator(schema=model.__pydantic_core_schema__)
    schema_validator.validate_python(model.__dict__)

# Example usage
class MyModel(BaseModel):
    name: str
    age: int

model_instance = MyModel(name="John", age=30)
check_schema(model_instance)  # Validates the model instance
```
In this example, `MyModel` is a Pydantic model with `name` and `age` fields. An instance of `MyModel` is created and passed to `check_schema` for validation.

## Functions Descriptions

### `check_schema`

The `check_schema` function is designed to validate a Pydantic model's schema. It accepts a single parameter, `model`, which is an instance of `BaseModel`. The function performs the following steps:
1. Creates a `SchemaValidator` using the model's core schema.
2. Validates the model's data dictionary against the schema.

Inputs:
- `model` (BaseModel): The Pydantic model instance to be validated.

Processing:
- The model's core schema is accessed via `model.__pydantic_core_schema__`.
- A `SchemaValidator` is instantiated with this schema.
- The model's data dictionary (`model.__dict__`) is validated using the schema validator.

Outputs:
- None. The function raises an exception if validation fails.

Example:
```python
from pydantic import BaseModel
from pydantic_core import SchemaValidator

def check_schema(model: BaseModel) -> None:
    schema_validator = SchemaValidator(schema=model.__pydantic_core_schema__)
    schema_validator.validate_python(model.__dict__)

# Example usage
class MyModel(BaseModel):
    name: str
    age: int

model_instance = MyModel(name="John", age=30)
check_schema(model_instance)  # Validates the model instance
```
In this example, the `check_schema` function validates an instance of `MyModel`, ensuring it adheres to the defined schema.

## Dependencies Used and Their Descriptions

### `pydantic`

The `pydantic` library is used for data validation and settings management using Python type annotations. In `utils.py`, it provides the `BaseModel` class, which is the base class for creating data models with type validation.

### `pydantic_core`

The `pydantic_core` library provides the `SchemaValidator` class, which is used to validate data against a schema. In `utils.py`, it is used to create a schema validator for the Pydantic model's core schema.

## Functional Flow

The functional flow in `utils.py` is centered around the `check_schema` function. When this function is called, it performs the following steps:
1. Receives a Pydantic model instance as input.
2. Accesses the model's core schema.
3. Creates a `SchemaValidator` using the core schema.
4. Validates the model's data dictionary against the schema.
5. Raises an exception if validation fails.

This flow ensures that any Pydantic model passed to `check_schema` is validated against its schema, catching any data inconsistencies early.

## Endpoints Used/Created

There are no endpoints used or created in `utils.py`. The file focuses solely on schema validation for Pydantic models.