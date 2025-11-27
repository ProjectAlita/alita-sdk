"""
Output formatting utilities for Alita CLI.

Provides text and JSON formatters for displaying toolkit test results,
agent responses, and other CLI outputs.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime


class OutputFormatter:
    """Base class for output formatters."""
    
    def format_toolkit_result(self, result: Dict[str, Any]) -> str:
        """Format toolkit test result."""
        raise NotImplementedError
    
    def format_error(self, error: str) -> str:
        """Format error message."""
        raise NotImplementedError
    
    def format_toolkit_list(self, toolkits: List[Dict[str, Any]]) -> str:
        """Format list of available toolkits."""
        raise NotImplementedError


class TextFormatter(OutputFormatter):
    """Human-readable text formatter."""
    
    def format_toolkit_result(self, result: Dict[str, Any]) -> str:
        """Format toolkit test result as text."""
        if not result.get('success', False):
            return self.format_error(result.get('error', 'Unknown error'))
        
        lines = [
            "\n✓ Tool executed successfully\n",
            f"Tool: {result.get('tool_name', 'unknown')}",
            f"Toolkit: {result.get('toolkit_config', {}).get('type', 'unknown')}",
            f"LLM Model: {result.get('llm_model', 'N/A')}",
            f"Execution time: {result.get('execution_time_seconds', 0):.3f}s",
            "",
            "Result:",
        ]
        
        # Format result based on type
        tool_result = result.get('result')
        if isinstance(tool_result, str):
            lines.append(f"  {tool_result}")
        elif isinstance(tool_result, dict):
            for key, value in tool_result.items():
                lines.append(f"  {key}: {value}")
        else:
            lines.append(f"  {str(tool_result)}")
        
        # Add events if present
        events = result.get('events_dispatched', [])
        if events:
            lines.extend([
                "",
                f"Events dispatched: {len(events)}"
            ])
            for event in events[:5]:  # Limit to first 5 events
                event_data = event.get('data', {})
                message = event_data.get('message', str(event_data))
                lines.append(f"  - {event.get('name', 'event')}: {message}")
            
            if len(events) > 5:
                lines.append(f"  ... and {len(events) - 5} more events")
        
        return "\n".join(lines)
    
    def format_error(self, error: str) -> str:
        """Format error message as text."""
        return f"\n✗ Error: {error}\n"
    
    def format_toolkit_list(self, toolkits: List[Dict[str, Any]]) -> str:
        """Format list of available toolkits as text."""
        lines = ["\nAvailable toolkits:\n"]
        
        for toolkit in sorted(toolkits, key=lambda x: x.get('name', '')):
            name = toolkit.get('name', 'unknown')
            class_name = toolkit.get('class_name', '')
            lines.append(f"  - {name}" + (f" ({class_name})" if class_name else ""))
        
        lines.append(f"\nTotal: {len(toolkits)} toolkits")
        return "\n".join(lines)
    
    def format_toolkit_schema(self, toolkit_name: str, schema: Dict[str, Any]) -> str:
        """Format toolkit schema as text."""
        lines = [
            f"\n{toolkit_name.title()} Toolkit Configuration Schema:\n",
        ]
        
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for field_name, field_schema in properties.items():
            field_type = field_schema.get('type', 'any')
            description = field_schema.get('description', '')
            is_required = field_name in required
            default = field_schema.get('default')
            
            req_text = "required" if is_required else "optional"
            lines.append(f"  - {field_name} ({req_text}): {description}")
            lines.append(f"      Type: {field_type}")
            
            if default is not None:
                lines.append(f"      Default: {default}")
            
            # Show enum values if present
            if 'enum' in field_schema:
                lines.append(f"      Options: {', '.join(map(str, field_schema['enum']))}")
            
            # Handle nested objects
            if field_type == 'object' and 'properties' in field_schema:
                lines.append(f"      Fields:")
                for nested_name, nested_schema in field_schema['properties'].items():
                    nested_desc = nested_schema.get('description', '')
                    lines.append(f"        - {nested_name}: {nested_desc}")
            
            lines.append("")
        
        return "\n".join(lines)


class JSONFormatter(OutputFormatter):
    """JSON formatter for scripting and automation."""
    
    def __init__(self, pretty: bool = True):
        """
        Initialize JSON formatter.
        
        Args:
            pretty: If True, format JSON with indentation
        """
        self.pretty = pretty
    
    def _dump(self, data: Any) -> str:
        """Dump data as JSON."""
        if self.pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)
    
    def format_toolkit_result(self, result: Dict[str, Any]) -> str:
        """Format toolkit test result as JSON."""
        return self._dump(result)
    
    def format_error(self, error: str) -> str:
        """Format error message as JSON."""
        return self._dump({'success': False, 'error': error})
    
    def format_toolkit_list(self, toolkits: List[Dict[str, Any]]) -> str:
        """Format list of available toolkits as JSON."""
        return self._dump({
            'toolkits': toolkits,
            'total': len(toolkits)
        })
    
    def format_toolkit_schema(self, toolkit_name: str, schema: Dict[str, Any]) -> str:
        """Format toolkit schema as JSON."""
        return self._dump({
            'toolkit': toolkit_name,
            'schema': schema
        })


def get_formatter(output_format: str = 'text', pretty: bool = True) -> OutputFormatter:
    """
    Get output formatter by name.
    
    Args:
        output_format: Format type ('text' or 'json')
        pretty: For JSON formatter, whether to pretty-print
        
    Returns:
        OutputFormatter instance
    """
    if output_format == 'json':
        return JSONFormatter(pretty=pretty)
    return TextFormatter()
