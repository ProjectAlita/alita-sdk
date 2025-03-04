# olap_cube.py

**Path:** `src/alita_sdk/community/eda/utils/olap_cube.py`

## Data Flow

The data flow within the `olap_cube.py` file revolves around the calculation of software development life cycle (SDLC) metrics and their subsequent storage in an Excel file. The data originates from the `work_items` and `statuses_mapping` parameters passed to the `OLAPbuild` class. These parameters are used to initialize various metric calculation classes such as `ClosedItemsMetrics`, `OpenItemsMetrics`, `QueueMetrics`, and `FlowMetrics`. The data is then processed through these classes to compute different sets of metrics. Finally, the results are written to an Excel file using the `ExcelManager` class.

Example:
```python
class OLAPbuild:
    def __init__(self, work_items, statuses_mapping, columns_to_group_by=None, aggregate_by=None):
        self.metrics = [
            ClosedItemsMetrics(work_items, statuses_mapping, columns_to_group_by, aggregate_by),
            OpenItemsMetrics(work_items, columns_to_group_by, aggregate_by),
            QueueMetrics(work_items, statuses_mapping, columns_to_group_by, aggregate_by),
            FlowMetrics(work_items, statuses_mapping, columns_to_group_by, aggregate_by)
        ]
```
In this snippet, the `work_items` and `statuses_mapping` are passed to initialize the metric calculation classes, which will process the data to compute the metrics.

## Functions Descriptions

### `__init__`
The `__init__` method initializes the `OLAPbuild` class with the provided `work_items`, `statuses_mapping`, `columns_to_group_by`, and `aggregate_by` parameters. It creates instances of various metric calculation classes and stores them in the `self.metrics` list.

### `save_sdlc_metrics_to_excel`
This method calculates the SDLC metrics and writes them to an Excel file. It first checks the configuration using the `Config.check_configuration` method, then creates an Excel file using the `ExcelManager` class. It iterates over the calculated metrics and appends them to the Excel file.

Example:
```python
def save_sdlc_metrics_to_excel(self, olap_file_name):
    Config.check_configuration(OUTPUT_METRICS_FOLDER)
    excel_manager = ExcelManager(f'{OUTPUT_METRICS_FOLDER}{olap_file_name}')
    excel_manager.create_excel_file()
    excel_sheets = (type(metric).__name__ for metric in self.metrics)
    for df_metrics, sheet_name in zip(self.calculate_olap_with_sdlc_metrics(), excel_sheets):
        excel_manager.append_df_to_excel(df_metrics, sheet_name)
        logging.info(f"Results have been saved to the file {olap_file_name} in the "
                     f"folder {OUTPUT_METRICS_FOLDER}")
```

### `calculate_olap_with_sdlc_metrics`
This method calculates four sets of metrics: for closed items, open items, queue metrics, and flow metrics. It logs the start of the metrics calculation and returns a tuple of the calculated metrics.

Example:
```python
def calculate_olap_with_sdlc_metrics(self):
    logging.info('Start of the metrics calculation...')
    return tuple(metric.calculate() for metric in self.metrics)
```

## Dependencies Used and Their Descriptions

### `logging`
Used for logging information, warnings, and errors. Configured to log at the DEBUG level.

### `ClosedItemsMetrics`, `FlowMetrics`, `OpenItemsMetrics`, `QueueMetrics`
These are custom classes imported from the `src.metrics` module. They are used to calculate different sets of SDLC metrics.

### `Config`
A custom class imported from `src.utils.read_config`. It is used to check the configuration before saving the metrics to an Excel file.

### `OUTPUT_METRICS_FOLDER`
A constant imported from `src.utils.constants`. It specifies the folder where the output Excel file will be saved.

### `ExcelManager`
A custom class imported from `src.utils.excel_manager`. It is used to create and manage the Excel file where the metrics will be saved.

## Functional Flow

1. **Initialization**: The `OLAPbuild` class is initialized with the provided parameters, creating instances of various metric calculation classes.
2. **Calculate Metrics**: The `calculate_olap_with_sdlc_metrics` method is called to calculate the metrics.
3. **Save to Excel**: The `save_sdlc_metrics_to_excel` method is called to save the calculated metrics to an Excel file.

## Endpoints Used/Created

No endpoints are explicitly defined or called within this file.