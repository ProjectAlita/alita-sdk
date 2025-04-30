from datetime import datetime
from typing import Dict, List, Any, Optional, Type
from pydantic import BaseModel, Field
from browser_use import Agent, ActionResult, Browser, BrowserConfig, BrowserContextConfig
from browser_use.agent.views import AgentHistoryList
from playwright._impl._api_structures import ProxySettings
from alita_tools.elitea_base import BaseToolApiWrapper
from pydantic import create_model, Field, model_validator
from tempfile import TemporaryDirectory, NamedTemporaryFile
from browser_use.controller.service import Controller
import asyncio


BrowserTask = create_model(
    "BrowserTask",
    task=(str, Field(description="Task to perform")),
    max_steps=(Optional[int], Field(description="Maximum number of steps to perform")),
    debug=(Optional[bool], Field(description="Whether debug mode is enabled")),
    __config__=Field(description="Browser Use API Wrapper")
)

BrowserTasks = create_model(
    "BrowserTasks",
    tasks=(List[str], Field(description="List of tasks to perform")),
    max_steps=(Optional[int], Field(description="Maximum number of steps to perform")),
    debug=(Optional[bool], Field(description="Whether debug mode is enabled")),
    __config__=Field(description="Browser Use API Wrapper")
)

class DoneResult(BaseModel):
	title: str
	comments: str
	hours_since_start: int

gif_default_location = './agent_history.gif'
default_bucket = 'browseruse'

class BrowserUseAPIWrapper(BaseToolApiWrapper):
    """Wrapper for Browser Use API."""
    headless: bool = True
    width: int = 1280
    height: int = 800
    use_vision: bool = False
    trace_actions: bool = False
    trace_actions_path: Optional[str] = None
    cookies: Optional[Dict[str, Any]] = None
    disable_security: bool = True
    proxy: Any = None
    extra_chromium_args: List[str] = []
    client: Any = None # AlitaClient
    artifact: Any = None # Artifact
    llm: Any = None # LLMLikeObject
    bucket: str = None
    proxy_settings: Any = None
    validate_output: bool = False
    planner_llm: Any = None
    browser_window_size: Dict[str, int] = None

    
    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        """Validate toolkit parameters."""
        values['proxy'] = ProxySettings(**values['proxy']) if values.get('proxy') else None
        values['extra_chromium_args'] = values.get('extra_chromium_args') or []
        values['browser_window_size'] = {"width": values.get('width', 1280), "height": values.get('height', 800)}
        values['artifact'] = values.get('client').artifact(values.get('bucket', default_bucket))
        return values
        
        
    def _create_browser(self):
        cookies_file = None
        if self.cookies:
            cookies_file = NamedTemporaryFile(delete=False)
            cookies_file.write(self.cookies)
            cookies_file.close()
        context_config = BrowserContextConfig(
                cookies_file=cookies_file,
                wait_for_network_idle_page_load_time=10.0, # TODO: Make this configurable
                highlight_elements=True,
                browser_window_size=self.browser_window_size
            )
        browser_config = BrowserConfig(
            headless=self.headless,
            disable_security=self.disable_security,
            extra_chromium_args=self.extra_chromium_args,
            proxy=self.proxy,
            new_context_config=context_config
        )
        return Browser(config=browser_config)
        
    
    def task(self, task: str, max_steps: Optional[int] = 20, debug: Optional[bool] = False):
        """Perform a task using the browser."""
        return asyncio.run(self._tasks([task], max_steps, debug))
    
    async def _tasks(self, tasks: List[str], max_steps: Optional[int] = 20, debug: Optional[bool] = False):
        browser = self._create_browser()
        context_config = BrowserContextConfig(
                wait_for_network_idle_page_load_time=10.0, # TODO: Make this configurable
                highlight_elements=True,
                browser_window_size=self.browser_window_size
            )
        async with await browser.new_context(context_config) as browser:
            start = tasks[0]
            if len(tasks) == 1:
                tasks = []
            agent = Agent(
                task=start,
                llm=self.llm,
                browser_context=browser,
                max_actions_per_step=20,
                use_vision=self.use_vision,
                save_conversation_path=None,
                generate_gif=True,
                planner_llm=self.planner_llm,
                controller=Controller(),
                message_context = "Carefully check every step, and make sure to provide detailed feedback on the results.",
                validate_output=self.validate_output
            )
            for task in tasks:
                agent.add_new_task(task) 
            history: AgentHistoryList = await agent.run(max_steps=max_steps)
        await browser.close()
        files = self._save_execution(history.model_dump_json())

        return {
            "run_data": str(history.extracted_content()), 
            "files": files
        }

    def _save_execution(self, data_content: Any):
        """Saves tasks execution gif"""

        try:
            with open(gif_default_location, 'rb') as file:
                artifact_data = file.read()
        except FileNotFoundError:
            artifact_data = None

        filename = f"tasks_{datetime.now().strftime("%Y%m%d_%H%M%S")}"
        files = []
        if data_content:
            self.artifact.create(f'{filename}.json', data_content)
            files.append(f'{filename}.json')
        
        if artifact_data:
            self.artifact.create(f'{filename}.gif', artifact_data)
            files.append(f'{filename}.gif')
        return files


    def tasks(self, tasks: List[str], max_steps: Optional[int] = 20, debug: Optional[bool] = False):
        """Perform a list of tasks using the browser."""
        return asyncio.run(self._tasks(tasks, max_steps, debug))
    
    def get_available_tools(self):
        return [
            {
                "name": "task",
                "description": self.task.__doc__,
                "args_schema": BrowserTask,
                "ref": self.task
            },
            {
                "name": "tasks",
                "description": self.tasks.__doc__,
                "args_schema": BrowserTasks,
                "ref": self.tasks
            }
        ]