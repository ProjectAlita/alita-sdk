# artifact.py

**Path:** `src/alita_sdk/tools/artifact.py`

## Data Flow

The data flow within `artifact.py` revolves around the `ArtifactWrapper` class, which acts as an interface to interact with an artifact storage system. The data originates from the client and bucket parameters provided during the instantiation of the `ArtifactWrapper` class. These parameters are validated and used to initialize the `_artifact` attribute, which represents the connection to the artifact storage.

Data transformations occur through various methods in the `ArtifactWrapper` class, such as `list_files`, `create_file`, `read_file`, `delete_file`, `append_data`, and `overwrite_data`. Each method interacts with the `_artifact` attribute to perform specific operations on the artifact storage. The data flows from the method parameters to the `_artifact` attribute, where the actual storage operations are executed.

For example, the `create_file` method takes `filename`, `filedata`, and an optional `bucket_name` as parameters. It then calls the `_artifact.create` method to store the file data in the specified bucket.

```python
class ArtifactWrapper(BaseModel):
    # ...
    def create_file(self, filename: str, filedata: str, bucket_name = None):
        return self._artifact.create(filename, filedata, bucket_name)
```

In this example, the `filename` and `filedata` parameters are passed to the `_artifact.create` method, which handles the actual file creation in the artifact storage.

## Functions Descriptions

### `validate_toolkit`

The `validate_toolkit` class method is a validator that ensures the presence of the `client` and `bucket` parameters during the instantiation of the `ArtifactWrapper` class. It raises a `ValueError` if either parameter is missing and initializes the `_artifact` attribute using the provided `client` and `bucket` values.

### `list_files`

The `list_files` method lists all files in the specified bucket. It calls the `_artifact.list` method with an optional `bucket_name` parameter to retrieve the list of files.

### `create_file`

The `create_file` method creates a new file in the specified bucket. It takes `filename`, `filedata`, and an optional `bucket_name` as parameters and calls the `_artifact.create` method to store the file data.

### `read_file`

The `read_file` method reads the content of a file from the specified bucket. It takes `filename` and an optional `bucket_name` as parameters and calls the `_artifact.get` method to retrieve the file content.

### `delete_file`

The `delete_file` method deletes a file from the specified bucket. It takes `filename` and an optional `bucket_name` as parameters and calls the `_artifact.delete` method to remove the file.

### `append_data`

The `append_data` method appends data to an existing file in the specified bucket. It takes `filename`, `filedata`, and an optional `bucket_name` as parameters and calls the `_artifact.append` method to add the data to the file.

### `overwrite_data`

The `overwrite_data` method overwrites the content of an existing file in the specified bucket. It takes `filename`, `filedata`, and an optional `bucket_name` as parameters and calls the `_artifact.overwrite` method to replace the file content.

### `create_new_bucket`

The `create_new_bucket` method creates a new bucket in the artifact storage. It takes `bucket_name`, `expiration_measure`, and `expiration_value` as parameters and calls the `_artifact.client.create_bucket` method to create the bucket with the specified expiration settings.

### `get_available_tools`

The `get_available_tools` method returns a list of available tools for interacting with the artifact storage. Each tool is represented as a dictionary containing a reference to the method, the tool's name, description, and argument schema.

### `run`

The `run` method executes a specified tool by its name. It takes `name`, `*args`, and `**kwargs` as parameters and iterates through the available tools to find and execute the matching tool. If the tool is not found, it raises a `ToolException`.

## Dependencies Used and Their Descriptions

### `langchain_core.tools.ToolException`

This dependency is used to raise exceptions related to tool execution errors. It is imported from the `langchain_core.tools` module.

### `typing.Any`, `Optional`

These dependencies are used for type hinting. `Any` represents any type, while `Optional` indicates that a value can be of a specified type or `None`.

### `pydantic`

The `pydantic` library is used for data validation and settings management. It provides the `BaseModel`, `Field`, `model_validator`, and `PrivateAttr` classes and functions used in the `ArtifactWrapper` class for defining and validating data models.

## Functional Flow

The functional flow of `artifact.py` begins with the instantiation of the `ArtifactWrapper` class, which requires `client` and `bucket` parameters. The `validate_toolkit` method validates these parameters and initializes the `_artifact` attribute.

The various methods of the `ArtifactWrapper` class (`list_files`, `create_file`, `read_file`, `delete_file`, `append_data`, `overwrite_data`, `create_new_bucket`) provide specific functionalities for interacting with the artifact storage. These methods are called as needed to perform operations on the artifact storage.

The `get_available_tools` method returns a list of available tools, and the `run` method allows executing a specified tool by its name.

## Endpoints Used/Created

The `artifact.py` file does not explicitly define or call any endpoints. Instead, it interacts with an artifact storage system through the `_artifact` attribute, which is initialized using the provided `client` and `bucket` parameters.