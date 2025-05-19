import logging
from io import StringIO
from typing import Optional, List, Dict, Any
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from jira import JIRA
import pandas as pd


from elitea_analyse.utils.constants import OUTPUT_MAPPING_FILE, OUTPUT_WORK_ITEMS_FILE
from elitea_analyse.jira.jira_projects_overview import jira_projects_overview
from elitea_analyse.jira.jira_all_fields_overview import jira_all_fields_overview
from elitea_analyse.jira.jira_statuses import get_all_statuses_list
from elitea_analyse.jira.jira_issues import JiraIssues

from alita_tools.elitea_base import BaseToolApiWrapper
from ....tools.artifact import ArtifactWrapper


logger = logging.getLogger(__name__)


class GetJiraFieldsArgs(BaseModel):
    project_keys: str = Field(
        description="One or more projects keys separated with comma."
    )
    after_date: str = Field(description="Date after which issues are considered.")


class GetJiraIssuesArgs(BaseModel):
    project_keys: str = Field(
        description="One or more projects keys separated with comma."
    )
    closed_issues_based_on: int = Field(
        description="Define whether issues can be thought as closed based on their status (1) or not empty resolved date (2)."
    )
    resolved_after: str = Field(description="Resolved after date (i.e. 2023-01-01).")
    updated_after: str = Field(description="Updated after date (i.e. 2023-01-01).")
    created_after: str = Field(description="Created after date (i.e. 2023-01-01).")
    add_filter: Optional[str] = Field(
        description="Additional filter for Jira issues in JQL format like 'customfield_10000 = 'value' AND customfield_10001 = 'value'"
    )


