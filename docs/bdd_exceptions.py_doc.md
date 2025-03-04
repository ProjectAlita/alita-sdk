# bdd_exceptions.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/bdd_exceptions.py`

## Data Flow

The `bdd_exceptions.py` file defines a series of custom exception classes used within the BDD (Behavior-Driven Development) parser module. These exceptions are designed to handle specific error conditions that may arise during the parsing and validation of BDD scenarios. The data flow in this file is relatively straightforward as it primarily involves the instantiation and raising of these exceptions when certain conditions are met in other parts of the BDD parser code.

For example, the `FeatureError` class includes a custom string representation method that formats an error message with specific details:

```python
class FeatureError(Exception):
    """Feature parse error."""

    message = "{0}.\nLine number: {1}.\nLine: {2}.\nFile: {3}"

    def __str__(self) -> str:
        """String representation."""
        return self.message.format(*self.args)
```

In this snippet, the `FeatureError` class defines a template for error messages and overrides the `__str__` method to format the message with the provided arguments. This ensures that when a `FeatureError` is raised, it provides a detailed and formatted error message.

## Functions Descriptions

The file contains several custom exception classes, each serving a specific purpose within the BDD parser module:

1. **ScenarioIsDecoratorOnly**: Indicates that a scenario can only be used as a decorator.

    ```python
    class ScenarioIsDecoratorOnly(Exception):
        """Scenario can be only used as decorator."""
    ```

2. **ScenarioValidationError**: Serves as the base class for scenario validation errors.

    ```python
    class ScenarioValidationError(Exception):
        """Base class for scenario validation."""
    ```

3. **ScenarioNotFound**: Indicates that a scenario was not found.

    ```python
    class ScenarioNotFound(ScenarioValidationError):
        """Scenario Not Found."""
    ```

4. **ExamplesNotValidError**: Indicates that the example table is not valid.

    ```python
    class ExamplesNotValidError(ScenarioValidationError):
        """Example table is not valid."""
    ```

5. **StepDefinitionNotFoundError**: Indicates that a step definition was not found.

    ```python
    class StepDefinitionNotFoundError(Exception):
        """Step definition not found."""
    ```

6. **NoScenariosFound**: Indicates that no scenarios were found.

    ```python
    class NoScenariosFound(Exception):
        """No scenarios found."""
    ```

7. **FeatureError**: Indicates a feature parse error and provides a detailed error message.

    ```python
    class FeatureError(Exception):
        """Feature parse error."""

        message = "{0}.\nLine number: {1}.\nLine: {2}.\nFile: {3}"

        def __str__(self) -> str:
            """String representation."""
            return self.message.format(*self.args)
    ```

## Dependencies Used and Their Descriptions

The `bdd_exceptions.py` file does not explicitly import or call any external dependencies. It solely defines custom exception classes that are likely used by other modules within the BDD parser package. These exceptions help in handling specific error conditions and improving the readability and maintainability of the code by providing clear and descriptive error messages.

## Functional Flow

The functional flow of the `bdd_exceptions.py` file is centered around the definition of custom exception classes. These classes are designed to be raised by other parts of the BDD parser module when specific error conditions are encountered. The flow can be summarized as follows:

1. **Definition of Exception Classes**: The file defines several custom exception classes, each with a specific purpose and error message.
2. **Usage in BDD Parser**: These exceptions are raised by other modules within the BDD parser package when certain conditions are met, such as when a scenario is not found or an example table is invalid.
3. **Error Handling**: When these exceptions are raised, they provide clear and descriptive error messages that help in diagnosing and resolving issues within the BDD scenarios.

For example, the `FeatureError` class provides a detailed error message that includes the line number, line content, and file name where the error occurred. This information is crucial for debugging and fixing issues in the BDD feature files.

## Endpoints Used/Created

The `bdd_exceptions.py` file does not define or interact with any endpoints. Its primary purpose is to define custom exception classes that are used internally within the BDD parser module to handle specific error conditions.