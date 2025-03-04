# artifact.py

**Path:** `src/alita_sdk/tools/artifact.py`

## Data Flow

The data flow within `artifact.py` revolves around the `ArtifactWrapper` class, which manages interactions with an artifact storage system. Data originates from the client and bucket parameters provided during the instantiation of the `ArtifactWrapper` class. These parameters are validated and used to initialize the `_artifact` attribute, which represents the connection to the artifact storage.

Data transformations occur through various methods of the `ArtifactWrapper` class, such as `list_files`, `create_file`, `read_file`, `delete_file`, `append_data`, and `overwrite_data`. Each method interacts with the `_artifact` attribute to perform operations on the artifact storage, manipulating data as needed. The final destination of the data is the artifact storage system, where files are listed, created, read, deleted, appended, or overwritten.

Example:
```python
class ArtifactWrapper(BaseModel):
    client: Any
    bucket: str
    _artifact: Any = PrivateAttr()
    
    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        if not values.get('client'):
            raise ValueError("Client is required.")
        if not values.get('bucket'):
            raise ValueError("Bucket is required.")
        cls._artifact = values['client'].artifact(values['bucket'])
        return values
```
In this snippet, the `validate_toolkit` method validates the client and bucket parameters and initializes the `_artifact` attribute.

## Functions Descriptions

### `validate_toolkit`

This class method validates the `client` and `bucket` parameters provided during the instantiation of the `ArtifactWrapper` class. If either parameter is missing, it raises a `ValueError`. It also initializes the `_artifact` attribute using the `client` and `bucket` values.

### `list_files`

This method lists all files in the specified bucket. If no bucket name is provided, it uses the default bucket associated with the `_artifact` attribute.

### `create_file`

This method creates a new file in the specified bucket with the given filename and file data. If no bucket name is provided, it uses the default bucket associated with the `_artifact` attribute.

### `read_file`

This method reads the content of a file in the specified bucket with the given filename. If no bucket name is provided, it uses the default bucket associated with the `_artifact` attribute.

### `delete_file`

This method deletes a file in the specified bucket with the given filename. If no bucket name is provided, it uses the default bucket associated with the `_artifact` attribute.

### `append_data`

This method appends data to a file in the specified bucket with the given filename. If no bucket name is provided, it uses the default bucket associated with the `_artifact` attribute.

### `overwrite_data`

This method overwrites the content of a file in the specified bucket with the given filename and new file data. If no bucket name is provided, it uses the default bucket associated with the `_artifact` attribute.

### `create_new_bucket`

This method creates a new bucket with the specified name and expiration settings. The expiration measure and value can be customized.

### `get_available_tools`

This method returns a list of available tools, each represented as a dictionary with references to the corresponding methods, names, descriptions, and argument schemas.

### `run`

This method executes a specified tool by its name, passing any provided arguments and keyword arguments. If the tool name is unknown, it raises a `ToolException`.

## Dependencies Used and Their Descriptions

### `langchain_core.tools.ToolException`

This exception is used to handle unknown tool names in the `run` method.

### `typing.Any, Optional`

These types are used for type hinting in method signatures and class attributes.

### `pydantic.create_model, BaseModel, Field, model_validator, PrivateAttr`

These Pydantic components are used to define the `ArtifactWrapper` class, validate input parameters, and manage private attributes.

## Functional Flow

1. The `ArtifactWrapper` class is instantiated with a client and bucket.
2. The `validate_toolkit` method validates the input parameters and initializes the `_artifact` attribute.
3. Various methods (`list_files`, `create_file`, `read_file`, `delete_file`, `append_data`, `overwrite_data`) perform operations on the artifact storage using the `_artifact` attribute.
4. The `create_new_bucket` method creates a new bucket with specified expiration settings.
5. The `get_available_tools` method returns a list of available tools with their details.
6. The `run` method executes a specified tool by its name, passing any provided arguments and keyword arguments.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The interactions are primarily with the artifact storage system through the `_artifact` attribute.