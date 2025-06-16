from .aws import AWSToolkit
from .azure import AzureToolkit
from .gcp import GCPToolkit
from .k8s import KubernetesToolkit

name = "cloud"

def get_tools(tool_type, tool):
    if tool_type == 'aws':
        return AWSToolkit().get_toolkit().get_tools()
    elif tool_type == 'azure':
        return AzureToolkit().get_toolkit().get_tools()
    elif tool_type == 'gcp':
        return GCPToolkit().get_toolkit().get_tools()
    elif tool_type == 'k8s':
        return KubernetesToolkit().get_toolkit().get_tools()