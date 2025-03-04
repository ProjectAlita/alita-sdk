# exceptions.py

**Path:** `src/alita_sdk/community/eda/utils/exceptions.py`

## Data Flow

The data flow within `exceptions.py` is relatively straightforward as it primarily deals with handling exceptions based on response codes. The data originates from the response codes received from an API, which are then processed to raise specific exceptions. The `ResponseCodeHandler` class is responsible for this processing. When a response code is passed to the `process_response_code` method, it checks the code and raises the corresponding exception. The data, in this case, is the response code and the project ID, which is used to instantiate the exceptions. The exceptions themselves are the final destination of the data flow, providing meaningful error messages based on the response code.

Example:
```python
class ResponseCodeHandler:
    """This class handles response codes from the API."""
    def __init__(self, project_id):
        self.project_id = project_id

    def process_response_code(self, code):
        """Process response code from the API."""
        if code == 401:
            raise UnauthorizedAccess(self.project_id)
        if code == 403:
            raise AbsentAccessToRepository(self.project_id)
        if code == 404:
            raise NotFoundException(self.project_id)
        if code == 204:
            raise Unknown(self.project_id)
```
In this example, the `process_response_code` method takes a response code and raises the appropriate exception based on the code.

## Functions Descriptions

### ResponseCodeHandler

The `ResponseCodeHandler` class is designed to handle response codes from an API. It has an `__init__` method that initializes the class with a `project_id`. The `process_response_code` method takes a response code as input and raises the appropriate exception based on the code. The method checks the code against known values (401, 403, 404, 204) and raises the corresponding exception, passing the `project_id` to the exception's constructor.

### NotFoundException

The `NotFoundException` class is an exception that is raised when a project is not found. It inherits from the base `Exception` class and takes a `project_id` as input. The exception message indicates that the user has no access to the specified project.

### AbsentAccessToRepository

The `AbsentAccessToRepository` class is an exception that is raised when the user has no access to the repository. It inherits from the base `Exception` class and takes a `project_id` as input. The exception message indicates that there is no information on merge requests in the specified project.

### UnauthorizedAccess

The `UnauthorizedAccess` class is an exception that is raised when the user has no access to the project. It inherits from the base `Exception` class and takes a `project_id` as input. The exception message indicates that the user should check their authentication credentials for the specified project.

### Unknown

The `Unknown` class is an exception that is raised when the response code is unknown. It inherits from the base `Exception` class and takes a `project_id` as input. The exception message indicates that the response code is unknown for the specified project.

## Dependencies Used and Their Descriptions

The `exceptions.py` file does not explicitly import any external dependencies. It defines custom exception classes and a handler class for processing response codes. The file relies on Python's built-in `Exception` class to create custom exceptions.

## Functional Flow

The functional flow of `exceptions.py` revolves around the `ResponseCodeHandler` class and its `process_response_code` method. When a response code is received from an API, the `process_response_code` method is called with the code as an argument. The method checks the code against known values and raises the corresponding exception. The exceptions provide meaningful error messages based on the response code, helping to identify the issue and take appropriate action.

Example:
```python
handler = ResponseCodeHandler(project_id="12345")
try:
    handler.process_response_code(401)
except UnauthorizedAccess as e:
    print(e)
```
In this example, the `ResponseCodeHandler` is instantiated with a `project_id`. The `process_response_code` method is called with a response code of 401, which raises an `UnauthorizedAccess` exception. The exception is caught in the `except` block, and the error message is printed.

## Endpoints Used/Created

The `exceptions.py` file does not define or interact with any endpoints directly. It is designed to handle response codes that are presumably received from API calls made elsewhere in the project. The file focuses on defining custom exceptions and a handler class for processing these response codes.