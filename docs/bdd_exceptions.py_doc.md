# bdd_exceptions.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/bdd_exceptions.py`

## Data Flow

The `bdd_exceptions.py` file defines a set of custom exception classes used within the BDD (Behavior-Driven Development) parser module. These exceptions are designed to handle various error scenarios that may arise during the parsing and validation of BDD scenarios and features. The data flow in this file is relatively straightforward as it primarily involves the instantiation and raising of these exceptions when specific error conditions are met in other parts of the BDD parser code.

For example, when a scenario is not found, the `ScenarioNotFound` exception is raised:

```python
class ScenarioNotFound(ScenarioValidationError):
    """Scenario Not Found."""
```

In this case, the data flow involves the detection of a missing scenario, which triggers the raising of the `ScenarioNotFound` exception, effectively halting the current operation and signaling the error condition to the calling code.

## Functions Descriptions

The file defines several custom exception classes, each serving a specific purpose within the BDD parser module. Here are the key exception classes and their descriptions:

1. **ScenarioIsDecoratorOnly**: This exception is raised when a scenario is used incorrectly, specifically when it is not used as a decorator.

    ```python
    class ScenarioIsDecoratorOnly(Exception):
        """Scenario can be only used as decorator."""
    ```

2. **ScenarioValidationError**: This is a base class for exceptions related to scenario validation errors.

    ```python
    class ScenarioValidationError(Exception):
        """Base class for scenario validation."""
    ```

3. **ScenarioNotFound**: This exception is raised when a scenario cannot be found.

    ```python
    class ScenarioNotFound(ScenarioValidationError):
        """Scenario Not Found."""
    ```

4. **ExamplesNotValidError**: This exception is raised when the example table provided for a scenario is not valid.

    ```python
    class ExamplesNotValidError(ScenarioValidationError):
        """Example table is not valid."""
    ```

5. **StepDefinitionNotFoundError**: This exception is raised when a step definition cannot be found.

    ```python
    class StepDefinitionNotFoundError(Exception):
        """Step definition not found."""
    ```

6. **NoScenariosFound**: This exception is raised when no scenarios are found.

    ```python
    class NoScenariosFound(Exception):
        """No scenarios found."""
    ```

7. **FeatureError**: This exception is raised when there is an error parsing a feature file. It includes a custom message format that provides details about the error, including the line number and file where the error occurred.

    ```python
    class FeatureError(Exception):
        """Feature parse error."""

        message = "{0}.\nLine number: {1}.\nLine: {2}.\nFile: {3}"

        def __str__(self) -> str:
            """String representation."""
            return self.message.format(*self.args)
    ```

## Dependencies Used and Their Descriptions

The `bdd_exceptions.py` file does not explicitly import or depend on any external libraries or modules. It solely defines custom exception classes that are likely used by other parts of the BDD parser module.

## Functional Flow

The functional flow of the `bdd_exceptions.py` file is centered around the definition of custom exception classes. These classes are instantiated and raised by other parts of the BDD parser module when specific error conditions are encountered. The flow is as follows:

1. **Definition of Exception Classes**: The file defines several custom exception classes, each tailored to handle a specific type of error related to BDD parsing and validation.

2. **Raising Exceptions**: In other parts of the BDD parser module, these exceptions are raised when corresponding error conditions are detected. For example, if a scenario is not found, the `ScenarioNotFound` exception is raised.

3. **Handling Exceptions**: The raised exceptions are caught and handled by the calling code, which may involve logging the error, halting the current operation, or taking corrective actions.

## Endpoints Used/Created

The `bdd_exceptions.py` file does not define or interact with any endpoints. Its primary role is to provide custom exception classes for error handling within the BDD parser module.