# exceptions.py

**Path:** `src/alita_sdk/community/eda/utils/exceptions.py`

## Data Flow

The data flow within the `exceptions.py` file is relatively straightforward as it primarily deals with handling exceptions based on response codes from an API. The data originates from the response codes received from the API and is then processed by the `ResponseCodeHandler` class. Depending on the response code, different custom exceptions are raised, each carrying the `project_id` as part of the exception message. The data flow can be summarized as follows:

1. **Input:** Response code from the API.
2. **Processing:** The `process_response_code` method of the `ResponseCodeHandler` class checks the response code and raises the appropriate custom exception.
3. **Output:** A custom exception is raised with a message that includes the `project_id`.

Example:
```python
class ResponseCodeHandler:
    """This class handles response codes from the API."""
    def __init__(self, project_id):
        self.project_id = project_id

    def process_response_code(self, code):
        """Process response code from the API."""
        if code == 401:
            raise UnauthorizedAccess(self.project_id)  # Raises UnauthorizedAccess exception
        if code == 403:
            raise AbsentAccessToRepository(self.project_id)  # Raises AbsentAccessToRepository exception
        if code == 404:
            raise NotFoundException(self.project_id)  # Raises NotFoundException exception
        if code == 204:
            raise Unknown(self.project_id)  # Raises Unknown exception
```

## Functions Descriptions

### ResponseCodeHandler

**Purpose:** This class handles response codes from the API and raises appropriate exceptions based on the response code.

**Methods:**
- `__init__(self, project_id)`: Initializes the class with the `project_id`.
- `process_response_code(self, code)`: Processes the response code and raises the appropriate exception.

### NotFoundException

**Purpose:** Custom exception raised when the project is not found.

**Constructor:**
- `__init__(self, project_id)`: Initializes the exception with a message indicating no access to the project.

### AbsentAccessToRepository

**Purpose:** Custom exception raised when the user has no access to the repository.

**Constructor:**
- `__init__(self, project_id)`: Initializes the exception with a message indicating no information on merge requests in the project.

### UnauthorizedAccess

**Purpose:** Custom exception raised when the user has no access to the project.

**Constructor:**
- `__init__(self, project_id)`: Initializes the exception with a message indicating to check authentication credentials.

### Unknown

**Purpose:** Custom exception raised when the response code is unknown.

**Constructor:**
- `__init__(self, project_id)`: Initializes the exception with a message indicating an unknown response code.

## Dependencies Used and Their Descriptions

The `exceptions.py` file does not explicitly import any external dependencies. It defines custom exceptions and a handler class for processing API response codes.

## Functional Flow

The functional flow of the `exceptions.py` file is centered around the `ResponseCodeHandler` class and its method `process_response_code`. The sequence of operations is as follows:

1. **Initialization:** An instance of `ResponseCodeHandler` is created with a `project_id`.
2. **Processing Response Code:** The `process_response_code` method is called with a response code.
3. **Raising Exceptions:** Based on the response code, the method raises the appropriate custom exception.

Example:
```python
handler = ResponseCodeHandler(project_id="12345")
try:
    handler.process_response_code(401)  # This will raise UnauthorizedAccess exception
except UnauthorizedAccess as e:
    print(e)  # Output: Check yours authentication credentials for 12345
```

## Endpoints Used/Created

The `exceptions.py` file does not define or interact with any endpoints directly. It is designed to handle exceptions based on response codes, which would typically be received from API calls made elsewhere in the application.
