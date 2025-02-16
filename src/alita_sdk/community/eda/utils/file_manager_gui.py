"""This module contains class FileManager, which methods allows to manage file dialogs using Tkinter."""

import logging
import os

import tkinter as tk

from tkinter import filedialog


class FileManager:
    """
    A class to manage file dialogs using Tkinter.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def open_file_dialog(self) -> tuple:
        """
        Open a custom file dialog with a specified title and return the selected file paths.
        """
        self.root.attributes('-topmost', True)
        file_paths = filedialog.askopenfilenames()
        return file_paths

    def check_files_selection(self, selected_file_paths: tuple, files_to_check: tuple) -> bool:
        """
        Check if the selected files are correct.
        """
        if not selected_file_paths:
            error_message = 'No files selected!'
            logging.error(error_message)
            raise ValueError('No files selected!')
        selected_file_names = [self._get_file_name(file_path) for file_path in selected_file_paths]
        difference = 0
        for selected in selected_file_names:
            difference += int(all(item not in selected for item in files_to_check))
        if difference:
            error_message = f"You haven't selected files, which names should contain: {', '.join(files_to_check)}"
            logging.error(error_message)
            raise ValueError(error_message)
        return True

    @staticmethod
    def check_selected_files_number(file_paths: tuple, control_number: int):
        """
        Checks if the number of selected files equals the input control number.
        """
        if len(file_paths) != control_number:
            raise ValueError(f"Select {control_number} files!")

    @staticmethod
    def _get_file_name(file_path: str) -> str:
        """
        Extracts and returns the file name from the given file path.
        """
        if not isinstance(file_path, str):
            raise ValueError("The file path must be a string.")
        if not file_path:
            raise ValueError("The file path cannot be an empty string.")
        file_name = os.path.basename(file_path)
        return file_name
