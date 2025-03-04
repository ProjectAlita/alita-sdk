# jira_fields.py

**Path:** `src/alita_sdk/community/eda/jira/jira_fields.py`

## Data Flow

The data flow within the `jira_fields.py` file revolves around the interaction with the JIRA API to retrieve and process custom field information. The data originates from the JIRA instance, where it is fetched using the JIRA client. The data is then processed to extract field names and their corresponding IDs, which are stored in dictionaries and lists for further use.

For example, in the `define_custom_fields_ids` method, the data flow can be traced as follows:

1. The method `get_all_fields_list` is called to fetch all fields from the JIRA instance.
2. The method `_create_custom_fields_dict` processes the field names to create a dictionary of custom fields.
3. The method `_get_custom_fields_ids` iterates over the fields to extract their IDs.

```python
all_fields, all_fields_names = self.get_all_fields_list(jira)
dict_custom_fields = self._create_custom_fields_dict(all_fields_names)
custom_fields_ids = self._get_custom_fields_ids(all_fields, dict_custom_fields)
```

In this snippet, `all_fields` and `all_fields_names` are fetched from JIRA, then processed to create `dict_custom_fields`, and finally, `custom_fields_ids` are extracted.

## Functions Descriptions

### `__init__(self, fields: dict)`

The constructor initializes the `JiraFields` class with a dictionary of fields. This dictionary maps output column names to JIRA field names.

### `define_custom_fields_ids(self, jira: JIRA) -> tuple[list, dict]`

This method defines the IDs of custom fields based on the input field names. It calls `get_all_fields_list` to fetch all fields, `_create_custom_fields_dict` to create a dictionary of custom fields, and `_get_custom_fields_ids` to extract the IDs of these fields.

### `_get_custom_fields_ids(self, all_fields: list, dict_custom_fields: dict) -> list[str]`

This private method iterates over the fields to extract the IDs of the custom fields. It compares the field names case-insensitively and appends the matching IDs to the list.

### `_create_custom_fields_dict(self, all_fields_names: list) -> dict`

This private method creates a dictionary of custom fields by splitting the input field names and checking their existence in the list of all field names. It raises a `ValueError` if any input field names are invalid.

### `get_all_fields_list(jira: JIRA) -> tuple[list, list]`

This static method fetches all fields from the JIRA instance and returns a list of fields and their names.

## Dependencies Used and Their Descriptions

### `jira`

The `jira` module is imported to interact with the JIRA API. It is used to fetch field information from the JIRA instance. The `JIRA` class from this module is used to create a client instance that communicates with JIRA.

## Functional Flow

The functional flow of the `jira_fields.py` file involves initializing the `JiraFields` class with a dictionary of fields, and then using the `define_custom_fields_ids` method to fetch and process custom field information from JIRA. The flow includes fetching all fields, creating a dictionary of custom fields, and extracting their IDs.

For example, the `define_custom_fields_ids` method orchestrates the flow by calling other methods in sequence:

1. `get_all_fields_list` to fetch all fields.
2. `_create_custom_fields_dict` to create a dictionary of custom fields.
3. `_get_custom_fields_ids` to extract the IDs of the custom fields.

## Endpoints Used/Created

The `jira_fields.py` file does not explicitly define or call any endpoints. Instead, it interacts with the JIRA API through the `jira` module to fetch field information.