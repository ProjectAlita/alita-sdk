import base64
import io
import json
import random
from PIL import Image
import logging
from traceback import format_exc
logging.basicConfig(level=logging.INFO)
from os import environ
from dotenv import load_dotenv
load_dotenv('.env')
from .constants import STYLES
logger = logging.getLogger(__name__)

ai_icon = b'<plain_txt_msg:img>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<!plain_txt_msg>'
user_icon = b'<plain_txt_msg:img>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<!plain_txt_msg>'
agent_types = ["pipeline", "react", "xml", "openai", "predict"]

def img_to_txt(filename):
    msg = b"<plain_txt_msg:img>"
    with open(filename, "rb") as imageFile:
        msg = msg + base64.b64encode(imageFile.read())
    msg = msg + b"<!plain_txt_msg>"
    return msg

def decode_img(msg):
    try:
        # Extract the base64 data between the markers
        start_marker = b"<plain_txt_msg:img>"
        end_marker = b"<!plain_txt_msg>"
        
        start_pos = msg.find(start_marker)
        end_pos = msg.find(end_marker)
        
        if start_pos == -1 or end_pos == -1:
            raise ValueError("Image markers not found in data")
        
        # Extract the base64 data
        base64_data = msg[start_pos + len(start_marker):end_pos]
        
        # Decode base64 data
        decoded_data = base64.b64decode(base64_data)
        
        # Create image from decoded data
        buf = io.BytesIO(decoded_data)
        img = Image.open(buf)
        return img
    except Exception as e:
        logger.error(f"Error decoding image: {e}")
        # Return a placeholder or None if image decoding fails
        return None

def pil_to_base64_string(pil_image):
    """Convert PIL Image to base64 string that Streamlit can use as avatar"""
    if pil_image is None:
        return None
    try:
        # Convert PIL image to base64 string
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"Error converting PIL image to base64: {e}")
        return None


# from alita_sdk.runtime.llms.alita import AlitaChatModel
from alita_sdk.runtime.clients.client import AlitaClient
from alita_sdk.runtime.utils.AlitaCallback import AlitaStreamlitCallback
from alita_sdk.runtime.toolkits.tools import get_toolkits, get_tools
from alita_sdk.community.utils import check_schema

