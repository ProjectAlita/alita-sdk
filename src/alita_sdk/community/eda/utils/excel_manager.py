"""This module contains class ExcelManager to work with local Excl files (create, append etc.)"""

import logging

import pandas as pd

from openpyxl import Workbook


class ExcelManager:
    """
    This class is responsible for working with Excel files (creation, update etc.) on a local machine.

    Attributes:
        output_path: str
            The path to the Excel file.
    """

    def __init__(self, output_path: str):
        self.output_path = output_path

    def create_excel_file(self):
        """
        Create an empty Excel file.

        Parameters:
        - output_path (str): The path where the empty Excel file will be saved.
        """
        wb = Workbook()
        wb.save(self.output_path)

    def append_df_to_excel(self, data: pd.DataFrame, sheet_name: str):
        """
        Append a DataFrame to an existing Excel file.
        """
        try:
            with pd.ExcelWriter(self.output_path, engine='openpyxl', mode='a') as writer:
                data.to_excel(writer, sheet_name=sheet_name, index=False)
        except FileNotFoundError as err:
            logging.error(f"File not found: {err}")
            raise
        except Exception as ex:
            logging.error(f"An error occurred: {ex}")
            raise
