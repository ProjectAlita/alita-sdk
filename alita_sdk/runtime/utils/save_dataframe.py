import logging

from io import StringIO
from typing import Any, Dict, Optional

from langchain_core.tools import ToolException
import pandas as pd

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - avoid heavy imports at runtime
    from ..tools.artifact import ArtifactWrapper

logger = logging.getLogger(__name__)


def save_dataframe_to_artifact(
    artifacts_wrapper: 'ArtifactWrapper',
    df: pd.DataFrame,
    target_file: str,
    csv_options: Optional[Dict[str, Any]] = None,
):
    """
    Save a pandas DataFrame as a CSV file in the artifact repository using the ArtifactWrapper.

    Args:
        df (pd.DataFrame): The DataFrame to save.
        target_file (str): The target file name in the storage (e.g., "file.csv").
        csv_options: Dictionary of options to pass to Dataframe.to_csv()

    Raises:
        ValueError: If the DataFrame is empty or the file name is invalid.
        Exception: If saving to the artifact repository fails.
    """

    csv_options = csv_options or {}

    # Use StringIO to save the DataFrame as a string
    try:
        buffer = StringIO()
        df.to_csv(buffer, **csv_options)
        artifacts_wrapper.create_file(target_file, buffer.getvalue())
        logger.info(
            f"Successfully saved dataframe to {target_file} in bucket{artifacts_wrapper.bucket}"
        )
    except Exception as e:
        logger.exception("Failed to save DataFrame to artifact repository")
        return ToolException(
            f"Failed to save DataFrame to artifact repository: {str(e)}"
        )
