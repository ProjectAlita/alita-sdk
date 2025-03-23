"""
This module contains class OLAPbuild, which methods allow to calculate software development life cycle (SDLC) metrics
 and write them to an Excel file.
"""

import logging

from src.metrics.closed_items_metrics import ClosedItemsMetrics
from src.metrics.flow_metrics import FlowMetrics
from src.metrics.open_items_metrics import OpenItemsMetrics
from src.metrics.queue_metrics import QueueMetrics

from src.utils.read_config import Config
from src.utils.constants import OUTPUT_METRICS_FOLDER
from src.utils.excel_manager import ExcelManager


# logging.basicConfig(level=logging.DEBUG)


class OLAPbuild:
    """
    A class to calculate software development life cycle (SDLC) metrics and write them to an Excel file.
    """
    def __init__(self, work_items, statuses_mapping, columns_to_group_by=None, aggregate_by=None):
        self.metrics = [
            ClosedItemsMetrics(work_items, statuses_mapping, columns_to_group_by, aggregate_by),
            OpenItemsMetrics(work_items, columns_to_group_by, aggregate_by),
            QueueMetrics(work_items, statuses_mapping, columns_to_group_by, aggregate_by),
            FlowMetrics(work_items, statuses_mapping, columns_to_group_by, aggregate_by)
        ]

    def save_sdlc_metrics_to_excel(self, olap_file_name):
        """
        Calculate SDLC metrics and write them to an Excel file.
        """
        Config.check_configuration(OUTPUT_METRICS_FOLDER)
        excel_manager = ExcelManager(f'{OUTPUT_METRICS_FOLDER}{olap_file_name}')
        excel_manager.create_excel_file()
        excel_sheets = (type(metric).__name__ for metric in self.metrics)
        for df_metrics, sheet_name in zip(self.calculate_olap_with_sdlc_metrics(), excel_sheets):
            excel_manager.append_df_to_excel(df_metrics, sheet_name)
            logging.info(f"Results have been saved to the file {olap_file_name} in the "
                         f"folder {OUTPUT_METRICS_FOLDER}")

    def calculate_olap_with_sdlc_metrics(self):
        """
        Calculate four sets of metrics:
        - for closed items (Lead Time, Cycle Time, count of closed work items);
        - for open items (Life Time and count of open items);
        - Queue metrcis (Throughput, WIP and Lead Time);
        - Flow Metrics.
        """
        logging.info('Start of the metrics calculation...')
        return tuple(metric.calculate() for metric in self.metrics)
