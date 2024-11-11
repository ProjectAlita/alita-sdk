

import base64
import io
from PIL import Image
import logging
 
logging.basicConfig(level=logging.INFO)
from os import environ
from dotenv import load_dotenv
load_dotenv('.env')
logger = logging.getLogger(__name__)

ai_icon = b'<plain_txt_msg:img>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<!plain_txt_msg>'
user_icon = b'<plain_txt_msg:img>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<!plain_txt_msg>'
agent_types = ["pipeline", "react", "llama", "openai", "dial", "autogen"]

def img_to_txt(filename):
    msg = b"<plain_txt_msg:img>"
    with open(filename, "rb") as imageFile:
        msg = msg + base64.b64encode(imageFile.read())
    msg = msg + b"<!plain_txt_msg>"
    return msg

def decode_img(msg):
    msg = msg[msg.find(b"<plain_txt_msg:img>")+len(b"<plain_txt_msg:img>"):
              msg.find(b"<!plain_txt_msg>")]
    msg = base64.b64decode(msg)
    buf = io.BytesIO(msg)
    img = Image.open(buf)
    return img


from src.alita_sdk.llms.alita import AlitaChatModel
from src.alita_sdk.utils.AlitaCallback import AlitaStreamlitCallback
from src.alita_sdk.clients.tools import get_toolkits


def run_streamlit(st, ai_icon=decode_img(ai_icon), user_icon=decode_img(user_icon)):
    
    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.thread_id = None
        
    
    def create_tooklit_schema(tkit_schema):
        schema = {}
        for key, value in tkit_schema.get('properties', {}).items():
            if value.get('autopopulate'):
                continue
            schema[key] = value
        return schema
    
    st.set_page_config(
        page_title='Alita Assistants', 
        page_icon = ai_icon, 
        layout = 'wide', 
        initial_sidebar_state = 'auto',
        menu_items={
            "Get help" : "https://elitea.ai",
            "About": "https://elitea.ai/docs"
        }
    )
    
    if not(st.session_state.tooklit_configs and len(st.session_state.tooklit_configs) > 0):
        for tkit_pd in get_toolkits():
            ktit_sch = tkit_pd.schema()
            st.session_state.tooklit_configs.append(ktit_sch)
            st.session_state.tooklit_names.append(ktit_sch['title'])
    
    st.markdown(
        r"""
        <style>
        [data-testid="stStatusWidget"] { display: none; }
        .stDeployButton { display: none; }
        section[data-testid="stSidebarContent"] { width: 400px !important; }
        </style>
        """, unsafe_allow_html=True
    )
    
    with st.sidebar:
        clear_chat = st.button("Clear Chat")
        if clear_chat:
            clear_chat_history()

        llmconfig, agentconfig = st.tabs(["Alita Settings", "Local Runtime"])
        with llmconfig:
            st.title("Elitea Login Form")
            deployment_value = environ.get('DEPLOYMENT_URL', None)
            deployment_secret = environ.get('XSECRET', 'secret')
            api_key_value = environ.get('API_KEY', None)
            project_id_value = int(environ.get('PROJECT_ID', None))
            if st.session_state.llm:
                deployment_value = st.session_state.llm.deployment
                api_key_value = st.session_state.llm.api_token
                project_id_value = st.session_state.llm.project_id
            ## Alita authentication
            with st.form("settings_form", clear_on_submit=False):
                deployment = st.text_input("Deployment URL", placeholder="Enter Deployment URL", value=deployment_value)
                api_key = st.text_input("API Key", placeholder="Enter API Key", value=api_key_value, type="password")
                project_id = st.number_input("Project ID", format="%d", min_value=1, value=project_id_value, placeholder="Enter Project ID")
                deployment_secret = st.text_input("Deployment Secret", placeholder="Enter Deployment Secret", value=deployment_secret)
                submitted = st.form_submit_button("Login")
                if submitted:
                    with st.spinner("Logging to Alita..."):
                        try:
                            st.session_state.llm = AlitaChatModel(**{
                                    "deployment": deployment,
                                    "api_key": api_key,
                                    "project_id": project_id,
                                })
                            client = st.session_state.llm.client
                            integrations = client.all_models_and_integrations()
                            unique_models = set()
                            models_list = []
                            for entry in integrations:
                                models = entry.get('settings', {}).get('models', [])
                                for model in models:
                                    if model.get('capabilities', {}).get('chat_completion') and model['name'] not in unique_models:
                                        unique_models.add(model['name'])
                                        models_list.append({model['name']: entry['uid']})
                            st.session_state.agents = client.get_list_of_apps()
                            st.session_state.models = models_list
                            clear_chat_history()
                        except Exception as e:
                            st.session_state.agents = None
                            st.session_state.models = None
                            st.session_state.llm = None
                            st.error(f"Error loggin to ELITEA ")
                        
            if st.session_state.llm:
                st.title("Available Agents")
                st.write("This one will load latest version of agent")
                with st.form("agents_form", clear_on_submit=False):
                    options = st.selectbox("Select an agent to load", (agent['name'] for agent in st.session_state.agents))
                    agent_version_name = st.text_input("Agent Version Name", value='latest', placeholder="Enter Version ID")
                    agent_type = st.selectbox("Agent Type (leave brank for default)", [""] + agent_types)
                    submitted = st.form_submit_button("Load Agent")
                    if submitted:
                        with st.spinner("Loading Agent..."):
                            agent = next((a for a in st.session_state.agents if a['name'] == options), None)
                            if agent:
                                agent_id = agent['id']
                                agent_details = st.session_state.llm.client.get_app_details(agent_id)
                                latest_version = next((v for v in agent_details['versions'] if v['name'] == agent_version_name), None)
                                if latest_version:
                                    agent_version_id = latest_version['id']
                                    st.session_state.agent_executor = st.session_state.llm.client.application(
                                        st.session_state.llm, agent_id, agent_version_id,
                                        agent_type if agent_type else None)
                                    st.session_state.agent_name = options
                                    clear_chat_history()
                                else:
                                    st.session_state.agent_executor = None
                                    st.session_state.agent_name = "Load agent using config"
                                    clear_chat_history()
                                    st.error("Agent version not found")
                            
        with agentconfig:
            st.title("Local Agent")
            with st.form("add_tkit", clear_on_submit=False):
                options = st.selectbox("Add toolkit", st.session_state.tooklit_names)
                submitted = st.form_submit_button("Add Toolkit")
                if submitted:
                    pass
            
            with st.form("agent_config", clear_on_submit=False):
                
                context = st.text_area("Context", placeholder="Enter Context")
                tools = st.text_area("Tools", placeholder="Enter Tools in JSON format")
                submitted = st.form_submit_button("Submit")
                if submitted:
                    pass
    if st.session_state.llm and st.session_state.agent_executor:
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar=ai_icon if message["role"] == "assistant" else user_icon):
                st.markdown(message["content"])
        try:
            st.title(st.session_state.agent_name)
        except:
            st.title("Login to ELITEA and load your agent")
        if prompt := st.chat_input():
            st.chat_message("user", avatar=user_icon).write(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("assistant", avatar=ai_icon):
                st_cb = AlitaStreamlitCallback(st)
                response = st.session_state.agent_executor.invoke(
                    {"input": prompt, "chat_history": st.session_state.messages}, 
                    { 'callbacks': [st_cb], 'configurable': {"thread_id": st.session_state.thread_id}}
                )
                st.write(response["output"])
                st.session_state.thread_id = response.get("thread_id", None)
                st.session_state.messages.append({"role": "assistant", "content": response["output"]})
    else:
        st.title("Please Load an Agent to Start Chatting")    

