# artifact.py

**Path:** `src/alita_sdk/clients/artifact.py`

## Data Flow

The data flow within the `artifact.py` file revolves around the `Artifact` class, which manages the creation, retrieval, deletion, listing, appending, and overwriting of artifacts in a specified bucket. The data originates from the client and is manipulated through various methods of the `Artifact` class. The data is typically in the form of strings or binary data, which are then encoded or decoded as necessary. The flow of data can be summarized as follows:

1. **Initialization:** The `Artifact` class is initialized with a client and a bucket name. If the bucket does not exist, it is created.
2. **Creation:** The `create` method takes an artifact name and data, and stores it in the specified bucket.
3. **Retrieval:** The `get` method retrieves the artifact data from the bucket, detects its encoding, and returns it as a string.
4. **Deletion:** The `delete` method removes the specified artifact from the bucket.
5. **Listing:** The `list` method returns a list of all artifacts in the bucket.
6. **Appending:** The `append` method retrieves the existing artifact data, appends new data to it, and stores it back in the bucket.
7. **Overwriting:** The `overwrite` method replaces the existing artifact data with new data.

Example:
```python
class Artifact:
    def __init__(self, client: Any, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        if not self.client.bucket_exists(bucket_name):
            self.client.create_bucket(bucket_name)
```
In this example, the `Artifact` class is initialized with a client and a bucket name. If the bucket does not exist, it is created.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `Artifact` class with a client and a bucket name. It checks if the bucket exists, and if not, it creates the bucket.

**Parameters:**
- `client` (Any): The client used to interact with the storage service.
- `bucket_name` (str): The name of the bucket where artifacts are stored.

### `create`

The `create` method creates a new artifact in the specified bucket.

**Parameters:**
- `artifact_name` (str): The name of the artifact to be created.
- `artifact_data` (Any): The data of the artifact to be created.
- `bucket_name` (str, optional): The name of the bucket where the artifact will be created. Defaults to the bucket name provided during initialization.

**Returns:**
- `str`: A JSON string representing the created artifact.

### `get`

The `get` method retrieves an artifact from the specified bucket.

**Parameters:**
- `artifact_name` (str): The name of the artifact to be retrieved.
- `bucket_name` (str, optional): The name of the bucket where the artifact is stored. Defaults to the bucket name provided during initialization.

**Returns:**
- `str`: The data of the retrieved artifact as a string.

### `delete`

The `delete` method deletes an artifact from the specified bucket.

**Parameters:**
- `artifact_name` (str): The name of the artifact to be deleted.
- `bucket_name` (str, optional): The name of the bucket where the artifact is stored. Defaults to the bucket name provided during initialization.

### `list`

The `list` method lists all artifacts in the specified bucket.

**Parameters:**
- `bucket_name` (str, optional): The name of the bucket where the artifacts are stored. Defaults to the bucket name provided during initialization.

**Returns:**
- `str`: A JSON string representing the list of artifacts.

### `append`

The `append` method appends data to an existing artifact in the specified bucket.

**Parameters:**
- `artifact_name` (str): The name of the artifact to be appended to.
- `additional_data` (Any): The data to be appended to the artifact.
- `bucket_name` (str, optional): The name of the bucket where the artifact is stored. Defaults to the bucket name provided during initialization.

**Returns:**
- `str`: A message indicating the success or failure of the append operation.

### `overwrite`

The `overwrite` method overwrites an existing artifact with new data in the specified bucket.

**Parameters:**
- `artifact_name` (str): The name of the artifact to be overwritten.
- `new_data` (Any): The new data to overwrite the artifact with.
- `bucket_name` (str, optional): The name of the bucket where the artifact is stored. Defaults to the bucket name provided during initialization.

**Returns:**
- `str`: A JSON string representing the created artifact.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used to specify type hints for the parameters and return values of the functions.

### `json`

The `json` module is used to convert Python objects to JSON strings and vice versa.

### `chardet`

The `chardet` module is used to detect the encoding of the artifact data.

### `logging`

The `logging` module is used to log error messages.

## Functional Flow

1. **Initialization:** The `Artifact` class is initialized with a client and a bucket name. If the bucket does not exist, it is created.
2. **Creation:** The `create` method takes an artifact name and data, and stores it in the specified bucket.
3. **Retrieval:** The `get` method retrieves the artifact data from the bucket, detects its encoding, and returns it as a string.
4. **Deletion:** The `delete` method removes the specified artifact from the bucket.
5. **Listing:** The `list` method returns a list of all artifacts in the bucket.
6. **Appending:** The `append` method retrieves the existing artifact data, appends new data to it, and stores it back in the bucket.
7. **Overwriting:** The `overwrite` method replaces the existing artifact data with new data.

## Endpoints Used/Created

There are no explicit endpoints used or created in the `artifact.py` file. The functionality is based on the interaction with the client provided during the initialization of the `Artifact` class.