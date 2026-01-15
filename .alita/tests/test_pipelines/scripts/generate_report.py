#!/usr/bin/env python3
"""
Generate a standalone HTML report from test results JSON.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

CSS = """
:root {
    --bg-color: #f8f9fa;
    --card-bg: #ffffff;
    --text-color: #212529;
    --border-color: #dee2e6;
    --success-color: #28a745;
    --failure-color: #dc3545;
    --warning-color: #ffc107;
    --info-color: #17a2b8;
    --muted-color: #6c757d;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background-color: var(--bg-color);
    color: var(--text-color);
    line-height: 1.5;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

header {
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

h1 { margin: 0; font-size: 24px; }
.meta { color: var(--muted-color); font-size: 14px; }

.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.stat-card { text-align: center; }
.stat-value { font-size: 32px; font-weight: bold; display: block; }
.stat-label { color: var(--muted-color); font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }

.passed { color: var(--success-color); }
.failed { color: var(--failure-color); }

.test-list { display: flex; flex-direction: column; gap: 15px; }

.test-item {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
}

.test-header {
    padding: 15px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    background-color: rgba(0,0,0,0.02);
}

.test-header:hover { background-color: rgba(0,0,0,0.04); }

.test-status {
    font-weight: bold;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    text-transform: uppercase;
}

.status-passed { background-color: #d4edda; color: #155724; }
.status-failed { background-color: #f8d7da; color: #721c24; }
.status-unknown { background-color: #e2e3e5; color: #383d41; }

.test-title { font-weight: 600; font-size: 16px; margin: 0 15px; flex-grow: 1; }
.test-time { color: var(--muted-color); font-size: 14px; font-family: monospace; }
.test-ts { color: var(--muted-color); font-size: 11px; margin-left: 10px; }
.test-id { color: var(--muted-color); font-size: 12px; font-family: monospace; background: #eee; padding: 2px 6px; border-radius: 4px; }

.test-details {
    border-top: 1px solid var(--border-color);
    padding: 20px;
    display: none;
}

.test-item.open .test-details { display: block; }

.scenario-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 15px;
    margin-top: 15px;
}

.scenario-card {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 12px;
    background: #fdfdfd;
}

.scenario-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 600;
}

.scenario-details {
    font-size: 12px;
    color: var(--muted-color);
    white-space: pre-wrap;
    background: #f8f9fa;
    padding: 8px;
    border-radius: 4px;
    max-height: 150px;
    overflow-y: auto;
}

    .json-table { width: 100%; border-collapse: collapse; font-family: monospace; font-size: 11px; }
    .json-table td { border: 1px solid #eee; padding: 4px; vertical-align: top; }
    .json-table .key { font-weight: bold; color: #555; background: #fafafa; width: 100px; }
    .json-table .value { color: #333; }
    .json-list { margin: 0; padding-left: 20px; }
    .string { color: #22863a; white-space: pre-wrap; word-break: break-all; }
    .primitive { color: #005cc5; }
    .empty { color: #999; font-style: italic; }
"""

SCRIPT = """
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.test-header').forEach(header => {
        header.addEventListener('click', () => {
             // Only toggle if not clicking on a link or button inside header
            if (!event.target.closest('a') && !event.target.closest('button')) {
                 header.parentElement.classList.toggle('open');
            }
        });
    });
});
"""

def format_data_html(data: Any) -> str:
    """Recursively format data as HTML table/list."""
    if isinstance(data, dict):
        if not data:
            return "<span class='empty'>{}</span>"
        rows = []
        for k, v in data.items():
            rows.append(f"<tr><td class='key'>{k}</td><td class='value'>{format_data_html(v)}</td></tr>")
        return f"<table class='json-table'>{''.join(rows)}</table>"
    
    elif isinstance(data, list):
        if not data:
            return "<span class='empty'>[]</span>"
        # If list of primitives, show inline
        if all(not isinstance(x, (dict, list)) for x in data) and len(str(data)) < 100:
             return f"<span class='primitive'>{json.dumps(data)}</span>"
        
        items = [f"<li>{format_data_html(i)}</li>" for i in data]
        return f"<ul class='json-list'>{''.join(items)}</ul>"
    
    elif isinstance(data, str):
        # Try parse nested json
        stripped = data.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                parsed = json.loads(data)
                return format_data_html(parsed)
            except:
                pass
        return f"<span class='string'>{data}</span>"
        
    else:
        return f"<span class='primitive'>{data}</span>"


def generate_html(data: Dict[str, Any]) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    total = data.get("total", 0)
    passed = data.get("passed", 0)
    failed = data.get("failed", 0)
    duration = data.get("execution_time", 0)
    suite_name = data.get("suite_name", "Unknown Suite")
    
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    html = [f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Test Report: {suite_name}</title>
        <style>{CSS}</style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>Test Execution Report</h1>
                    <div class="meta">{suite_name} • Generated: {timestamp}</div>
                </div>
                <div class="meta">Duration: {duration:.2f}s</div>
            </header>
            
            <div class="summary-grid">
                <div class="card stat-card">
                    <span class="stat-value">{total}</span>
                    <span class="stat-label">Total Tests</span>
                </div>
                <div class="card stat-card">
                    <span class="stat-value passed">{passed}</span>
                    <span class="stat-label">Passed</span>
                </div>
                <div class="card stat-card">
                    <span class="stat-value failed">{failed}</span>
                    <span class="stat-label">Failed</span>
                </div>
                <div class="card stat-card">
                    <span class="stat-value">{pass_rate:.1f}%</span>
                    <span class="stat-label">Success Rate</span>
                </div>
            </div>
            
            <div class="test-list">
    """]
    
    for result in data.get("results", []):
        test_passed = result.get("test_passed")
        
        if test_passed is True:
            status_class = "status-passed"
            status_text = "PASS"
        elif test_passed is False:
            status_class = "status-failed"
            status_text = "FAIL"
        else:
            status_class = "status-unknown"
            status_text = "ERROR"
            
        name = result.get("pipeline_name", "Unknown Pipeline")
        pid = result.get("pipeline_id", "N/A")
        time_taken = result.get("execution_time", 0)
        
        # Timestamp display
        ts = result.get("timestamp", "")
        ts_display = ""
        if ts:
             try:
                 dt = datetime.fromisoformat(ts)
                 ts_display = dt.strftime("%H:%M:%S")
             except:
                 ts_display = ts

        output_data = result.get("output", {})
        result_data = {}
        if isinstance(output_data, dict):
            if "result" in output_data:
                result_data = output_data["result"]
            else:
                result_data = output_data

        # 1. Scenarios (High level summary)
        scenarios_html = []
        scenarios = result_data.get("scenarios", {}) if isinstance(result_data, dict) else {}
        
        if scenarios:
            for s_name, s_data in scenarios.items():
                s_passed = s_data.get("passed", False)
                s_color = "green" if s_passed else "red"
                s_icon = "✓" if s_passed else "✗"
                details_dump = json.dumps(s_data.get("details", {}), indent=2)
                scenarios_html.append(f"""
                <div class="scenario-card" style="border-left: 3px solid {s_color}">
                    <div class="scenario-header">
                        <span>{s_name}</span>
                        <span style="color: {s_color}">{s_icon}</span>
                    </div>
                    <div class="scenario-details">{details_dump}</div>
                </div>
                """)

        # 2. Execution Steps (Tool Calls)
        steps_html = []
        tools_dict = output_data.get("tool_calls_dict", {}) if isinstance(output_data, dict) else {}
        
        # Collect and sort steps
        steps = []
        if isinstance(tools_dict, dict):
            for key, tc in tools_dict.items():
                steps.append({
                    "name": tc.get("tool_name", "Unknown Tool"),
                    "input": tc.get("tool_inputs"),
                    "output": tc.get("tool_output"),
                    "error": tc.get("error"),
                    "timestamp": tc.get("timestamp_start", "")
                })
        
        # Sort by timestamp
        steps.sort(key=lambda x: x["timestamp"] or "")
        
        if steps:
            steps_html.append('<div style="margin-top: 20px;"><strong>Execution Steps:</strong></div>')
            steps_html.append('<div style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">')
            
            for step in steps:
                s_name = step["name"]
                
                # Format IO
                if step["input"]:
                   s_input_html = format_data_html(step["input"])
                else:
                   s_input_html = "<span class='empty'>{}</span>"
                   
                if step["output"]:
                   s_output_html = format_data_html(step["output"])
                else:
                   s_output_html = "<span class='empty'>null</span>"

                s_error = step["error"]
                border_color = "#dc3545" if s_error else "#28a745"
                bg_color = "#fff5f5" if s_error else "#fafffa"
                
                step_content = f"""
                <div style="border: 1px solid {border_color}; background: {bg_color}; border-radius: 6px; padding: 10px; font-size: 13px;">
                    <div style="font-weight: bold; margin-bottom: 5px; color: #333;">Tool: {s_name}</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div style="overflow-x: auto;">
                            <div style="font-size: 11px; color: #666; font-weight: bold; margin-bottom: 2px;">INPUT</div>
                            <div style="background: rgba(255,255,255,0.5); padding: 5px; border-radius: 3px; max-height: 300px; overflow-y: auto;">
                                {s_input_html}
                            </div>
                        </div>
                        <div style="overflow-x: auto;">
                            <div style="font-size: 11px; color: #666; font-weight: bold; margin-bottom: 2px;">OUTPUT</div>
                            <div style="background: rgba(255,255,255,0.5); padding: 5px; border-radius: 3px; max-height: 300px; overflow-y: auto;">
                                {s_output_html}
                            </div>
                        </div>
                    </div>
                """
                if s_error:
                    step_content += f"""
                    <div style="margin-top: 5px; color: #dc3545; font-weight: bold; font-size: 12px;">Error: {s_error}</div>
                    """
                step_content += "</div>"
                steps_html.append(step_content)
            
            steps_html.append('</div>')

        
        # Error extraction
        error_html = ""
        error_msg = result.get("error")
        
        if not error_msg and isinstance(output_data, dict):
             # Alita tool error pattern or raw string error
             content = output_data.get("content")
             if content and isinstance(content, str) and ("error" in content.lower() or "exception" in content.lower()):
                  try:
                      j = json.loads(content)
                      if isinstance(j, dict) and "error" in j:
                          error_msg = j["error"]
                      else:
                          error_msg = str(content)
                  except:
                      # Check if wrapped in single quotes logic from run_pipeline
                      if content.startswith("{'error':"):
                           error_msg = content
                      else:
                           error_msg = str(content)
        
        if error_msg:
             error_html = f"""
                <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 4px; color: #856404; border: 1px solid #ffeeba;">
                    <strong>Error:</strong> {error_msg}
                </div>
             """
        
        # Raw output fallback (if no structured steps or scenarios)
        raw_output_html = ""
        if not scenarios and not steps and output_data:
             dump = json.dumps(output_data, indent=2, default=str)
             raw_output_html = f"""
                <div style="margin-top: 15px;">
                    <strong>Raw Output / Details:</strong>
                    <pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 11px; overflow-x: auto;">{dump}</pre>
                </div>
             """
        
        html.append(f"""
            <div class="test-item">
                <div class="test-header">
                    <span class="test-status {status_class}">{status_text}</span>
                    <span class="test-title">{name}</span>
                    <span class="test-id">ID: {pid}</span>
                    <span class="test-time" style="margin-left: 10px">{time_taken:.2f}s</span>
                    <span class="test-ts">{ts_display}</span>
                </div>
                <div class="test-details">
                    <div class="scenario-grid">
                        {''.join(scenarios_html) if scenarios_html else ''}
                    </div>
                    {''.join(steps_html) if steps_html else ''}
                    {error_html}
                    {raw_output_html}
                </div>
            </div>
        """)
    
    html.append(f"""
            </div>
        </div>
        <script>{SCRIPT}</script>
    </body>
    </html>
    """)
    
    return "\n".join(html)

def run(results_path: Path, output_path: Path = None) -> Path:
    """Read JSON results and generate HTML report."""
    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}")
        return None
        
    try:
        with open(results_path) as f:
            data = json.load(f)
            
        html_content = generate_html(data)
        
        if output_path is None:
            output_path = results_path.with_suffix('.html')
            
        with open(output_path, 'w') as f:
            f.write(html_content)
            
        return output_path
    except Exception as e:
        print(f"Failed to generate HTML report: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <results.json> [output.html]")
        sys.exit(1)
        
    res_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    generated = run(res_path, out_path)
    if generated:
        print(f"Report generated: {generated}")
