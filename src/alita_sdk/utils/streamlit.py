
def run_streamlit(agent_executor):
    from langchain_community.callbacks.streamlit import (
        StreamlitCallbackHandler,
    )
    import streamlit as st

    st_callback = StreamlitCallbackHandler(st.container())

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        st.session_state["agent_executor"] = agent_executor
        
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


    if prompt := st.chat_input():
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            st_callback = StreamlitCallbackHandler(st.container())
            response = st.session_state.agent_executor.invoke(
                {"content": prompt, "chat_history": st.session_state.messages}, {"callbacks": [st_callback]}
            )
            st.write(response["output"])
            
            st.session_state.messages.append({"role": "assistant", "content": response["output"]})
