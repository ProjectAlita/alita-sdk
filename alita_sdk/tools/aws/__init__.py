from .delta_lake import DeltaLakeToolkit

name = "aws"

def get_tools(tool_type, tool):
    if tool_type == 'delta_lake':
        return DeltaLakeToolkit().get_toolkit().get_tools()