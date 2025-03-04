# jira_fields.py

**Path:** `src/alita_sdk/community/eda/jira/jira_fields.py`

## Data Flow

The data flow within the `jira_fields.py` file revolves around the interaction with the JIRA API to fetch and process custom field information. The data originates from the JIRA instance, where it retrieves all available fields using the `jira.fields()` method. This data is then processed to extract specific custom field IDs based on the input field names provided during the class initialization. The data undergoes several transformations, including filtering, dictionary creation, and ID extraction, before being returned as a tuple containing the custom field IDs and a dictionary of custom fields.

Example:
```python
all_fields, all_fields_names = self.get_all_fields_list(jira)
dict_custom_fields = self._create_custom_fields_dict(all_fields_names)
custom_fields_ids = self._get_custom_fields_ids(all_fields, dict_custom_fields)
return custom_fields_ids, dict_custom_fields
```
In this snippet, the data flows from fetching all fields from JIRA, creating a dictionary of custom fields, extracting their IDs, and finally returning the processed data.

## Functions Descriptions

### `__init__(self, fields: dict)`

This is the constructor method for the `JiraFields` class. It initializes the class with a dictionary of field names. The `fields` attribute stores this dictionary for later use in other methods.

### `define_custom_fields_ids(self, jira: JIRA) -> tuple[list, dict]`

This method defines the custom field IDs based on the input field names. It calls other helper methods to fetch all fields from JIRA, create a dictionary of custom fields, and extract their IDs. It returns a tuple containing the custom field IDs and the dictionary of custom fields.

### `_get_custom_fields_ids(self, all_fields: list, dict_custom_fields: dict) -> list[str]`

This private method iterates over the provided fields and matches them with the custom field names to extract their IDs. It returns a list of custom field IDs.

### `_create_custom_fields_dict(self, all_fields_names: list) -> dict`

This private method creates a dictionary with the keys as output column names and values as lists of field names in JIRA. It also checks if the input fields exist in the JIRA instance and raises a `ValueError` if any fields are missing.

### `get_all_fields_list(jira: JIRA) -> tuple[list, list]`

This static method fetches all fields from the JIRA instance and returns a tuple containing the list of all fields and their names.

## Dependencies Used and Their Descriptions

### `jira`

The `jira` module is imported to interact with the JIRA API. It is used to create a JIRA instance and fetch field information from JIRA. The `JIRA` class from this module is essential for making API calls to retrieve data about fields in the JIRA instance.

## Functional Flow

1. **Initialization**: The `JiraFields` class is initialized with a dictionary of field names.
2. **Define Custom Fields IDs**: The `define_custom_fields_ids` method is called with a JIRA instance. This method orchestrates the process of fetching all fields, creating a custom fields dictionary, and extracting custom field IDs.
3. **Fetch All Fields**: The `get_all_fields_list` method is called to retrieve all fields from the JIRA instance.
4. **Create Custom Fields Dictionary**: The `_create_custom_fields_dict` method is called to create a dictionary of custom fields and validate their existence.
5. **Extract Custom Field IDs**: The `_get_custom_fields_ids` method is called to extract the IDs of the custom fields based on the input field names.
6. **Return Data**: The `define_custom_fields_ids` method returns the custom field IDs and the custom fields dictionary.

## Endpoints Used/Created

The `jira_fields.py` file does not explicitly define or call any endpoints. However, it interacts with the JIRA API through the `jira` module to fetch field information from the JIRA instance.