def run_streamlit(st, ai_icon=None, user_icon=None):
    # Use simple emoji avatars as default if not provided
    # This fixes the StreamlitAPIException error with avatar loading
    if ai_icon is None:
        ai_icon = "🤖"  # Robot emoji for AI
        # Alternative: To use the original base64 encoded images, uncomment the lines below:
        # ai_icon = pil_to_base64_string(decode_img(globals()['ai_icon'])) if 'ai_icon' in globals() else "🤖"
    if user_icon is None:
        user_icon = "👤"  # User emoji for human
        # Alternative: To use the original base64 encoded images, uncomment the line below:
        # user_icon = pil_to_base64_string(decode_img(globals()['user_icon'])) if 'user_icon' in globals() else "👤"

    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.thread_id = None
        
    def clear_agent_context():
        """Clear agent-related context when switching away from agent"""
        st.session_state.agent_executor = None
        st.session_state.agent_chat = False
        st.session_state.agent_name = None
        st.session_state.agent_toolkits = []
        st.session_state.agent_toolkit_configs = {}
        st.session_state.agent_raw_config = None
        st.session_state.configured_toolkit_ready = False
        clear_chat_history()

    def create_tooklit_schema(tkit_schema):
        schema = {}
        for key, value in tkit_schema.get('properties', {}).items():
            if value.get('autopopulate'):
                continue
            schema[key] = value
        return schema
    
    def render_function_parameters_form(tool, form_key_prefix=""):
        """Render function parameters as a form instead of JSON"""
        if not hasattr(tool, 'args_schema') or not tool.args_schema:
            return {}
        
        try:
            schema = tool.args_schema.schema()
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            if not properties:
                st.info("This function doesn't require any parameters.")
                return {}
            
            st.markdown("### 📝 Function Parameters")
            
            parameters = {}
            for param_name, param_schema in properties.items():
                param_type = param_schema.get('type', 'string')
                param_description = param_schema.get('description', '')
                param_default = param_schema.get('default', '')
                is_required = param_name in required
                
                label = f"{'*' if is_required else ''}{param_name.replace('_', ' ').title()}"
                key = f"{form_key_prefix}_{param_name}"
                
                if param_type == 'string':
                    if param_schema.get('enum'):
                        # Dropdown for enum values
                        options = param_schema['enum']
                        default_index = 0
                        if param_default and param_default in options:
                            default_index = options.index(param_default)
                        parameters[param_name] = st.selectbox(
                            label,
                            options=options,
                            index=default_index,
                            help=param_description,
                            key=key
                        )
                    else:
                        parameters[param_name] = st.text_input(
                            label,
                            value=str(param_default) if param_default else '',
                            help=param_description,
                            key=key
                        )
                elif param_type == 'integer':
                    parameters[param_name] = st.number_input(
                        label,
                        value=int(param_default) if param_default else 0,
                        help=param_description,
                        step=1,
                        key=key
                    )
                elif param_type == 'number':
                    parameters[param_name] = st.number_input(
                        label,
                        value=float(param_default) if param_default else 0.0,
                        help=param_description,
                        key=key
                    )
                elif param_type == 'boolean':
                    parameters[param_name] = st.checkbox(
                        label,
                        value=bool(param_default) if param_default else False,
                        help=param_description,
                        key=key
                    )
                elif param_type == 'array':
                    items_schema = param_schema.get('items', {})
                    if items_schema.get('type') == 'string':
                        array_input = st.text_area(
                            f"{label} (one per line)",
                            help=f"{param_description} - Enter one item per line",
                            key=key
                        )
                        parameters[param_name] = [line.strip() for line in array_input.split('\n') if line.strip()]
                    else:
                        # For complex array types, fall back to JSON input
                        array_input = st.text_area(
                            f"{label} (JSON array)",
                            help=f"{param_description} - Enter as JSON array",
                            placeholder='["item1", "item2"]',
                            key=key
                        )
                        try:
                            parameters[param_name] = json.loads(array_input) if array_input.strip() else []
                        except json.JSONDecodeError:
                            parameters[param_name] = []
                            st.error(f"Invalid JSON format for {param_name}")
                elif param_type == 'object':
                    # For object types, use JSON input
                    obj_input = st.text_area(
                        f"{label} (JSON object)",
                        help=f"{param_description} - Enter as JSON object",
                        placeholder='{"key": "value"}',
                        key=key
                    )
                    try:
                        parameters[param_name] = json.loads(obj_input) if obj_input.strip() else {}
                    except json.JSONDecodeError:
                        parameters[param_name] = {}
                        st.error(f"Invalid JSON format for {param_name}")
                else:
                    # Fallback to text input for unknown types
                    parameters[param_name] = st.text_input(
                        label,
                        value=str(param_default) if param_default else '',
                        help=param_description,
                        key=key
                    )
            
            # Validate required fields
            missing_required = []
            for req_field in required:
                if req_field in parameters and not parameters[req_field]:
                    missing_required.append(req_field)
            
            if missing_required:
                st.error(f"Required fields missing: {', '.join(missing_required)}")
                return None
            
            return parameters
            
        except Exception as e:
            st.error(f"Error rendering form: {str(e)}")
            return None
    
    def inject_project_secrets(toolkit_config):
        """Inject project secrets into toolkit configuration"""
        if not st.session_state.project_secrets:
            return toolkit_config
        
        # Create a copy to avoid modifying the original
        config = toolkit_config.copy()
        
        # Inject pgvector connection string if available
        if 'pgvector_project_connstr' in st.session_state.project_secrets:
            pgvector_connstr = st.session_state.project_secrets['pgvector_project_connstr']
            # Common field names for connection strings
            connection_fields = ['connection_string', 'connstr', 'database_url', 'db_url', 'conn_str']
            for field in connection_fields:
                if field in config and not config[field]:
                    config[field] = pgvector_connstr
                    logger.info(f"Injected pgvector connection string into {field}")
                    break
        
        return config
    
    def instantiate_toolkit(toolkit_config):
        """
        Helper function to instantiate a toolkit based on its configuration.
        This function now delegates to the toolkit_utils module for the actual implementation.
        """
        try:
            from .toolkit_utils import instantiate_toolkit_with_client
            
            # Extract toolkit name and settings from the old format
            toolkit_name = toolkit_config.get('toolkit_name')
            settings = toolkit_config.get('settings', {})
            
            # Inject project secrets into configuration  
            enhanced_settings = inject_project_secrets(settings)
            
            # Create the new format configuration
            new_config = {
                'toolkit_name': toolkit_name,
                'settings': enhanced_settings
            }
            
            # Create a basic LLM client for toolkit instantiation
            try:
                if not st.session_state.client:
                    raise ValueError("Alita client not available")
                    
                llm_client = st.session_state.client.get_llm(
                    model_name="gpt-4o-mini",
                    model_config={
                        "temperature": 0.1,
                        "max_tokens": 1000,
                        "top_p": 1.0
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create LLM client: {str(e)}. Falling back to basic toolkit instantiation.")
                # Fallback to basic instantiation
                from .toolkit_utils import instantiate_toolkit as fallback_instantiate
                return fallback_instantiate(new_config)
            
            # Use the enhanced implementation with client support
            return instantiate_toolkit_with_client(
                new_config, 
                llm_client, 
                st.session_state.client
            )
                
        except Exception as e:
            logger.error(f"Error instantiating toolkit {toolkit_config.get('toolkit_name')}: {str(e)}")
            raise

    st.set_page_config(
        page_title='Alita Assistants',
        page_icon = "🤖",  # Use emoji instead of decoded image
        layout = 'wide',
        initial_sidebar_state = 'auto',
        menu_items={
            "Get help" : "https://elitea.ai",
            "About": "https://elitea.ai/docs"
        }
    )

    # Initialize session state variables
    if 'tooklit_configs' not in st.session_state:
        st.session_state.tooklit_configs = []
    if 'tooklit_names' not in st.session_state:
        st.session_state.tooklit_names = []
    if 'llm' not in st.session_state:
        st.session_state.llm = None
    if 'agents' not in st.session_state:
        st.session_state.agents = None
    if 'models' not in st.session_state:
        st.session_state.models = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = None
    if 'agent_executor' not in st.session_state:
        st.session_state.agent_executor = None
    if 'agent_chat' not in st.session_state:
        st.session_state.agent_chat = False
    if 'agent_name' not in st.session_state:
        st.session_state.agent_name = None
    if 'configured_toolkit' not in st.session_state:
        st.session_state.configured_toolkit = None
    if 'project_secrets' not in st.session_state:
        st.session_state.project_secrets = None
    if 'login_form_expanded' not in st.session_state:
        st.session_state.login_form_expanded = True  # Start expanded by default
    if 'show_toolkit_testing' not in st.session_state:
        st.session_state.show_toolkit_testing = False
    if 'agent_toolkits' not in st.session_state:
        st.session_state.agent_toolkits = []  # Store agent's toolkit configurations
    if 'agent_toolkit_configs' not in st.session_state:
        st.session_state.agent_toolkit_configs = {}  # Store agent's toolkit settings
    if 'agent_raw_config' not in st.session_state:
        st.session_state.agent_raw_config = None  # Store raw agent configuration for debugging
    if 'configured_toolkit_ready' not in st.session_state:
        st.session_state.configured_toolkit_ready = False  # Track when toolkit config is ready

    # Initialize toolkit configurations
    if not(st.session_state.tooklit_configs and len(st.session_state.tooklit_configs) > 0):
        for tkit_pd in get_toolkits():
            ktit_sch = tkit_pd.model_json_schema()
            st.session_state.tooklit_configs.append(ktit_sch)
            st.session_state.tooklit_names.append(ktit_sch['title'])

    st.markdown(STYLES, unsafe_allow_html=True)

    with st.sidebar:
        clear_chat = st.button("Clear Chat")
        if clear_chat:
            clear_chat_history()
        
        # Clear all button for debugging/reset
        if st.session_state.agent_executor or st.session_state.configured_toolkit:
            clear_all = st.button("🗑️ Clear All", help="Clear agent and toolkit configurations")
            if clear_all:
                clear_agent_context()
                st.session_state.configured_toolkit = None
                st.session_state.show_toolkit_testing = False
                st.rerun()
        
        # Determine login form title and expansion state
        if st.session_state.client:
            login_title = "✅ Elitea Login (Connected)"
            # Collapse after successful login, but allow expansion
            if st.session_state.login_form_expanded is True:
                st.session_state.login_form_expanded = False
        else:
            login_title = "🔐 Elitea Login Form"
            # Keep expanded if not logged in
            st.session_state.login_form_expanded = True
            
        # Use expander for accordion functionality
        with st.expander(login_title, expanded=st.session_state.login_form_expanded):
            deployment_value = environ.get('DEPLOYMENT_URL', None)
            deployment_secret = environ.get('XSECRET', 'secret')
            api_key_value = environ.get('API_KEY', None)
            project_id_value = int(environ.get('PROJECT_ID', 0))
            if st.session_state.client:
                deployment_value = st.session_state.client.base_url
                api_key_value = st.session_state.client.auth_token
                project_id_value = st.session_state.client.project_id

            # Show current connection status
            if st.session_state.client:
                st.success(f"Connected to: {deployment_value}")
                st.info(f"Project ID: {project_id_value}")
                
            ## Alita authentication
            with st.form("settings_form", clear_on_submit=False):
                deployment = st.text_input("Deployment URL", placeholder="Enter Deployment URL", value=deployment_value)
                api_key = st.text_input("API Key", placeholder="Enter API Key", value=api_key_value, type="password")
                project_id = st.number_input("Project ID", format="%d", min_value=0, value=project_id_value, placeholder="Enter Project ID")
                deployment_secret = st.text_input("Deployment Secret", placeholder="Enter Deployment Secret", value=deployment_secret)
                
                # Change button text based on login status
                button_text = "Re-Login" if st.session_state.client else "Login"
                submitted = st.form_submit_button(button_text)
                
                if submitted:
                    with st.spinner("Logging to Alita..."):
                        try:

                            st.session_state.client = AlitaClient(
                                base_url=deployment,
                                project_id=project_id,
                                auth_token=api_key,
                                api_extra_headers={"X-SECRET": deployment_secret}
                            )
                            
                            
                            # Fetch specific project secret for pgvector connection
                            try:
                                pgvector_connstr = st.session_state.client.unsecret('pgvector_project_connstr')
                                if pgvector_connstr:
                                    st.session_state.project_secrets = {'pgvector_project_connstr': pgvector_connstr}
                                    logger.info("Successfully retrieved pgvector connection string from project secrets")
                                else:
                                    st.session_state.project_secrets = {}
                                    logger.info("No pgvector connection string found in project secrets")
                            except Exception as e:
                                logger.warning(f"Could not retrieve pgvector connection string: {str(e)}")
                                st.session_state.project_secrets = {}
                            
                            integrations = st.session_state.client.all_models_and_integrations()
                            unique_models = set()
                            models_list = []
                            for entry in integrations:
                                models = entry.get('settings', {}).get('models', [])
                                for model in models:
                                    if model.get('capabilities', {}).get('chat_completion') and model['name'] not in unique_models:
                                        unique_models.add(model['name'])
                                        models_list.append({'name': model['name'], 'integration_id': entry['uid']})
                            st.session_state.agents = st.session_state.client.get_list_of_apps()
                            st.session_state.models = models_list
                            clear_chat_history()
                            
                            # Show immediate success message
                            st.success("✅ Successfully logged in to Alita!")
                            if st.session_state.project_secrets and st.session_state.project_secrets.get('pgvector_project_connstr'):
                                st.success("🔗 Project database connection string retrieved!")
                            elif st.session_state.project_secrets is not None:
                                st.info("ℹ️ Login successful, but no database connection string found in project secrets")
                            
                            # Force a rerun to update the UI
                            st.rerun()
                        except Exception as e:
                            logger.error(f"Error loggin to ELITEA: {format_exc()}")
                            st.session_state.agents = None
                            st.session_state.client = None
                            st.session_state.models = None
                            st.session_state.llm = None
                            st.session_state.project_secrets = None
                            st.error(f"Error loggin to ELITEA ")
        
        # Main tabs
        llmconfig, toolkit_config = st.tabs(["Alita Agents", "Toolkit Testing"])
        
        with llmconfig:
            if st.session_state.client:
                st.title("Available Agents")
                st.write("This one will load latest version of agent")
                with st.form("agents_form", clear_on_submit=False):
                    options = st.selectbox("Select an agent to load", (agent['name'] for agent in st.session_state.agents))
                    agent_version_name = st.text_input("Agent Version Name", value='latest', placeholder="Enter Version ID")
                    agent_type = st.selectbox("Agent Type (leave blank for default)", [""] + agent_types)
                    custom_tools = st.text_area("Custom Tools", placeholder="Enter Custom Tools in List Dict format")
                    submitted = st.form_submit_button("Load Agent")
                    if submitted:
                        with st.spinner("Loading Agent..."):
                            agent = next((a for a in st.session_state.agents if a['name'] == options), None)
                            if agent:
                                agent_id = agent['id']
                                agent_details = st.session_state.client.get_app_details(agent_id)
                                latest_version = next((v for v in agent_details['versions'] if v['name'] == agent_version_name), None)
                                if latest_version:
                                    agent_version_id = latest_version['id']
                                    #
                                    import sqlite3
                                    from langgraph.checkpoint.sqlite import SqliteSaver
                                    #
                                    memory = SqliteSaver(
                                        sqlite3.connect("memory.db", check_same_thread=False)
                                    )
                                    #
                                    try:
                                        custom_tools_json = json.loads(custom_tools)
                                        if not isinstance(custom_tools_json, list):
                                            raise ValueError("Custom tools should be a list of dictionaries")
                                    except:
                                        custom_tools_json = []
                                    
                                    # Extract and store agent toolkit configurations
                                    try:
                                        # Get complete agent configuration
                                        agent_version_details = None
                                        agent_full_config = None
                                        
                                        # Try to get the complete agent configuration
                                        try:
                                            agent_version_details = st.session_state.client.get_app_version_details(agent_id, agent_version_id)
                                            agent_full_config = agent_version_details
                                        except AttributeError:
                                            try:
                                                agent_version_details = st.session_state.client.get_application_version_details(agent_id, agent_version_id)
                                                agent_full_config = agent_version_details
                                            except AttributeError:
                                                # Use the version details we already have
                                                agent_full_config = latest_version
                                        
                                        # Debug: Log the complete agent configuration
                                        logger.info(f"Agent full configuration: {json.dumps(agent_full_config, indent=2)}")
                                        
                                        # Try different possible locations for toolkit information
                                        toolkit_sources = []
                                        
                                        if agent_full_config:
                                            # Check common locations for toolkit configurations
                                            possible_toolkit_keys = ['tools', 'toolkits', 'integrations', 'tool_configs', 'tool_resources']
                                            
                                            for key in possible_toolkit_keys:
                                                if key in agent_full_config and agent_full_config[key]:
                                                    toolkit_sources.append((key, agent_full_config[key]))
                                                    logger.info(f"Found toolkit source '{key}': {agent_full_config[key]}")
                                            
                                            # Also check nested configurations
                                            if 'config' in agent_full_config and isinstance(agent_full_config['config'], dict):
                                                for key in possible_toolkit_keys:
                                                    if key in agent_full_config['config'] and agent_full_config['config'][key]:
                                                        toolkit_sources.append((f"config.{key}", agent_full_config['config'][key]))
                                                        logger.info(f"Found nested toolkit source 'config.{key}': {agent_full_config['config'][key]}")
                                        
                                        # Process found toolkit configurations
                                        st.session_state.agent_toolkits = []
                                        st.session_state.agent_toolkit_configs = {}
                                        
                                        for source_name, toolkit_data in toolkit_sources:
                                            logger.info(f"Processing toolkit source '{source_name}': {toolkit_data}")
                                            
                                            if isinstance(toolkit_data, list):
                                                for tool_config in toolkit_data:
                                                    if isinstance(tool_config, dict):
                                                        # Try different ways to extract toolkit identifier
                                                        # Priority: type > toolkit_name > name (since type is more reliable)
                                                        toolkit_identifier = None
                                                        toolkit_type = None
                                                        
                                                        # First try to get the type (most reliable for matching)
                                                        if 'type' in tool_config and tool_config['type']:
                                                            toolkit_type = tool_config['type']
                                                            toolkit_identifier = toolkit_type
                                                        
                                                        # Fallback to other name fields if type not found
                                                        if not toolkit_identifier:
                                                            name_keys = ['toolkit_name', 'name', 'tool_type', 'integration_name']
                                                            for name_key in name_keys:
                                                                if name_key in tool_config and tool_config[name_key]:
                                                                    toolkit_identifier = tool_config[name_key]
                                                                    break
                                                        
                                                        if toolkit_identifier:
                                                            logger.info(f"Found toolkit identifier: {toolkit_identifier} (type: {toolkit_type}) with config: {tool_config}")
                                                            
                                                            # Try to match with available toolkits using type-based matching
                                                            matched_toolkit = None
                                                            
                                                            # First, try exact type matching (most reliable)
                                                            if toolkit_type:
                                                                for available_toolkit in st.session_state.tooklit_names:
                                                                    # Check if the available toolkit name contains the type
                                                                    available_lower = available_toolkit.lower()
                                                                    type_lower = toolkit_type.lower()
                                                                    
                                                                    # Direct type match or type within toolkit name
                                                                    if (type_lower == available_lower or 
                                                                        type_lower in available_lower or
                                                                        available_lower in type_lower):
                                                                        matched_toolkit = available_toolkit
                                                                        logger.info(f"Matched by type '{toolkit_type}' to '{available_toolkit}'")
                                                                        break
                                                            
                                                            # If no type match, try identifier matching
                                                            if not matched_toolkit:
                                                                normalized_identifier = toolkit_identifier.replace('_', '').replace('-', '').replace(' ', '').lower()
                                                                
                                                                for available_toolkit in st.session_state.tooklit_names:
                                                                    available_normalized = available_toolkit.replace('_', '').replace('-', '').replace(' ', '').lower()
                                                                    
                                                                    if (available_normalized == normalized_identifier or 
                                                                        normalized_identifier in available_normalized or 
                                                                        available_normalized in normalized_identifier):
                                                                        matched_toolkit = available_toolkit
                                                                        logger.info(f"Matched by identifier '{toolkit_identifier}' to '{available_toolkit}'")
                                                                        break
                                                            
                                                            # Store the result
                                                            if matched_toolkit:
                                                                if matched_toolkit not in st.session_state.agent_toolkits:
                                                                    st.session_state.agent_toolkits.append(matched_toolkit)
                                                                st.session_state.agent_toolkit_configs[matched_toolkit] = tool_config.get('settings', tool_config)
                                                                logger.info(f"Successfully matched '{toolkit_identifier}' (type: {toolkit_type}) to available toolkit '{matched_toolkit}'")
                                                            else:
                                                                # Keep original identifier even if not found in available toolkits
                                                                if toolkit_identifier not in st.session_state.agent_toolkits:
                                                                    st.session_state.agent_toolkits.append(toolkit_identifier)
                                                                st.session_state.agent_toolkit_configs[toolkit_identifier] = tool_config.get('settings', tool_config)
                                                                logger.warning(f"Could not match '{toolkit_identifier}' (type: {toolkit_type}) to any available toolkit")
                                                                logger.warning(f"Available toolkits: {st.session_state.tooklit_names}")
                                        
                                        # Store raw agent config for debugging
                                        st.session_state.agent_raw_config = agent_full_config
                                        
                                        logger.info(f"Final agent toolkits: {st.session_state.agent_toolkits}")
                                        logger.info(f"Available toolkits: {st.session_state.tooklit_names}")
                                        logger.info(f"Agent toolkit configs: {list(st.session_state.agent_toolkit_configs.keys())}")
                                        
                                        if not st.session_state.agent_toolkits:
                                            logger.warning("No toolkits extracted from agent configuration")
                                            
                                    except Exception as e:
                                        logger.error(f"Error extracting agent toolkits: {str(e)}")
                                        logger.error(f"Full error: {format_exc()}")
                                        st.session_state.agent_toolkits = []
                                        st.session_state.agent_toolkit_configs = {}
                                        st.session_state.agent_raw_config = None
                                    
                                    st.session_state.agent_executor = st.session_state.client.application(
                                        application_id=agent_id,
                                        application_version_id=agent_version_id,
                                        app_type=agent_type if agent_type else None,
                                        tools=custom_tools_json,
                                        memory=memory,
                                    )
                                    st.session_state.agent_chat = True
                                    #
                                    st.session_state.agent_name = options
                                    clear_chat_history()
                                else:
                                    st.session_state.agent_executor = None
                                    st.session_state.agent_name = None
                                    clear_chat_history()
                                    st.error("Agent version not found")

        with toolkit_config:
            st.title("🔧 Toolkit Testing")
            st.markdown("""
            **Welcome to Toolkit Testing!** This interface allows you to:
            - Configure and test individual toolkits
            - Run toolkit functions with AI assistance (Tool Mode) 
            - Execute toolkit functions directly (Function Mode)
            """)
            
            # Check if user is logged in
            if not st.session_state.client:
                st.warning("⚠️ **Please log in first!**")
                st.info("""
                📋 **To use Toolkit Testing:**
                1. Enter your credentials in the sidebar form
                2. Click **Login** to authenticate
                3. Return to this tab to configure and test toolkits
                
                💡 **Tip:** You can find your API key and deployment URL in your Alita dashboard.
                """)
                st.stop()
            
            # User is logged in, proceed with toolkit testing
            if st.session_state.client:
                # Show project secrets status with detailed debugging
                secrets_status = st.session_state.project_secrets
                
                if secrets_status and isinstance(secrets_status, dict) and secrets_status.get('pgvector_project_connstr'):
                    st.success("✅ **Project secrets loaded** - Database connection will be auto-configured")
                elif secrets_status is not None:
                    st.info("ℹ️ **Project secrets checked** - No pgvector connection string found")
                else:
                    st.warning("⚠️ **Project secrets not loaded yet** - You may need to configure database connections manually")
                
                # Debug info (can be removed later)
                with st.expander("🔍 Debug Info", expanded=False):
                    st.write(f"**Project Secrets Status:** {type(secrets_status)} - {secrets_status}")
                    # st.write(f"**LLM Status:** {'Connected' if st.session_state.llm else 'Not Connected'}")
                
                # Toolkit selection and configuration
                st.markdown("---")
                st.subheader("📋 Step 1: Select and Configure Toolkit")
                
                # Determine which toolkits to show
                if st.session_state.agent_chat and st.session_state.agent_toolkits:
                    # Show only agent's toolkits
                    st.info(f"🤖 **Showing toolkits from active agent:** {st.session_state.agent_name}")
                    
                    # Show debug information
                    with st.expander("🔍 Agent Toolkit Debug Info", expanded=False):
                        st.write("**Agent Toolkits Found:**", st.session_state.agent_toolkits)
                        st.write("**Available SDK Toolkits:**", st.session_state.tooklit_names)
                        
                        if st.session_state.agent_raw_config:
                            st.write("**Raw Agent Configuration:**")
                            st.json(st.session_state.agent_raw_config)
                        
                        if st.session_state.agent_toolkit_configs:
                            st.write("**Agent Toolkit Configurations:**")
                            for toolkit_name, config in st.session_state.agent_toolkit_configs.items():
                                st.write(f"**{toolkit_name}:**")
                                
                                # Show type and name separately for clarity
                                if isinstance(config, dict):
                                    toolkit_type = config.get('type', 'N/A')
                                    toolkit_display_name = config.get('toolkit_name', config.get('name', 'N/A'))
                                    st.write(f"  - **Type:** `{toolkit_type}`")
                                    st.write(f"  - **Name:** `{toolkit_display_name}`")
                                    st.write(f"  - **Settings:**")
                                    st.json(config.get('settings', config))
                                else:
                                    st.json(config)
                    
                    # Find matching toolkits
                    available_toolkits = []
                    unmatched_toolkits = []
                    
                    for agent_toolkit in st.session_state.agent_toolkits:
                        found_match = False
                        
                        # Get the agent toolkit config to check the type
                        agent_config = st.session_state.agent_toolkit_configs.get(agent_toolkit, {})
                        agent_type = agent_config.get('type', '') if isinstance(agent_config, dict) else ''
                        
                        # First try exact match by name
                        for i, toolkit_name in enumerate(st.session_state.tooklit_names):
                            if toolkit_name == agent_toolkit:
                                available_toolkits.append((i, toolkit_name))
                                found_match = True
                                break
                        
                        # If no exact match, try type-based matching (most reliable)
                        if not found_match and agent_type:
                            for i, toolkit_name in enumerate(st.session_state.tooklit_names):
                                toolkit_lower = toolkit_name.lower()
                                type_lower = agent_type.lower()
                                
                                # Check if type matches or is contained in toolkit name
                                if (type_lower == toolkit_lower or 
                                    type_lower in toolkit_lower or 
                                    toolkit_lower in type_lower):
                                    available_toolkits.append((i, toolkit_name))
                                    found_match = True
                                    st.info(f"🔗 **Type Match:** Agent '{agent_toolkit}' (type: `{agent_type}`) → SDK `{toolkit_name}`")
                                    break
                        
                        # Finally try fuzzy matching by name if type matching failed
                        if not found_match:
                            agent_normalized = agent_toolkit.replace('_', '').replace('-', '').replace(' ', '').lower()
                            for i, toolkit_name in enumerate(st.session_state.tooklit_names):
                                toolkit_normalized = toolkit_name.replace('_', '').replace('-', '').replace(' ', '').lower()
                                if (agent_normalized in toolkit_normalized or 
                                    toolkit_normalized in agent_normalized or
                                    agent_normalized == toolkit_normalized):
                                    available_toolkits.append((i, toolkit_name))
                                    found_match = True
                                    st.info(f"🔗 **Name Match:** Agent '{agent_toolkit}' → SDK `{toolkit_name}`")
                                    break
                        
                        if not found_match:
                            unmatched_toolkits.append({
                                'name': agent_toolkit,
                                'type': agent_type,
                                'config': agent_config
                            })
                    
                    # Show results
                    if available_toolkits:
                        st.success(f"✅ **Found {len(available_toolkits)} matching toolkits**")
                    
                    if unmatched_toolkits:
                        st.warning(f"⚠️ **{len(unmatched_toolkits)} toolkits from agent not found in SDK:**")
                        for unmatched in unmatched_toolkits:
                            if isinstance(unmatched, dict):
                                st.write(f"  - **{unmatched['name']}** (type: `{unmatched['type']}`)")
                            else:
                                st.write(f"  - **{unmatched}**")
                        st.info("💡 These might be custom toolkits or use different names. You can still test available toolkits.")
                        
                        # Show type comparison for debugging
                        with st.expander("🔍 Type Comparison Debug", expanded=False):
                            st.write("**Unmatched Agent Types vs Available SDK Toolkits:**")
                            for unmatched in unmatched_toolkits:
                                if isinstance(unmatched, dict) and unmatched['type']:
                                    st.write(f"Agent type: `{unmatched['type']}`")
                                    st.write("Available SDK toolkits:")
                                    for sdk_toolkit in st.session_state.tooklit_names:
                                        st.write(f"  - {sdk_toolkit}")
                                    st.write("---")
                    
                    if not available_toolkits:
                        st.error("❌ No matching toolkits found for the current agent.")
                        st.info("🔄 **Fallback:** Showing all available toolkits instead")
                        # Fallback to all toolkits
                        available_toolkits = [(i, name) for i, name in enumerate(st.session_state.tooklit_names)]
                        
                else:
                    # Show all available toolkits
                    st.info("🔧 **Showing all available toolkits**")
                    available_toolkits = [(i, name) for i, name in enumerate(st.session_state.tooklit_names)]
                
                # Select toolkit type (outside of form to allow dynamic updates)
                selected_toolkit_idx = None
                if available_toolkits:
                    selected_toolkit_idx = st.selectbox(
                        "🛠️ Select a toolkit", 
                        options=[idx for idx, name in available_toolkits],
                        format_func=lambda idx: next(name for i, name in available_toolkits if i == idx),
                        help="Choose from available toolkits",
                        key="toolkit_selector"
                    )
                
                # Configuration form (updates automatically when toolkit changes)
                if selected_toolkit_idx is not None:
                    toolkit_schema = st.session_state.tooklit_configs[selected_toolkit_idx]
                    st.info(f"**Selected Toolkit:** {toolkit_schema['title']}")
                    
                    # Show toolkit description if available
                    if 'description' in toolkit_schema:
                        st.markdown(f"**Description:** {toolkit_schema['description']}")
                    
                    with st.form("toolkit_config_form", clear_on_submit=False):
                        # Create configuration inputs based on schema
                        toolkit_config_values = {}
                        config_schema = create_tooklit_schema(toolkit_schema)
                        
                        # Get agent's pre-configured values for this toolkit
                        agent_config = {}
                        if st.session_state.agent_chat and toolkit_schema['title'] in st.session_state.agent_toolkit_configs:
                            agent_config = st.session_state.agent_toolkit_configs[toolkit_schema['title']]
                            st.success(f"✅ **Auto-populated from agent:** {st.session_state.agent_name}")
                        
                        if config_schema:
                            st.markdown("### Configuration Parameters")
                            for field_name, field_schema in config_schema.items():
                                field_type = field_schema.get('type', 'string')
                                field_description = field_schema.get('description', '')
                                field_default = field_schema.get('default', '')
                                is_secret = field_schema.get('json_schema_extra', {}).get('secret', False)
                                is_required = field_name in toolkit_schema.get('required', [])
                                
                                # Use agent config value if available, otherwise use schema default
                                default_value = agent_config.get(field_name, field_default)
                                
                                label = f"{'🔒 ' if is_secret else ''}{'*' if is_required else ''}{field_name.replace('_', ' ').title()}"
                                
                                if field_type == 'string':
                                    if is_secret:
                                        toolkit_config_values[field_name] = st.text_input(
                                            label,
                                            value=str(default_value) if default_value else '', 
                                            help=field_description,
                                            type="password",
                                            key=f"config_{field_name}_{selected_toolkit_idx}"
                                        )
                                    else:
                                        toolkit_config_values[field_name] = st.text_input(
                                            label,
                                            value=str(default_value) if default_value else '', 
                                            help=field_description,
                                            key=f"config_{field_name}_{selected_toolkit_idx}"
                                        )
                                elif field_type == 'integer':
                                    toolkit_config_values[field_name] = st.number_input(
                                        label,
                                        value=int(default_value) if default_value else 0, 
                                        help=field_description,
                                        step=1,
                                        key=f"config_{field_name}_{selected_toolkit_idx}"
                                    )
                                elif field_type == 'number':
                                    toolkit_config_values[field_name] = st.number_input(
                                        label,
                                        value=float(default_value) if default_value else 0.0, 
                                        help=field_description,
                                        key=f"config_{field_name}_{selected_toolkit_idx}"
                                    )
                                elif field_type == 'boolean':
                                    toolkit_config_values[field_name] = st.checkbox(
                                        label,
                                        value=bool(default_value) if default_value is not None else (field_default if isinstance(field_default, bool) else False), 
                                        help=field_description,
                                        key=f"config_{field_name}_{selected_toolkit_idx}"
                                    )
                                elif field_type == 'array':
                                    items_schema = field_schema.get('items', {})
                                    if items_schema.get('type') == 'string':
                                        # Convert array to newline-separated string
                                        array_value = ""
                                        if isinstance(default_value, list):
                                            array_value = '\n'.join(str(item) for item in default_value)
                                        elif default_value:
                                            array_value = str(default_value)
                                        
                                        # Auto-populate selected_tools with all available tools
                                        if field_name == 'selected_tools':
                                            # Get available tools from the schema's json_schema_extra
                                            args_schemas = field_schema.get('json_schema_extra', {}).get('args_schemas', {})
                                            if args_schemas:
                                                available_tools = list(args_schemas.keys())
                                                
                                                # Create a session state key for this toolkit's auto-population
                                                auto_populate_key = f"auto_populate_tools_{toolkit_schema['title']}_{selected_toolkit_idx}"
                                                
                                                # Auto-populate if field is empty and not already auto-populated
                                                if not array_value and auto_populate_key not in st.session_state:
                                                    array_value = '\n'.join(available_tools)
                                                    st.session_state[auto_populate_key] = True
                                                    st.success(f"🔧 **Auto-populated {len(available_tools)} tools:** {', '.join(available_tools)}")
                                                elif array_value and auto_populate_key in st.session_state:
                                                    # Show info about existing auto-population
                                                    current_tools = [line.strip() for line in array_value.split('\n') if line.strip()]
                                                    st.info(f"📋 **{len(current_tools)} tools configured** (auto-populated: {len(available_tools)} available)")
                                                
                                                # Add a button to reset to all tools
                                                col1, col2 = st.columns([3, 1])
                                                with col2:
                                                    if st.button("📋 Load All Tools", help="Auto-populate with all available tools", key=f"load_all_tools_{selected_toolkit_idx}"):
                                                        # Update the session state to trigger rerun with populated tools
                                                        st.session_state[f"tools_loaded_{selected_toolkit_idx}"] = '\n'.join(available_tools)
                                                        st.success(f"✅ Loaded {len(available_tools)} tools")
                                                        st.rerun()
                                                
                                                # Check if tools were just loaded via button
                                                if f"tools_loaded_{selected_toolkit_idx}" in st.session_state:
                                                    array_value = st.session_state[f"tools_loaded_{selected_toolkit_idx}"]
                                                    del st.session_state[f"tools_loaded_{selected_toolkit_idx}"]  # Clean up
                                                
                                                with col1:
                                                    array_input = st.text_area(
                                                        f"{label} (one per line)",
                                                        value=array_value,
                                                        help=f"{field_description} - Enter one item per line. Available tools: {', '.join(available_tools)}",
                                                        key=f"config_{field_name}_{selected_toolkit_idx}"
                                                    )
                                            else:
                                                array_input = st.text_area(
                                                    f"{label} (one per line)",
                                                    value=array_value,
                                                    help=f"{field_description} - Enter one item per line",
                                                    key=f"config_{field_name}_{selected_toolkit_idx}"
                                                )
                                        else:
                                            array_input = st.text_area(
                                                f"{label} (one per line)",
                                                value=array_value,
                                                help=f"{field_description} - Enter one item per line",
                                                key=f"config_{field_name}_{selected_toolkit_idx}"
                                            )
                                        toolkit_config_values[field_name] = [line.strip() for line in array_input.split('\n') if line.strip()]
                        else:
                            st.info("This toolkit doesn't require additional configuration.")
                        
                        # Configure toolkit button and test connection button
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.session_state.agent_chat:
                                # Show "Configure & Switch to Testing" when agent is active
                                submitted = st.form_submit_button("� Configure & Switch to Testing", type="primary",
                                                                 help="Configure toolkit and switch from chat to testing view")
                                configure_and_switch = submitted  # Same action for this button
                            else:
                                # Show regular "Configure Toolkit" when no agent active
                                submitted = st.form_submit_button("⚙️ Configure Toolkit", type="primary")
                                configure_and_switch = False
                        with col2:
                            test_connection = st.form_submit_button("🔗 Test Connection")
                        
                        if submitted or configure_and_switch:
                            with st.spinner("Configuring Toolkit..."):
                                try:
                                    # Validate required fields
                                    required_fields = toolkit_schema.get('required', [])
                                    missing_fields = []
                                    
                                    for field in required_fields:
                                        if field not in toolkit_config_values or not toolkit_config_values[field]:
                                            missing_fields.append(field)
                                    
                                    if missing_fields:
                                        st.error(f"Missing required fields: {', '.join(missing_fields)}")
                                    else:
                                        toolkit_name = toolkit_schema['title']
                                        
                                        # Store configuration in session state with all details preserved
                                        st.session_state.configured_toolkit = {
                                            'name': toolkit_name,
                                            'schema': toolkit_schema,
                                            'config': toolkit_config_values.copy(),  # Make a copy to preserve values
                                            'agent_context': {
                                                'agent_name': st.session_state.agent_name if st.session_state.agent_chat else None,
                                                'from_agent': st.session_state.agent_chat,
                                                'original_agent_config': st.session_state.agent_toolkit_configs.get(toolkit_name, {}) if st.session_state.agent_chat else {}
                                            }
                                        }
                                        st.session_state.show_toolkit_testing = True
                                        
                                        # Log the configuration for debugging
                                        logger.info(f"Stored toolkit configuration: {st.session_state.configured_toolkit}")
                                        
                                        if configure_and_switch or (submitted and st.session_state.agent_chat):
                                            # Terminate chat and switch to testing view
                                            st.session_state.agent_chat = False
                                            # Don't clear messages completely, just mark as not in chat mode
                                            st.success(f"✅ Switched to toolkit testing for: {toolkit_name}")
                                            st.info("🔄 **Switching to toolkit testing view...**")
                                            # Force immediate state save before rerun
                                            st.session_state.configured_toolkit_ready = True
                                            st.rerun()  # Force immediate refresh
                                        else:
                                            st.success(f"✅ Toolkit {toolkit_name} configured successfully!")
                                            st.info("👉 **Go to the main area to start testing your toolkit!**")
                                            st.balloons()
                                        
                                except Exception as e:
                                    st.error(f"❌ Error configuring toolkit: {str(e)}")
                                    logger.error(f"Toolkit configuration error: {str(e)}")
                                    logger.error(f"Full error: {format_exc()}")
                        
                        if test_connection:
                            with st.spinner("Testing connection..."):
                                try:
                                    # Try to instantiate the toolkit to test connection
                                    toolkit_name = toolkit_schema['title']
                                    
                                    # Test with current config
                                    toolkit_test_config = {
                                        'toolkit_name': toolkit_name,
                                        'settings': toolkit_config_values
                                    }
                                    tools = instantiate_toolkit(toolkit_test_config)
                                    st.success("✅ Connection test successful!")
                                    
                                except Exception as e:
                                    st.error(f"❌ Connection test failed: {str(e)}")
                
                # Store toolkit configuration for main view
                if hasattr(st.session_state, 'configured_toolkit') and st.session_state.configured_toolkit:
                    st.session_state.show_toolkit_testing = True
                    
                    # Show current configured toolkit status
                    toolkit_name = st.session_state.configured_toolkit['name']
                    st.success(f"✅ **{toolkit_name}** is configured and ready for testing!")
                    st.info("👉 **Check the main area to start testing your toolkit**")
                    
                    # Quick actions
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 Reconfigure", help="Configure a different toolkit"):
                            st.session_state.configured_toolkit = None
                            st.session_state.show_toolkit_testing = False
                            st.rerun()
                    with col2:
                        if st.button("🗑️ Clear", help="Clear current configuration"):
                            st.session_state.configured_toolkit = None
                            st.session_state.show_toolkit_testing = False
                            st.rerun()
                else:
                    st.session_state.show_toolkit_testing = False
                    
            else:
                st.title("🔐 Please Login First")
                st.info("You need to login to your Alita deployment before you can test toolkits.")
                st.markdown("👈 Please use the **Alita Login Form** in the sidebar to authenticate.")
                        
    # Main content area
    if st.session_state.client and st.session_state.agent_executor and st.session_state.agent_chat:
        try:
            st.title(st.session_state.agent_name)
        except:
            st.title("Login to Elitea to load an agent")
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar=ai_icon if message["role"] == "assistant" else user_icon):
                st.markdown(message["content"])
        if prompt := st.chat_input():
            st.chat_message("user", avatar=user_icon).write(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("assistant", avatar=ai_icon):
                st_cb = AlitaStreamlitCallback(st)
                logger.info(st.session_state.messages)
                response = st.session_state.agent_executor.invoke(
                    {"input": [prompt], "chat_history": st.session_state.messages[:-1]},
                    { 'callbacks': [st_cb], 'configurable': {"thread_id": st.session_state.thread_id}}
                )
                st.write(response["output"])
                st.session_state.thread_id = response.get("thread_id", None)
                st.session_state.messages.append({"role": "assistant", "content": response["output"]})
    
    elif st.session_state.client and st.session_state.show_toolkit_testing and st.session_state.configured_toolkit:
        # Toolkit Testing Main View
        st.title("🚀 Toolkit Testing Interface")
        
        # Add info about the new testing capabilities
        st.info("""
        🔥 **Enhanced Testing Features:**
        - **Event Tracking**: Monitor custom events dispatched during tool execution
        - **Callback Support**: Full runtime callback support for real-time monitoring
        - **Error Handling**: Detailed error reporting with execution context
        - **Client Integration**: Uses the same method available in the API client
        """)
        
        # Sidebar with testing information
        with st.sidebar:
            st.markdown("### 🔧 Testing Information")
            st.markdown("""
            **Current Method**: `client.test_toolkit_tool()`
            
            **Features**:
            - ✅ Runtime callbacks
            - ✅ Event dispatching  
            - ✅ Error handling
            - ✅ Configuration validation
            
            **API Usage**:
            ```python
            result = client.test_toolkit_tool(
                toolkit_config={
                    'toolkit_name': 'github',
                    'settings': {'token': '...'}
                },
                tool_name='get_repo',
                tool_params={'repo': 'alita'},
                runtime_config={'callbacks': [cb]}
            )
            ```
            """)
        
        toolkit_config = st.session_state.configured_toolkit
        
        # Header with toolkit info and navigation
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"✅ **Active Toolkit:** {toolkit_config['name']}")
            
            # Show agent context and configuration source
            agent_context = toolkit_config.get('agent_context', {})
            if agent_context.get('from_agent') and agent_context.get('agent_name'):
                st.info(f"🤖 **Configuration from agent:** {agent_context['agent_name']}")
            
            # Show configuration summary
            config_count = len(toolkit_config.get('config', {}))
            st.caption(f"📋 **{config_count} configuration parameters loaded**")
            
        with col2:
            if st.session_state.agent_executor and st.session_state.agent_name:
                if st.button("💬 Back to Chat", help=f"Return to chat with {st.session_state.agent_name}"):
                    st.session_state.agent_chat = True
                    st.session_state.show_toolkit_testing = False
                    st.rerun()
        
        # Debug configuration preservation
        with st.expander("🔧 Toolkit Configuration Details", expanded=False):
            st.write("**Toolkit Name:**", toolkit_config['name'])
            st.write("**Configuration Source:**", "Agent" if agent_context.get('from_agent') else "Manual")
            if agent_context.get('agent_name'):
                st.write("**Agent:**", agent_context['agent_name'])
            
            st.write("**Current Configuration:**")
            current_config = toolkit_config.get('config', {})
            if current_config:
                st.json(current_config)
            else:
                st.warning("⚠️ No configuration found - this might indicate a configuration preservation issue")
            
            if agent_context.get('original_agent_config'):
                st.write("**Original Agent Configuration:**")
                st.json(agent_context['original_agent_config'])
        
        # Test mode selection in main view - simplified to function mode only
        st.markdown("---")
        st.subheader("📋 Step 2: Function Testing Mode")
        
        # Force to function mode only to avoid client dependency issues
        test_mode = "⚡ Without LLM (Function Mode)"
        st.info("🔧 **Function Mode:** Call specific toolkit functions directly with custom parameters.")
        
        st.markdown("---")
        
        # Directly proceed to Function Mode (no LLM option)
        st.markdown("### ⚡ Direct Function Testing")
        
        # Information about the new testing method
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("💡 **Enhanced Testing:** Using `AlitaClient.test_toolkit_tool()` method with event capture and runtime callbacks.")
        with col2:
            st.markdown("**🔧 Method:** `test_toolkit_tool`")
        
        # Show available functions
        try:
            # Use the client to get toolkit tools for display
            # We'll call the toolkit utilities directly to get tools
            from .toolkit_utils import instantiate_toolkit_with_client
            
            # Create a simple LLM client for tool instantiation
            try:
                if not st.session_state.client:
                    raise ValueError("Alita client not available")
                    
                llm_client = st.session_state.client.get_llm(
                    model_name="gpt-4o-mini",
                    model_config={
                        "temperature": 0.1,
                        "max_tokens": 1000,
                        "top_p": 1.0
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create LLM client for toolkit instantiation: {str(e)}. Falling back to basic mode.")
                # Fallback to basic instantiation
                from .toolkit_utils import instantiate_toolkit as fallback_instantiate
                toolkit_test_config = {
                    'toolkit_name': toolkit_config['name'],
                    'settings': toolkit_config['config']
                }
                tools = fallback_instantiate(toolkit_test_config)
            else:
                toolkit_test_config = {
                    'toolkit_name': toolkit_config['name'],
                    'settings': toolkit_config['config']
                }
                tools = instantiate_toolkit_with_client(
                    toolkit_test_config, 
                    llm_client, 
                    st.session_state.client
                )
            
            if tools:
                st.markdown("### 📚 Available Functions:")
                st.info("🔧 **Auto-Population Enabled:** All available tools are automatically selected when you configure a toolkit. You can modify the selection below.")
                function_names = [tool.name for tool in tools]
                
                # Auto-populate selected tools with all available tools
                if f"selected_tools_{toolkit_config['name']}" not in st.session_state:
                    st.session_state[f"selected_tools_{toolkit_config['name']}"] = function_names
                
                # Add controls for tool selection
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown("**Tool Selection:**")
                with col2:
                    if st.button("✅ Select All", help="Select all available tools", key=f"select_all_{toolkit_config['name']}"):
                        st.session_state[f"selected_tools_{toolkit_config['name']}"] = function_names
                        st.rerun()
                with col3:
                    if st.button("❌ Clear All", help="Clear all selected tools", key=f"clear_all_{toolkit_config['name']}"):
                        st.session_state[f"selected_tools_{toolkit_config['name']}"] = []
                        st.rerun()
                
                # Create multi-select for tools with auto-population
                selected_tools = st.multiselect(
                    "Select tools to test:", 
                    function_names,
                    default=st.session_state[f"selected_tools_{toolkit_config['name']}"],
                    help="Choose the tools you want to test. All tools are selected by default.",
                    key=f"tools_multiselect_{toolkit_config['name']}"
                )
                
                # Update session state when selection changes
                st.session_state[f"selected_tools_{toolkit_config['name']}"] = selected_tools
                
                # Show selection summary
                if selected_tools:
                    st.success(f"✅ **{len(selected_tools)} of {len(function_names)} tools selected**")
                else:
                    st.warning("⚠️ **No tools selected** - Please select at least one tool to proceed.")
                
                # Create function selection dropdown from selected tools
                if selected_tools:
                    selected_function = st.selectbox(
                        "Select a function to configure and run:", 
                        selected_tools,
                        help="Choose the specific function you want to configure and execute",
                        key="function_selector_main"
                    )
                else:
                    st.warning("Please select at least one tool to proceed.")
                    selected_function = None
                
                if selected_function:
                    selected_tool = next(tool for tool in tools if tool.name == selected_function)
                    
                    # Function details
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**📖 Description:** {selected_tool.description}")
                    with col2:
                        st.markdown(f"**🏷️ Function:** `{selected_function}`")
                    
                    # Show function schema if available
                    if hasattr(selected_tool, 'args_schema') and selected_tool.args_schema:
                        with st.expander("📋 Function Schema", expanded=False):
                            try:
                                schema = selected_tool.args_schema.schema()
                                st.json(schema)
                            except:
                                st.write("Schema not available")
                    
                    # Function parameter form (instead of JSON input)
                    st.markdown("---")
                    with st.form("function_params_form", clear_on_submit=False):
                        parameters = render_function_parameters_form(selected_tool, f"func_{selected_function}")
                        
                        # LLM Configuration Section
                        st.markdown("### 🤖 LLM Configuration")
                        st.markdown("Configure the LLM settings for tools that require AI capabilities:")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            llm_model = st.selectbox(
                                "LLM Model:",
                                options=['gpt-4o-mini', 'gpt-4o', 'gpt-4', 'gpt-3.5-turbo', 'claude-3-haiku', 'claude-3-sonnet'],
                                index=0,
                                help="Select the LLM model to use for tools that require AI capabilities"
                            )
                            
                            temperature = st.slider(
                                "Temperature:",
                                min_value=0.0,
                                max_value=1.0,
                                value=0.1,
                                step=0.1,
                                help="Controls randomness in AI responses. Lower values are more deterministic."
                            )
                        
                        with col2:
                            max_tokens = st.number_input(
                                "Max Tokens:",
                                min_value=100,
                                max_value=4000,
                                value=1000,
                                step=100,
                                help="Maximum number of tokens in the AI response"
                            )
                            
                            top_p = st.slider(
                                "Top-p:",
                                min_value=0.1,
                                max_value=1.0,
                                value=1.0,
                                step=0.1,
                                help="Controls diversity via nucleus sampling"
                            )
                        
                        # Create LLM config
                        llm_config = {
                            'max_tokens': max_tokens,
                            'temperature': temperature,
                            'top_p': top_p
                        }
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            run_function = st.form_submit_button("⚡ Run Function", type="primary")
                        with col2:
                            clear_params = st.form_submit_button("🗑️ Clear Form")
                            if clear_params:
                                st.rerun()
                        
                        if run_function and parameters is not None:
                            with st.spinner("⚡ Executing function..."):
                                try:
                                    # Use the client's test_toolkit_tool method
                                    # Create callback to capture events
                                    from langchain_core.callbacks import BaseCallbackHandler
                                    
                                    class StreamlitEventCallback(BaseCallbackHandler):
                                        """Callback handler for capturing custom events in Streamlit."""
                                        def __init__(self):
                                            self.events = []
                                            self.steps = []
                                            
                                        def on_custom_event(self, name, data, **kwargs):
                                            """Handle custom events dispatched by tools."""
                                            import datetime
                                            event = {
                                                'name': name, 
                                                'data': data, 
                                                'timestamp': datetime.datetime.now().isoformat(),
                                                **kwargs
                                            }
                                            self.events.append(event)
                                            
                                            # Update progress in real-time for certain events
                                            if name == "progress" and isinstance(data, dict):
                                                message = data.get('message', 'Processing...')
                                                step = data.get('step', None)
                                                total_steps = data.get('total_steps', None)
                                                
                                                if step and total_steps:
                                                    progress = step / total_steps
                                                    st.progress(progress, text=f"{message} ({step}/{total_steps})")
                                                else:
                                                    st.info(f"📊 {message}")
                                    
                                    callback = StreamlitEventCallback()
                                    runtime_config = {
                                        'callbacks': [callback],
                                        'configurable': {'streamlit_session': True},
                                        'tags': ['streamlit_testing', toolkit_config['name']]
                                    }
                                    
                                    # Call the client's test method with LLM configuration
                                    result = st.session_state.client.test_toolkit_tool(
                                        toolkit_config={
                                            'toolkit_name': toolkit_config['name'],
                                            'settings': toolkit_config['config']
                                        },
                                        tool_name=selected_function,
                                        tool_params=parameters,
                                        runtime_config=runtime_config,
                                        llm_model=llm_model,
                                        llm_config=llm_config
                                    )
                                    
                                    st.markdown("### 🎯 Function Result:")
                                    
                                    if result['success']:
                                        execution_time = result.get('execution_time_seconds', 0.0)
                                        # Display success status with timing and LLM info
                                        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                                        with col1:
                                            st.success("✅ Function executed successfully!")
                                        with col2:
                                            st.metric("⏱️ Time", f"{execution_time:.3f}s")
                                        with col3:
                                            st.metric("📡 Events", len(result.get('events_dispatched', [])))
                                        with col4:
                                            st.metric("🔧 Tool", result['tool_name'])
                                            llm_used = result.get('llm_model', 'N/A')
                                            st.metric("LLM", llm_used)
                                        
                                        # Display the actual result
                                        with st.container():
                                            st.markdown("**📊 Function Output:**")
                                            tool_result = result['result']
                                            if isinstance(tool_result, (dict, list)):
                                                st.json(tool_result)
                                            elif isinstance(tool_result, str):
                                                if tool_result.startswith('{') or tool_result.startswith('['):
                                                    try:
                                                        parsed_result = json.loads(tool_result)
                                                        st.json(parsed_result)
                                                    except:
                                                        st.code(tool_result, language="text")
                                                else:
                                                    if len(tool_result) > 1000:
                                                        with st.expander("📄 View Full Output", expanded=False):
                                                            st.code(tool_result, language="text")
                                                        st.info(f"Output truncated. Full length: {len(tool_result)} characters.")
                                                    else:
                                                        st.code(tool_result, language="text")
                                            else:
                                                st.code(str(tool_result), language="text")
                                        
                                        # Show events if any were dispatched with better formatting
                                        events = result.get('events_dispatched', [])
                                        if events:
                                            with st.expander(f"📡 Events Dispatched ({len(events)})", expanded=True):
                                                for i, event in enumerate(events):
                                                    with st.container():
                                                        col1, col2 = st.columns([1, 4])
                                                        with col1:
                                                            event_type = event.get('name', 'unknown')
                                                            if event_type == 'progress':
                                                                st.markdown("🔄 **Progress**")
                                                            elif event_type == 'info':
                                                                st.markdown("ℹ️ **Info**")
                                                            elif event_type == 'warning':
                                                                st.markdown("⚠️ **Warning**")
                                                            elif event_type == 'error':
                                                                st.markdown("❌ **Error**")
                                                            else:
                                                                st.markdown(f"📋 **{event_type.title()}**")
                                                        with col2:
                                                            event_data = event.get('data', {})
                                                            if isinstance(event_data, dict) and 'message' in event_data:
                                                                st.write(event_data['message'])
                                                                if len(event_data) > 1:
                                                                    with st.expander("Event Details"):
                                                                        st.json({k: v for k, v in event_data.items() if k != 'message'})
                                                            else:
                                                                st.json(event_data)
                                                    if i < len(events) - 1:
                                                        st.divider()
                                        
                                        # Show execution metadata
                                        with st.expander("🔍 Execution Details", expanded=False):
                                            execution_time = result.get('execution_time_seconds', 0.0)
                                            metadata = {
                                                'tool_name': result['tool_name'],
                                                'toolkit_name': result['toolkit_config'].get('toolkit_name'),
                                                'llm_model': result.get('llm_model'),
                                                'llm_config': llm_config,
                                                'success': result['success'],
                                                'execution_time_seconds': execution_time,
                                                'execution_time_formatted': f"{execution_time:.3f}s",
                                                'events_count': len(result.get('events_dispatched', [])),
                                                'parameters_used': parameters
                                            }
                                            st.json(metadata)
                                    else:
                                        # Display error from the client method
                                        execution_time = result.get('execution_time_seconds', 0.0)
                                        st.error(f"❌ {result['error']} (after {execution_time:.3f}s)")
                                        with st.expander("🔍 Error Details"):
                                            error_details = {
                                                'error': result['error'],
                                                'tool_name': result['tool_name'],
                                                'toolkit_config': result['toolkit_config'],
                                                'llm_model': result.get('llm_model'),
                                                'llm_config': llm_config,
                                                'execution_time_seconds': execution_time,
                                                'execution_time_formatted': f"{execution_time:.3f}s",
                                                'events_dispatched': result.get('events_dispatched', [])
                                            }
                                            st.json(error_details)
                                            
                                except Exception as e:
                                    st.error(f"❌ Error executing function: {str(e)}")
                                    with st.expander("🔍 Error Details"):
                                        st.code(str(e))
            else:
                st.warning("⚠️ No functions available in this toolkit.")
                                
        except Exception as e:
            st.error(f"❌ Error loading toolkit functions: {str(e)}")
            with st.expander("🔍 Error Details"):
                st.code(str(e))
        
        # Display current configuration
        st.markdown("---")
        with st.expander("📋 Current Toolkit Configuration"):
            st.json(st.session_state.configured_toolkit)
            
            # Clear configuration button
            if st.button("🗑️ Clear Toolkit Configuration", key="clear_toolkit_main"):
                st.session_state.configured_toolkit = None
                st.session_state.show_toolkit_testing = False
                st.success("Configuration cleared!")
                st.rerun()
    
    else:
        if st.session_state.client:
            st.title("🎯 Alita SDK Toolkit Interface")
            st.markdown("""
            ### Welcome to the Alita SDK!
            
            **Choose your path:**
            
            🤖 **Agent Chat**: Load an Alita agent for AI-powered conversations
            - Go to **Alita Agents** tab in the sidebar
            - Select and load an agent to start chatting
            
            🔧 **Toolkit Testing**: Test individual toolkits and functions
            - Go to **Toolkit Testing** tab in the sidebar  
            - Configure a toolkit to start testing
            
            💡 **Getting Started:**
            1. Make sure you're logged in (✅ check sidebar)
            2. Choose either Agent Chat or Toolkit Testing
            3. Follow the step-by-step instructions
            """)
        else:
            st.title("🔐 Please Login First")
            st.info("You need to login to your Alita deployment before you can use the interface.")
            st.markdown("👈 Please use the **Alita Login Form** in the sidebar to authenticate.")
