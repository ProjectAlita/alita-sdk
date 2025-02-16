import logging
from io import StringIO
import pandas as pd
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
from ....tools.artifact import ArtifactWrapper
from jira import JIRA
from ..utils.constants import OUTPUT_ISSUES_COUNT, OUTPUT_COUNT_PATH

from ..jira.jira_projects_overview import jira_projects_overview
from ..jira.jira_all_fields_overview import jira_all_fields_overview
from ..jira.jira_statuses import get_all_statuses_list
from ..jira.jira_issues import JiraIssues

logger = logging.getLogger(__name__)


class GetJiraFieldsArgs(BaseModel):
    project_keys: str = Field(description="One or more projects keys separated with comma.")
    after_date: str = Field(description="Date after which issues are considered.")

class GetJiraIssuesArgs(BaseModel):
    project_keys: str = Field(description="One or more projects keys separated with comma.")
    closed_issues_based_on: int = Field(description="Define whether issues can be thought as closed based on their status (1) or not empty resolved date (2).")
    resolved_after: str = Field(description="Resolved after date (i.e. 2023-01-01).")
    updated_after: str = Field(description="Updated after date (i.e. 2023-01-01).")
    created_after: str = Field(description="Created after date (i.e. 2023-01-01).")
    add_filter: Optional[str] = Field(description="Additional filter for Jira issues in JQL format like 'customfield_10000 = 'value' AND customfield_10001 = 'value'")
    

class EDAApiWrapper(BaseModel):
    artifacts_wrapper: ArtifactWrapper
    jira: 'JIRA'
    closed_status: str # Jira ticket closed statuses
    defects_name: str # Jira ticket defects name
    custom_fields: dict # Jira ticket custom fields

    class Config:
        arbitrary_types_allowed = True
    
    def get_number_off_all_issues(self, project_keys: str, after_date: str):
        """
            Get projects a user has access to and merge them with issues count.
            updated_after: str
                date after which issues are considered
        """
        project_df = jira_projects_overview(after_date, project_keys=project_keys, jira=self.jira)
        with open(OUTPUT_ISSUES_COUNT, 'r') as f:
            self.artifacts_wrapper.create_file('projects_overview.csv', f.read())
        return {"projects": project_df['key'].tolist(), "projects_summary": project_df.to_string()}    
    
    def get_all_jira_fields(self, project_keys: str, updated_after: str):
        """
            Get all Jira fields for the specified projects.
            projects: str
                one or more projects keys separated with comma
            updated_after: str
                date after which issues are considered
        """
        overall_stat, issue_types_stat = jira_all_fields_overview(project_keys, updated_after, jira=self.jira)
        with open(OUTPUT_COUNT_PATH, 'r') as f:
            self.artifacts_wrapper.create_file('fields_count.csv', f.read())
        return {"overall_stat": overall_stat.to_string(), "issue_types_stat": issue_types_stat.to_string()}
    
    def get_jira_issues(self, project_keys: str, closed_issues_based_on: int, 
                        resolved_after: str, updated_after: str, 
                        created_after:str, add_filter: str = ''):
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
        
        if not ((closed_issues_based_on == 1 and self.closed_status in get_all_statuses_list(self.jira)) or closed_issues_based_on == 2):
            return "ERROR: Check input parameters closed_issues_based_on and closed_status"
        jira_issues = JiraIssues(self.jira, project_keys, (closed_issues_based_on, self.closed_status), self.defects_name, add_filter = '')

        df_issues, df_map = jira_issues.extract_issues_from_jira_and_transform(
            self.custom_fields, (resolved_after, updated_after, created_after)
        )
        csv_buffer_projects = StringIO()
        df_map.to_csv(csv_buffer_projects, index_label='id')
        csv_buffer_projects.seek(0)
        self.artifacts_wrapper.create_file(f'map_statuses_{jira_issues.projects}.csv', csv_buffer_projects.getvalue())
        if not df_issues.empty:
            csv_buffer_issues = StringIO()
            df_issues.to_csv(csv_buffer_issues, index_label='id')
            csv_buffer_projects.seek(0)
            self.artifacts_wrapper.create_file(f'data_work_items_{jira_issues.projects}.csv', csv_buffer_issues.getvalue())
        return f'{jira_issues.projects} Data has been extracted successfully.'
        
        
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
            }
        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
