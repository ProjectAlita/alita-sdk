# excel_manager.py

**Path:** `src/alita_sdk/community/eda/utils/excel_manager.py`

## Data Flow

The data flow within the `excel_manager.py` file revolves around the creation and manipulation of Excel files using the `ExcelManager` class. The data originates from the parameters provided to the class methods, such as the file path for creating an Excel file or the DataFrame to be appended to an existing Excel file. The data is then transformed and saved to the specified Excel file. The primary data elements include the file path (a string) and the DataFrame (a pandas DataFrame). The data flow can be summarized as follows:

1. **Initialization:** The `ExcelManager` class is initialized with the `output_path` parameter, which specifies the path to the Excel file.
2. **Creating an Excel File:** The `create_excel_file` method creates an empty Excel file at the specified `output_path`.
3. **Appending Data to Excel:** The `append_df_to_excel` method takes a DataFrame and a sheet name as parameters and appends the DataFrame to the specified sheet in the existing Excel file.

Example:
```python
class ExcelManager:
    def __init__(self, output_path: str):
        self.output_path = output_path

    def create_excel_file(self):
        wb = Workbook()
        wb.save(self.output_path)

    def append_df_to_excel(self, data: pd.DataFrame, sheet_name: str):
        try:
            with pd.ExcelWriter(self.output_path, engine='openpyxl', mode='a') as writer:
                data.to_excel(writer, sheet_name=sheet_name, index=False)
        except FileNotFoundError as err:
            logging.error(f"File not found: {err}")
            raise
        except Exception as ex:
            logging.error(f"An error occurred: {ex}")
            raise
```

## Functions Descriptions

### `__init__(self, output_path: str)`

The constructor method initializes the `ExcelManager` class with the `output_path` parameter, which specifies the path to the Excel file. This path is stored as an instance attribute for use in other methods.

### `create_excel_file(self)`

This method creates an empty Excel file at the specified `output_path`. It uses the `Workbook` class from the `openpyxl` library to create a new workbook and saves it to the `output_path`.

### `append_df_to_excel(self, data: pd.DataFrame, sheet_name: str)`

This method appends a DataFrame to an existing Excel file. It takes two parameters: `data`, which is the DataFrame to be appended, and `sheet_name`, which is the name of the sheet where the DataFrame will be appended. The method uses the `ExcelWriter` class from the `pandas` library with the `openpyxl` engine to open the existing Excel file in append mode and write the DataFrame to the specified sheet. It includes error handling for `FileNotFoundError` and general exceptions, logging the errors and re-raising them.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging error messages when exceptions occur. It helps in debugging and tracking issues during the execution of the methods.

### `pandas as pd`

The `pandas` library is used for handling DataFrames, which are a key data structure for storing and manipulating tabular data. The `ExcelWriter` class from `pandas` is used to write DataFrames to Excel files.

### `openpyxl`

The `openpyxl` library is used for creating and manipulating Excel files. The `Workbook` class is used to create new Excel workbooks, and the `openpyxl` engine is used with `ExcelWriter` to append data to existing Excel files.

## Functional Flow

The functional flow of the `excel_manager.py` file involves the following steps:

1. **Initialization:** An instance of the `ExcelManager` class is created with the `output_path` parameter.
2. **Creating an Excel File:** The `create_excel_file` method is called to create an empty Excel file at the specified `output_path`.
3. **Appending Data to Excel:** The `append_df_to_excel` method is called with a DataFrame and a sheet name to append the DataFrame to the specified sheet in the existing Excel file. The method handles errors and logs them if they occur.

Example:
```python
# Initialize the ExcelManager with the output path
excel_manager = ExcelManager("path/to/excel_file.xlsx")

# Create an empty Excel file
excel_manager.create_excel_file()

# Append a DataFrame to the Excel file
data = pd.DataFrame({"Column1": [1, 2, 3], "Column2": [4, 5, 6]})
excel_manager.append_df_to_excel(data, "Sheet1")
```

## Endpoints Used/Created

The `excel_manager.py` file does not explicitly define or call any endpoints. It focuses on local file operations related to Excel files.