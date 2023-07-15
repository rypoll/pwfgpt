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
import random

load_dotenv()

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

st.header("pwfGPT - By Ryan Pollard")

# Define chat history storage
if "history" not in st.session_state:
    st.session_state.history = []

# Set up authentication
with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    config["preauthorized"]
)

# Add a login screen
name, authentication_status, username = authenticator.login("Login", "main")

# Check authentication status and display content accordingly
if authentication_status:
    st.success(f"Welcome, {name}!")
    # Display the rest of your app content here after successful login
else:
    st.error("Invalid username or password. Please try again.")

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

    search_results = semantic_search(st.session_state.prompt, top_k=8)
    context = ""
    selected_indices = list(range(len(search_results)))  # Create a list of indices
    random.shuffle(selected_indices)  # Randomly shuffle the indices
    
    for i in selected_indices:
        print("i is: ", i)
        transcript, title = search_results[i]
        context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

    # Generate human prompt template and convert to API message format
    query = st.session_state.prompt
    max_context_length = 4096 - len(prompts.human_template) + len(query)  # Calculate maximum context length
    context = context[:max_context_length]  # Limit the context to maximum length
    query_with_context = prompts.human_template.format(query=query, context=context)
    print("here's the whole query: ", query_with_context)
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
