"""Constants used in the project."""
from datetime import datetime
from pandas import Timestamp

from ..utils.convert_to_datetime import string_to_datetime

OUTPUT_FOLDER = './raw_data/'

OUTPUT_WORK_ITEMS_FILE = 'data_work_items_'
OUTPUT_WORK_ITEMS = OUTPUT_FOLDER + OUTPUT_WORK_ITEMS_FILE

OUTPUT_MAPPING_FILE = 'map_statuses_'
OUTPUT_MAPPING = OUTPUT_FOLDER + OUTPUT_MAPPING_FILE
OUTPUT_SPRINTS = OUTPUT_FOLDER + 'data_sprints_'
OUTPUT_ISSUES_COUNT = OUTPUT_FOLDER + 'projects_overview.csv'
OUTPUT_COUNT_PATH = OUTPUT_FOLDER + 'fields_count.csv'
OUTPUT_PROJECTS_PATH = OUTPUT_FOLDER + 'data_jira_projects.csv'
OUTPUT_COMMITS_PATH = OUTPUT_FOLDER + 'commits_details_'
OUTPUT_PULL_REQUESTS_PATH = OUTPUT_FOLDER + 'pull_requests_details_'
OUTPUT_METRICS_FOLDER = './output_metrics/'
DATE_UTC = string_to_datetime(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
OPEN_ISSUE_CREATED = Timestamp('2022-03-15 10:35:00')
WAITING_FOR_RELEASE_STATUS = 'Waiting for release'
TIME_IN_STATUS_OPEN = (DATE_UTC - OPEN_ISSUE_CREATED).days
ACTIVE_STATUSES = tuple([
    'triage',
    'collecting information',
    'in design',
    'in progress',
    'in development',
    'in pr',
    'design review',
    'in review',
    'team review',
    'qa',
    'qa in progress',
    'in qa',
    'eng qa in progress',
    'po review',
    'review',
    'team validation',
    'testing',
    'in testing',
    'po approval',
    'prod monitoring',
    'in production',
    'publish in process'
])

STATUSES_NOT_IN_CYCLE_TIME = tuple([
    "backlog",
    "open",
    "to do",
    "new",
    "in research",
    "collecting information",
    "ready",
    "ready for development",
    "selected for development",
    "cancelled",
    "closed",
    "won't do",
    "deferred",
    "approved",
    "done",
    "waiting for release"
])
