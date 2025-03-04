# excel_manager.py

**Path:** `src/alita_sdk/community/eda/utils/excel_manager.py`

## Data Flow

The data flow within the `excel_manager.py` file revolves around the creation and manipulation of Excel files using the `ExcelManager` class. The data originates from the parameters provided to the class methods, such as the file path for creating an Excel file or the DataFrame to be appended to an existing file. The data is then transformed and saved to the specified Excel file. The primary data elements include the file path (a string) and the DataFrame (a pandas DataFrame). The data is manipulated through the methods of the `ExcelManager` class, which utilize the `openpyxl` and `pandas` libraries to perform operations on the Excel files. The data flow can be summarized as follows:

1. The `ExcelManager` class is instantiated with the file path as an attribute.
2. The `create_excel_file` method creates an empty Excel file at the specified path.
3. The `append_df_to_excel` method appends a DataFrame to an existing Excel file at the specified path.

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

The constructor method initializes the `ExcelManager` class with the specified file path. It sets the `output_path` attribute to the provided path.

### `create_excel_file(self)`

This method creates an empty Excel file at the specified path. It uses the `Workbook` class from the `openpyxl` library to create a new workbook and saves it to the `output_path`.

### `append_df_to_excel(self, data: pd.DataFrame, sheet_name: str)`

This method appends a DataFrame to an existing Excel file. It uses the `ExcelWriter` class from the `pandas` library with the `openpyxl` engine to open the existing file in append mode and writes the DataFrame to the specified sheet. If the file is not found, it logs an error and raises a `FileNotFoundError`. If any other exception occurs, it logs the error and raises the exception.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used for logging error messages when exceptions occur during file operations.

### `pandas`

The `pandas` library is used for handling DataFrame operations. It provides the `ExcelWriter` class, which is used to write DataFrames to Excel files.

### `openpyxl`

The `openpyxl` library is used for creating and manipulating Excel files. It provides the `Workbook` class for creating new workbooks and is used as the engine for the `ExcelWriter` class from `pandas`.

## Functional Flow

The functional flow of the `excel_manager.py` file involves the following steps:

1. The `ExcelManager` class is instantiated with the file path as an attribute.
2. The `create_excel_file` method is called to create an empty Excel file at the specified path.
3. The `append_df_to_excel` method is called to append a DataFrame to an existing Excel file at the specified path.
4. If the file is not found, a `FileNotFoundError` is logged and raised.
5. If any other exception occurs, it is logged and raised.

## Endpoints Used/Created

The `excel_manager.py` file does not explicitly define or call any endpoints. It focuses on local file operations for creating and manipulating Excel files.