class JiraAnalyseWrapper(BaseToolApiWrapper):
    artifacts_wrapper: ArtifactWrapper
    jira: JIRA
    closed_status: str  # Jira ticket closed statuses
    defects_name: str  # Jira ticket defects name
    custom_fields: dict  # Jira ticket custom fields

    class Config:
        arbitrary_types_allowed = True

    def get_number_off_all_issues(self, project_keys: str, after_date: str):
        """
        Get projects a user has access to and merge them with issues count.
        after_date: str
            date after which issues are considered
        """
        project_df = jira_projects_overview(
            after_date, project_keys=project_keys, jira=self.jira
        )

        # Save project_df DataFrame into the bucket
        self.save_dataframe(
            project_df,
            f"projects_overview_{project_keys}.csv",
            csv_options={"index": False},
        )
        dispatch_custom_event(
            name="jira_projects_overview",
            data={
                "project_keys": project_keys,
                "after_date": after_date,
                "files": [f"projects_overview_{project_keys}.csv"],
                "project_count": len(project_df),
                "columns": project_df.columns.tolist(),
            },
        )

        return {
            "projects": project_df["key"].tolist(),
            "projects_summary": project_df.to_string(),
        }

    def get_all_jira_fields(self, project_keys: str, after_date: str):
        """
        Get all Jira fields for the specified projects.
        projects: str
            one or more projects keys separated with comma
        after_date: str
            date after which issues are considered
        """
        dispatch_custom_event(
            name="jira_all_fields_overview",
            data={
                "project_keys": project_keys,
                "after_date": after_date,
            },
        )
        overall_stat, issue_types_stat = jira_all_fields_overview(
            project_keys, after_date, jira=self.jira
        )

        dispatch_custom_event(
            name="jira_fields_saving",
            data={
                "project_keys": project_keys,
                "after_date": after_date,
                "overall_stat": len(overall_stat),
                "issue_types_stat": len(issue_types_stat),
                "files": [
                    "fields_count.csv",
                    f"fields_count_issues_{project_keys}.csv",
                ],
            },
        )

        self.save_dataframe(
            overall_stat,
            "fields_count.csv",
            csv_options={"index": False},
        )

        self.save_dataframe(
            issue_types_stat,
            f"fields_count_issues_{project_keys}.csv",
            csv_options={"index": False},
        )

        return {
            "overall_stat": overall_stat.to_string(),
            "issue_types_stat": issue_types_stat.to_string(),
        }

    def get_jira_issues(
        self,
        project_keys: str,
        closed_issues_based_on: int,
        resolved_after: str,
        updated_after: str,
        created_after: str,
        add_filter: str = "",
    ):
        """
        Extract Jira issues for the specified projects.
        projects: str
            one or more projects keys separated with comma
        closed_issues_based_on: int
            define whether issues can be thought as closed based on their status (1) or not empty resolved date (2)
        resolved_after: str
            resolved after date (i.e. 2023-01-01)
        updated_after: str
            updated after date (i.e. 2023-01-01)
        created_after: str
            created after date (i.e. 2023-01-01)
        add_filter: str
            additional filter for Jira issues in JQL format like "customfield_10000 = 'value' AND customfield_10001 = 'value'"
        """

        if not (
            (
                closed_issues_based_on == 1
                and self.closed_status in get_all_statuses_list(jira=self.jira)
            )
            or closed_issues_based_on == 2
        ):
            return (
                "ERROR: Check input parameters closed_issues_based_on and closed_status"
            )

        dispatch_custom_event(
            name="jira_issues_extraction_start",
            data={
                "closed_issues_based_on": closed_issues_based_on,
                "closed_status": self.closed_status,
            }
        )
        jira_issues = JiraIssues(
            self.jira,
            project_keys,
            (closed_issues_based_on, self.closed_status),
            self.defects_name,
            add_filter="",
        )

        df_issues, df_map = jira_issues.extract_issues_from_jira_and_transform(
            self.custom_fields, (resolved_after, updated_after, created_after)
        )
        dispatch_custom_event(
            name="jira_issues_extracted",
            data={
                "project_keys": jira_issues.projects,
                "issue_count": len(df_issues),
                "map_rows": len(df_map),
            },
        )
        self.save_dataframe(
            df_map,
            f"{OUTPUT_MAPPING_FILE}{jira_issues.projects}.csv",
            csv_options={"index_label": "id"},
        )
        dispatch_custom_event(
            name="jira_map_statuces_saved",
            data={
                "output_file": f"{OUTPUT_MAPPING_FILE}{jira_issues.projects}.csv",
                "row_count": len(df_map),
            }
        )

        if not df_issues.empty:
            self.save_dataframe(
                df_issues,
                f"{OUTPUT_WORK_ITEMS_FILE}{jira_issues.projects}.csv",
                csv_options={"index_label": "id"},
            )
            dispatch_custom_event(
                name="jira_issues_saved",
                data={
                    "output_file": f"{OUTPUT_WORK_ITEMS_FILE}{jira_issues.projects}.csv",
                    "row_count": len(df_issues),
                }
            )

        return f"{jira_issues.projects} Data has been extracted successfully."

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get a list of available tools."""
        return [
            {
                "name": "get_number_off_all_issues",
                "description": self.get_number_off_all_issues.__doc__,
                "args_schema": GetJiraFieldsArgs,
                "ref": self.get_number_off_all_issues,
            },
            {
                "name": "get_all_jira_fields",
                "description": self.get_all_jira_fields.__doc__,
                "args_schema": GetJiraFieldsArgs,
                "ref": self.get_all_jira_fields,
            },
            {
                "name": "get_jira_issues",
                "description": self.get_jira_issues.__doc__,
                "args_schema": GetJiraIssuesArgs,
                "ref": self.get_jira_issues,
            },
        ]

    def save_dataframe(
        self,
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
            self.artifacts_wrapper.create_file(target_file, buffer.getvalue())
            logger.info(
                f"Successfully saved dataframe to {target_file} in bucket {self.artifacts_wrapper.bucket}"
            )
        except Exception as e:
            logger.exception("Failed to save DataFrame to artifact repository")
            return ToolException(
                f"Failed to save DataFrame to artifact repository: {str(e)}"
            )

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")
