"""This module contains functions to check the input parameters."""

import re
import logging
from os import path
import six


def check_input_date(date_str: str) -> None:
    """
    Checks if the input date is in the correct format.

    Parameters
    ----------
    date_str : str
        The date to check.

    Returns None
    """
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        logging.error('The since_date parameter must be in the format YYYY-MM-DD')
        raise ValueError('The since_date parameter must be in the format YYYY-MM-DD')


def check_if_open(path_to_csv):
    """
    Checks if the file is open. If so, asks to close it.
    """
    print(f'Checking if {path_to_csv} is not open')
    if path.exists(path_to_csv):
        file_open = True
        while file_open:
            try:
                f = open(path_to_csv, 'r+')  # pylint: disable=unspecified-encoding,consider-using-with
                f.close()

            except PermissionError:
                six.moves.input(f'CLose the file {path_to_csv} and then press the <ENTER> key to continue...')
            else:
                file_open = False
    print("Now code is running! Wait a bit...")
