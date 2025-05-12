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
from langchain_core.callbacks import dispatch_custom_event
from pyobjtojson import obj_to_json
import os
import asyncio

import socket
from browser_use.browser.utils.screen_resolution import get_screen_resolution, get_window_adjustments
from playwright.async_api import Playwright, Browser as PlaywrightBrowser
from browser_use.browser.chrome import (
	CHROME_ARGS,
	CHROME_DEBUG_PORT,
	CHROME_DETERMINISTIC_RENDERING_ARGS,
	CHROME_DISABLE_SECURITY_ARGS,
	CHROME_DOCKER_ARGS,
	CHROME_HEADLESS_ARGS,
)
IN_DOCKER = os.environ.get('IN_DOCKER', 'false').lower()[0] in 'ty1'

class BrowserEx(Browser):
    def __init__(self, config: BrowserConfig):
        super().__init__(config)
        self.config = config

    async def _setup_builtin_browser(self, playwright: Playwright) -> PlaywrightBrowser:
        """Sets up and returns a Playwright Browser instance with anti-detection measures."""
        assert self.config.browser_binary_path is None, 'browser_binary_path should be None if trying to use the builtin browsers'

		# Use the configured window size from new_context_config if available
        if (
			not self.config.headless
			and hasattr(self.config, 'new_context_config')
			and hasattr(self.config.new_context_config, 'browser_window_size')
		):
            screen_size = self.config.new_context_config.browser_window_size.model_dump()
            offset_x, offset_y = get_window_adjustments()
        elif self.config.headless:
            screen_size = {'width': 1920, 'height': 1080}
            offset_x, offset_y = 0, 0
        else:
            screen_size = get_screen_resolution()
            offset_x, offset_y = get_window_adjustments()

        chrome_args = {
			f'--remote-debugging-port={self.config.chrome_remote_debugging_port}',
			*CHROME_ARGS,
			*(CHROME_DOCKER_ARGS if IN_DOCKER else []),
			*(CHROME_HEADLESS_ARGS if self.config.headless else []),
			*(CHROME_DISABLE_SECURITY_ARGS if self.config.disable_security else []),
			*(CHROME_DETERMINISTIC_RENDERING_ARGS if self.config.deterministic_rendering else []),
			f'--window-position={offset_x},{offset_y}',
			f'--window-size={screen_size["width"]},{screen_size["height"]}',
			*self.config.extra_browser_args,
		}

		# check if chrome remote debugging port is already taken,
		# if so remove the remote-debugging-port arg to prevent conflicts
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', self.config.chrome_remote_debugging_port)) == 0:
                chrome_args.remove(f'--remote-debugging-port={self.config.chrome_remote_debugging_port}')

        browser_class = getattr(playwright, self.config.browser_class)
        args = {
			'chromium': list(chrome_args),
			'firefox': [
				*{
					'-no-remote',
					*self.config.extra_browser_args,
				}
			],
			'webkit': [
				*{
					'--no-startup-window',
					*self.config.extra_browser_args,
				}
			],
		}

        browser = await browser_class.launch(
			headless=self.config.headless,
			channel='chromium',
			args=args[self.config.browser_class],
			proxy=self.config.proxy.model_dump() if self.config.proxy else None,
			handle_sigterm=False,
			handle_sigint=False,
		)
        return browser


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

async def thinking_processor(agent):
    """Hook to be called after each step."""
    if hasattr(agent, "state"):
        history = agent.state.history
    else:
        history = None
        return

    # Process model thoughts
    model_thoughts = obj_to_json(
        obj=history.model_thoughts(),
        check_circular=False
    )
    if len(model_thoughts) > 0:
        model_thoughts_last_elem = model_thoughts[-1]
        evalualtion = model_thoughts_last_elem.get('evaluation_previous_goal')
        memory = model_thoughts_last_elem.get('memory')
        next_goal = model_thoughts_last_elem.get('next_goal')
        dispatch_custom_event(
            name="thinking_step",
            data={
                "message": f"**Memory** : \n\n{memory}\n\n**Evaluation goal**:\n\n{evalualtion}\n\n**Next goal**:\n\n{next_goal}",
                "tool_name": "task",
                "toolkit": "browser_use"
            }
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
            browser_class='chromium', # TODO: Make this configurable
            disable_security=self.disable_security,
            extra_chromium_args=self.extra_chromium_args,
            proxy=self.proxy,
            new_context_config=context_config
        )
        return BrowserEx(config=browser_config)
    
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
            history: AgentHistoryList = await agent.run(
                max_steps=max_steps, 
                on_step_end=thinking_processor
                )
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