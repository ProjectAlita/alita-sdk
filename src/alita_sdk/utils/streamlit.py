
def run_streamlit(st, agent_executor, ai_icon='🤖', user_icon='🦖'):
    from langchain_community.callbacks.streamlit import (
        StreamlitCallbackHandler,
    )
    st.set_page_config(
        page_title='Alita Assistant', 
        page_icon = ai_icon, 
        layout = 'wide', 
        initial_sidebar_state = 'auto',
        menu_items={
            "Get help" : "https://projectalita.ai",
            "About": "https://alita.lab.epam.com"
        }
    )
    st_callback = StreamlitCallbackHandler(st.container())

    st.markdown(
        r"""
        <style>
        [data-testid="stStatusWidget"] { display: none; }
        .stDeployButton { display: none; }
        </style>
        """, unsafe_allow_html=True
    )
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        st.session_state["agent_executor"] = agent_executor
        
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=ai_icon if message["role"] == "assistant" else user_icon):
            st.markdown(message["content"])


    if prompt := st.chat_input():
        st.chat_message("user", avatar=user_icon).write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant", avatar=ai_icon):
            st_callback = StreamlitCallbackHandler(st.container())
            response = st.session_state.agent_executor.invoke(
                {"content": prompt, "chat_history": st.session_state.messages}, {"callbacks": [st_callback]}
            )
            st.write(response["output"])
            
            st.session_state.messages.append({"role": "assistant", "content": response["output"]})
