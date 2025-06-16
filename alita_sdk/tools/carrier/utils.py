import json
import logging
import os

from pydantic import BaseModel, Field
from datetime import date
from typing import List


class TicketPayload(BaseModel):
    title: str
    board_id: str
    severity: str = "Medium"
    type: str
    description: str
    external_link: str
    engagement: str
    assignee: str
    start_date: date
    end_date: date
    tags: List[str] = []


def parse_config_from_string(config_str: str) -> dict:
    """
    Parse configuration from a JSON string or key-value pairs.

    Args:
        config_str (str): Configuration string in JSON or key:value format

    Returns:
        dict: Parsed configuration
    """
    try:
        # Try parsing as JSON first
        return json.loads(config_str)
    except json.JSONDecodeError:
        # If not JSON, try parsing as key:value pairs
        config = {}
        for line in config_str.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                config[key.strip()] = value.strip()
        return config


def validate_resource_type(resource_type: str) -> bool:
    """
    Validate if the resource type is supported.

    Args:
        resource_type (str): Resource type to validate

    Returns:
        bool: Whether the resource type is valid
    """
    # Define a list of supported resource types
    supported_types = [
        'deployments',
        'services',
        'configurations',
        'environments'
    ]

    return resource_type.lower() in supported_types


def log_action(action: str, details: dict = None):
    """
    Log an action with optional details.

    Args:
        action (str): Description of the action
        details (dict, optional): Additional details about the action
    """
    logger = logging.getLogger(__name__)
    log_message = action
    if details is not None:  # Check for None instead of truthiness to handle empty dicts
        log_message += f": {json.dumps(details, indent=2)}"
    logger.info(log_message)


def get_latest_log_file(root_dir: str, log_file_name: str) -> str:
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"Directory not found: {root_dir}")
    folders = next(os.walk(root_dir))[1]
    folders.sort(key=lambda folder: os.path.getmtime(os.path.join(root_dir, folder)))
    latest_folder = folders[-1]
    simulation_log_file = os.path.join(root_dir, latest_folder, log_file_name)

    if not os.path.isfile(simulation_log_file):
        raise FileNotFoundError(f"File not found: {simulation_log_file}")
    return simulation_log_file


def calculate_thresholds(results, report_percentile, thresholds):
    """

    :param results:
    :param report_percentile:
    :param thresholds:
    :return:
    """
    data = []
    tp_threshold = thresholds['tp_threshold']
    rt_threshold = thresholds['rt_threshold']
    er_threshold = thresholds['er_threshold']

    if results['throughput'] < tp_threshold:
        data.append({"target": "throughput", "scope": "all", "value": results['throughput'],
                    "threshold": tp_threshold, "status": "FAILED", "metric": "req/s"})
    else:
        data.append({"target": "throughput", "scope": "all", "value": results['throughput'],
                    "threshold": tp_threshold, "status": "PASSED", "metric": "req/s"})

    if results['error_rate'] > er_threshold:
        data.append({"target": "error_rate", "scope": "all", "value": results['error_rate'],
                    "threshold": er_threshold, "status": "FAILED", "metric": "%"})
    else:
        data.append({"target": "error_rate", "scope": "all", "value": results['error_rate'],
                    "threshold": er_threshold, "status": "PASSED", "metric": "%"})

    for req in results['requests']:
        if float(results['requests'][req][report_percentile]) > rt_threshold:
            data.append({"target": "response_time", "scope": results['requests'][req],
                        "value": results['requests'][req][report_percentile],
                        "threshold": rt_threshold, "status": "FAILED", "metric": "ms"})
        else:
            data.append({"target": "response_time", "scope": results['requests'][req]['request_name'],
                        "value": results['requests'][req][report_percentile],
                        "threshold": rt_threshold, "status": "PASSED", "metric": "ms"})
    return data

