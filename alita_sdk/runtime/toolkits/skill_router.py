"""
SkillRouter Toolkit for configuring and accessing specialized skills.

This toolkit provides a configurable way to set up the skill router with
specific skills from filesystem or platform-hosted agents/pipelines.
"""

from typing import List, Optional, TYPE_CHECKING
from pydantic import create_model, BaseModel, Field, ConfigDict
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from alita_sdk.clients import AlitaClient

from alita_sdk.tools.base.tool import BaseAction
from alita_sdk.tools.utils import clean_string
from ..skills import SkillsRegistry, SkillMetadata, SkillType, SkillSource
from ..tools.skill_router import SkillRouterWrapper


class SkillConfig(BaseModel):
    """Configuration for a single skill."""

    type: str = Field(description="Skill type: 'filesystem', 'agent', or 'pipeline'")

    # Filesystem skill fields
    path: Optional[str] = Field(default=None, description="Path to skill directory (for filesystem skills)")

    # Platform skill fields
    id: Optional[int] = Field(default=None, description="Platform ID (for agent/pipeline skills)")
    version_id: Optional[int] = Field(default=None, description="Platform version ID (for agent/pipeline skills)")
    name: Optional[str] = Field(default=None, description="Skill name (optional override)")


class SkillRouterToolkit(BaseToolkit):
    """Toolkit for configuring skill router with specific skills."""

    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """Define the configuration schema for the skill router toolkit."""
        return create_model(
            "skill_router",
            # Separate fields for agents and pipelines - optional but default to empty lists
            agents=(Optional[List[SkillConfig]], Field(
                description="List of agents to make available as skills",
                default_factory=list,
                json_schema_extra={
                    "agent_tags": ["skill"]
                }
            )),
            pipelines=(Optional[List[SkillConfig]], Field(
                description="List of pipelines to make available as skills",
                default_factory=list,
                json_schema_extra={
                    "pipeline_tags": ["skill"]
                }
            )),
            prompt=(Optional[str], Field(
                description="Custom system prompt for skill routing",
                default="",
                json_schema_extra={"lines": 4}
            )),
            # Hidden skills_paths field - not exposed in UI
            skills_paths=(Optional[List[str]], Field(
                description="Additional filesystem paths to search for skills",
                default=None,
                json_schema_extra={"hidden": True}
            )),
            timeout=(Optional[int], Field(description="Default timeout in seconds for skill execution", default=300)),
            execution_mode=(Optional[str], Field(
                description="Default execution mode for skills",
                default=None,
                json_schema_extra={"enum": ["subprocess", "remote"]}
            )),
            selected_tools=(Optional[List[str]], Field(
                description="List of tools to enable",
                default=[]
            )),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Skill Router", "icon_url": None}})
        )

    @classmethod
    def get_toolkit(
        cls,
        client: 'AlitaClient',
        llm = None,
        toolkit_name: Optional[str] = None,
        selected_tools: List[str] = None,
        agents: List[SkillConfig] = None,
        pipelines: List[SkillConfig] = None,
        prompt: Optional[str] = None,
        skills_paths: Optional[str] = None,
        timeout: Optional[int] = None,
        execution_mode: Optional[str] = None
    ):
        """Create a skill router toolkit with configured skills."""
        
        if selected_tools is None:
            selected_tools = []

        # Create a custom registry for this toolkit
        registry = SkillsRegistry(search_paths=skills_paths or [])

        # Add filesystem-based skills from paths (if any)
        if skills_paths:
            registry.discover(refresh=True)

        # Helper function to process skill configs
        def add_skills_to_registry(skill_configs, default_type=None):
            if skill_configs:
                for skill_config_dict in skill_configs:
                    # Convert dict to SkillConfig object
                    skill_config = SkillConfig(**skill_config_dict)
                    # Set default type if not specified
                    if default_type and not skill_config.type:
                        skill_config.type = default_type
                    skill_metadata = cls._create_skill_from_config(skill_config, client)
                    if skill_metadata:
                        # Add skill to registry manually
                        registry.discovery.cache[skill_metadata.name] = skill_metadata

        # Add configured agents (if provided)
        add_skills_to_registry(agents or [], "agent")

        # Add configured pipelines (if provided)
        add_skills_to_registry(pipelines or [], "pipeline")

        # Create skill router wrapper with custom configuration
        wrapper = SkillRouterWrapper(
            registry=registry,
            alita_client=client,
            llm=llm,
            enable_callbacks=True,
            default_timeout=timeout,
            default_execution_mode=execution_mode,
            custom_prompt=prompt
        )
        
        # Get available tools from wrapper
        available_tools = wrapper.get_available_tools()
        
        # Filter by selected_tools if provided
        tools = []
        toolkit_context = f" [Toolkit: {clean_string(toolkit_name, 0)}]" if toolkit_name else ''
        
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            
            # Add toolkit context to description with character limit
            description = tool["description"]
            if toolkit_context and len(description + toolkit_context) <= 1000:
                description = description + toolkit_context
            
            # Wrap in BaseAction
            tools.append(BaseAction(
                api_wrapper=wrapper,
                name=tool["name"],
                description=description,
                args_schema=tool["args_schema"],
                metadata={"toolkit_name": toolkit_name} if toolkit_name else {}
            ))

        return cls(tools=tools)

    @classmethod
    def _create_skill_from_config(cls, config: SkillConfig, client: 'AlitaClient') -> Optional[SkillMetadata]:
        """Create SkillMetadata from SkillConfig."""
        try:
            if config.type == "filesystem":
                # Filesystem skills are handled by discovery
                return None

            elif config.type in ["agent", "pipeline"]:
                if not config.id or not config.version_id:
                    raise ValueError(f"Platform skill type '{config.type}' requires id and version_id")

                # Get skill details from platform
                if config.type == "agent":
                    skill_details = cls._get_agent_details(client, config.id, config.version_id)
                    skill_type = SkillType.AGENT
                else:  # pipeline
                    skill_details = cls._get_pipeline_details(client, config.id, config.version_id)
                    skill_type = SkillType.PIPELINE

                # Create SkillMetadata for platform skill
                return SkillMetadata(
                    name=config.name or skill_details.get('name', f"{config.type}_{config.id}"),
                    skill_type=skill_type,
                    source=SkillSource.PLATFORM,
                    id=config.id,
                    version_id=config.version_id,
                    description=skill_details.get('description', ''),
                    capabilities=skill_details.get('capabilities', []),
                    tags=skill_details.get('tags', []),
                    version=skill_details.get('version', '1.0.0'),
                    # Set default execution config - platform skills run remotely
                    execution={"mode": "remote", "timeout": 300},
                    results={"format": "text_with_links"},
                    inputs={},
                    outputs={}
                )

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to create skill from config {config}: {e}")
            return None

    @classmethod
    def _get_agent_details(cls, client: 'AlitaClient', agent_id: int, version_id: int) -> dict:
        """Get agent details from platform."""
        try:
            app_details = client.get_app_details(agent_id)
            version_details = client.get_app_version_details(agent_id, version_id)

            return {
                'name': app_details.get('name', f'agent_{agent_id}'),
                'description': app_details.get('description', ''),
                'capabilities': [], # Could be extracted from app metadata
                'tags': [], # Could be extracted from app metadata
                'version': version_details.get('version', '1.0.0')
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to get agent details for {agent_id}/{version_id}: {e}")
            return {'name': f'agent_{agent_id}', 'description': 'Platform-hosted agent'}

    @classmethod
    def _get_pipeline_details(cls, client: 'AlitaClient', pipeline_id: int, version_id: int) -> dict:
        """Get pipeline details from platform."""
        try:
            # For now, use the same method as agents since they use the same API
            # In the future, this might use a different endpoint for pipelines
            app_details = client.get_app_details(pipeline_id)
            version_details = client.get_app_version_details(pipeline_id, version_id)

            return {
                'name': app_details.get('name', f'pipeline_{pipeline_id}'),
                'description': app_details.get('description', ''),
                'capabilities': [], # Could be extracted from pipeline metadata
                'tags': [], # Could be extracted from pipeline metadata
                'version': version_details.get('version', '1.0.0')
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to get pipeline details for {pipeline_id}/{version_id}: {e}")
            return {'name': f'pipeline_{pipeline_id}', 'description': 'Platform-hosted pipeline'}

    def get_tools(self):
        """Get the configured tools."""
        return self.tools