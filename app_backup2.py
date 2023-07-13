import os
import openai
import streamlit as st
from dotenv import load_dotenv
from render import bot_msg_container_html_template, user_msg_container_html_template
from utils import semantic_search
import prompts
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)
    
    
authenticator = stauth.Authenticate(
config['credentials'],
config['cookie']['name'],
config['cookie']['key'],
config['cookie']['expiry_days'],
config['preauthorized']
)

# st.session_state["name"] = None
# st.session_state["authentication_status"] = None
# st.session_state["username"] = None


name, authentication_status, username = authenticator.login('Login', 'main')



if authentication_status:
    authenticator.logout('Logout', 'main')
    st.write(f'Welcome *{name}*')
    load_dotenv()

    # Set up OpenAI API key
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.header("pwfGPT - By Ryan Pollard")

    # Define chat history storage
    if "history" not in st.session_state:
        st.session_state.history = []

    # Construct messages from chat history
    def construct_messages(history):
        messages = [{"role": "system", "content": prompts.system_message}]
        
        for entry in history:
            role = "user" if entry["is_user"] else "assistant"
            messages.append({"role": role, "content": entry["message"]})
        
        return messages

    # Generate response to user prompt
    def generate_response():
        st.session_state.history.append({
            "message": st.session_state.prompt,
            "is_user": True
        })

        # Perform semantic search and format results
        search_results = semantic_search(st.session_state.prompt, top_k=4)
        context = ""
        for i, (title, transcript) in enumerate(search_results):
            context += f"Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        # Generate human prompt template and convert to API message format
        query_with_context = prompts.human_template.format(query=st.session_state.prompt, context=context)

        # Convert chat history to a list of messages
        messages = construct_messages(st.session_state.history)
        messages.append({"role": "user", "content": query_with_context})

        # Run the LLMChain
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
        print(messages)

        # Parse response
        bot_response = response["choices"][0]["message"]["content"]
        st.session_state.history.append({
            "message": bot_response,
            "is_user": False
        })

    # User input prompt
    user_prompt = st.text_input("Enter your prompt:",
                                key="prompt",
                                placeholder="e.g. 'Give me advice on texting in online dating",
                                on_change=generate_response
                                )

    # Display chat history
    for message in st.session_state.history:
        if message["is_user"]:
            st.write(user_msg_container_html_template.replace("$MSG", message["message"]), unsafe_allow_html=True)
        else:
            st.write(bot_msg_container_html_template.replace("$MSG", message["message"]), unsafe_allow_html=True)

elif authentication_status == False:
    st.error('Username/password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')