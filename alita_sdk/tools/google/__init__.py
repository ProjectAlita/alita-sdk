from .bigquery import BigQueryToolkit

name = "google"

def get_tools(tool_type, tool):
    if tool_type == 'bigquery':
        return BigQueryToolkit().get_toolkit().get_tools()