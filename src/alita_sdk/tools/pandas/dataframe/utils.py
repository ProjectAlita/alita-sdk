from langchain_core.callbacks import dispatch_custom_event

def send_thinking_step(func="", content=""):
    if not func:
        func = "process_query"
    if content:
        dispatch_custom_event(
            name="thinking_step",
            data={
                "message": content,
                "tool_name": func,
                "toolkit": "pandas"
            }
        )