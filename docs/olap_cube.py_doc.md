# olap_cube.py

**Path:** `src/alita_sdk/community/eda/utils/olap_cube.py`

## Data Flow

The data flow within the `olap_cube.py` file revolves around the calculation of software development life cycle (SDLC) metrics and their subsequent storage in an Excel file. The data originates from the `work_items` and `statuses_mapping` parameters provided to the `OLAPbuild` class. These inputs are used to instantiate various metric calculation classes such as `ClosedItemsMetrics`, `OpenItemsMetrics`, `QueueMetrics`, and `FlowMetrics`. The data is then processed through these classes to compute different sets of metrics. The results are temporarily stored in data frames before being written to an Excel file using the `ExcelManager` class. The final destination of the data is the specified Excel file within the `OUTPUT_METRICS_FOLDER`.

Example:
```python
# Example of data transformation in calculate_olap_with_sdlc_metrics method
return tuple(metric.calculate() for metric in self.metrics)
```
In this example, the `calculate` method of each metric class processes the input data and returns the computed metrics, which are then collected into a tuple.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `OLAPbuild` class with the provided `work_items`, `statuses_mapping`, `columns_to_group_by`, and `aggregate_by` parameters. It creates instances of various metric calculation classes and stores them in the `self.metrics` list.

### `save_sdlc_metrics_to_excel`

This method calculates the SDLC metrics and writes them to an Excel file. It first checks the configuration of the output folder, creates an Excel file, and then appends the calculated metrics to the file, logging the process.

### `calculate_olap_with_sdlc_metrics`

This method calculates four sets of metrics: for closed items, open items, queue metrics, and flow metrics. It logs the start of the calculation process and returns a tuple of the calculated metrics.

Example:
```python
# Example of save_sdlc_metrics_to_excel method
excel_manager = ExcelManager(f'{OUTPUT_METRICS_FOLDER}{olap_file_name}')
excel_manager.create_excel_file()
for df_metrics, sheet_name in zip(self.calculate_olap_with_sdlc_metrics(), excel_sheets):
    excel_manager.append_df_to_excel(df_metrics, sheet_name)
    logging.info(f"Results have been saved to the file {olap_file_name} in the folder {OUTPUT_METRICS_FOLDER}")
```
In this example, the `ExcelManager` class is used to create and manage the Excel file, and the calculated metrics are appended to it.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging information during the execution of the code.

### `ClosedItemsMetrics`, `FlowMetrics`, `OpenItemsMetrics`, `QueueMetrics`

These are custom classes imported from the `src.metrics` module, used for calculating different sets of SDLC metrics.

### `Config`

A custom class from `src.utils.read_config` used to check the configuration of the output folder.

### `OUTPUT_METRICS_FOLDER`

A constant from `src.utils.constants` that specifies the folder where the output Excel file will be stored.

### `ExcelManager`

A custom class from `src.utils.excel_manager` used to create and manage the Excel file where the metrics are stored.

## Functional Flow

The functional flow of the `olap_cube.py` file begins with the instantiation of the `OLAPbuild` class, followed by the invocation of its methods to calculate and store SDLC metrics. The process starts with the `__init__` method, which initializes the necessary metric calculation classes. The `save_sdlc_metrics_to_excel` method is then called to calculate the metrics and write them to an Excel file. This method internally calls `calculate_olap_with_sdlc_metrics` to perform the actual metric calculations. The results are logged and stored in the specified output folder.

Example:
```python
# Example of functional flow
olap_builder = OLAPbuild(work_items, statuses_mapping)
olap_builder.save_sdlc_metrics_to_excel('sdlc_metrics.xlsx')
```
In this example, an instance of `OLAPbuild` is created, and the `save_sdlc_metrics_to_excel` method is called to calculate and store the metrics.

## Endpoints Used/Created

No explicit endpoints are defined or used within the `olap_cube.py` file.