import os
import openai
import streamlit as st
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from render import bot_msg_container_html_template, user_msg_container_html_template
from utils import semantic_search
import prompts
import yaml
import streamlit_authenticator as stauth
import random
from transformers import GPT2TokenizerFast
from yaml.loader import SafeLoader
import json



tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

load_dotenv()
message_quota = 1
time_quota = 60 # in seconds
time_quota_minutes = int(round(time_quota / 60))
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)


# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

st.markdown(
    """
    <h1 style="text-align: center;">ChadTDC - Your Personal Date Coach</h1>
    """,
    unsafe_allow_html=True
)

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

if authentication_status is not None and authentication_status:
    authenticator.logout('Logout', 'main', key='unique_key')
    st.title(f'Welcome *{name}*')
    import streamlit as st


    st.markdown(
        """
        ChadTDC, The Date Coach,  is a GPT based chatbot, trained on thousands of hours of advice that various successful dating coaches have given to their clients - helping them getting the results they want. 
        This can be used to seek advice about online dating, real-life dating and relationships.

        It serves as your own personal date/relationship coach.
        """,
        unsafe_allow_html=True
    )


    quota_text = f"Quota: {message_quota} messages every {time_quota_minutes} minutes"
    st.write(quota_text)

    # Load or initialize the data from data.json
    if os.path.exists("data.json"):
        with open("data.json", "r") as file:
            data = json.load(file)
    else:
        data = {
            "users": {}
        }

    if "warning_message" not in st.session_state:
        st.session_state.warning_message = False

    def get_user_data(username):
        if username not in data["users"]:
            data["users"][username] = {
                "message_count": 0,
                "last_reset_time": time.time()
            }
        return data["users"][username]

    def update_data():
        with open("data.json", "w") as file:
            json.dump(data, file)

    # Set the user's message count and last reset time
    user_data = get_user_data(username)
    message_count = user_data["message_count"]
    last_reset_time = user_data["last_reset_time"]

    # Check if an hour has passed since the last reset time
    elapsed_time = time.time() - last_reset_time
    time_left = time_quota - elapsed_time
    minutes, seconds = divmod(time_left, 60)
    minutes = int(minutes)
    seconds = int(seconds)
    print("this is the elapsed time: ", elapsed_time)
    if elapsed_time >= time_quota:
        message_count = 0
        last_reset_time = time.time()
        user_data["message_count"] = message_count
        user_data["last_reset_time"] = last_reset_time
        update_data()
        st.session_state.warning_message = False

    print("This is the message_count: ", message_count)
    def construct_messages(history):
        messages = [{"role": "system", "content": prompts.system_message}]
        tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        cumulative_token_count = 0

        for entry in history[::-1]:
            role = "user" if entry["is_user"] else "assistant"
            tokens = tokenizer.encode(entry["message"], add_special_tokens=False)
            token_count = len(tokens)

            if cumulative_token_count + token_count > 700:
                break

            cumulative_token_count += token_count
            messages.append({"role": role, "content": entry["message"]})

        return messages[::-1]

    def generate_response():
        if user_data["message_count"] >= message_quota:
            st.session_state.warning_message = True
            return

        user_data["message_count"] += 1
        update_data()

        st.session_state.history.append({
            "message": st.session_state.prompt,
            "is_user": True
        })

        # Perform semantic search and format results
        top_k = 8
        non_random_snip = 1
        search_results = semantic_search(st.session_state.prompt, top_k=top_k)
        context = ""
        selected_indices = list(range(len(search_results)))
        random.shuffle(selected_indices)

        full_course_indices = [i for i, (_, title) in enumerate(search_results) if title == "zzzFull Dating Course"]

        if full_course_indices:
            full_course_indices = sorted(full_course_indices, key=lambda i: selected_indices.index(i), reverse=True)
            full_course_index = full_course_indices[0]
            selected_indices.remove(full_course_index)

            transcript, title = search_results[full_course_index]
            context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        top_results = selected_indices[:non_random_snip-1]
        remaining_results = selected_indices[non_random_snip-1:]

        for i in top_results:
            transcript, title = search_results[i]
            context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        random.shuffle(remaining_results)

        for i in remaining_results:
            transcript, title = search_results[i]
            context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        query = st.session_state.prompt
        query_with_context = prompts.human_template.format(query=query, context=context)

        max_context_length = 2500
        context_tokens = tokenizer.tokenize(query_with_context)

        if len(context_tokens) > max_context_length:
            context_tokens = context_tokens[:max_context_length]
            query_with_context_limited = tokenizer.convert_tokens_to_string(context_tokens)
        else:
            query_with_context_limited = query_with_context

        messages = construct_messages(st.session_state.history)

        cumcount = 0
        for msg in messages:
            msg_tokens = tokenizer.tokenize(msg["content"])
            cumcount += len(msg_tokens)
            content = msg["content"]
            print("This is the count of the number of tokens", cumcount)
            print("this is a message:", content.encode('utf-8'))

        messages.append({"role": "user", "content": query_with_context_limited})

        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)

        for msg in messages:
            content = msg["content"]
            print("after recent append: this is a message:", content.encode('utf-8'))

        bot_response = response["choices"][0]["message"]["content"]
        st.session_state.history.append({
            "message": bot_response,
            "is_user": False
        })

    for message in st.session_state.history:
        if message["is_user"]:
            st.write(user_msg_container_html_template.replace("$MSG", message["message"]), unsafe_allow_html=True)
        else:
            st.write(bot_msg_container_html_template.replace("$MSG", message["message"]), unsafe_allow_html=True)

    if st.session_state.warning_message:
        st.error(f"Your message limit of {message_quota} messages per hour has been reached. Please wait {minutes} minute{'s' if minutes != 1 else ''} and {seconds} second{'s' if seconds != 1 else ''} for the message limit to reset and try again")

    st.text_input(
        "Send a message:",
        key="prompt",
        placeholder="e.g. 'Give me advice on texting on online dating apps'",
        on_change=generate_response,
        disabled=user_data["message_count"] >= message_quota + 1  # Disable input field when message limit is exceeded
    )

    st.markdown('<div id="bottom"></div>', unsafe_allow_html=True)

    # Hide the links to the widgets
    hide_links = True
elif authentication_status is False:
    st.error('Username/password is incorrect')
    hide_links = False
elif authentication_status is None:
    st.warning('Please enter your username and password')
    hide_links = False
else:
    hide_links = False

# New User Registration Widget
if not hide_links:
    register_user_expander = st.expander("Register new user")
    with register_user_expander:
        try:
            if authenticator.register_user('Register new user', preauthorization=False):
                st.success('User registered successfully. Please use these details to log in.')
                # Set the authentication status and username
                authentication_status = True
                username = authenticator.username
                st.session_state.logged_in = True  # Set the logged_in session state variable to True
                st.session_state.username = username  # Store the username in session state
                st.session_state.history = []  # Clear chat history for the new user
                st.session_state.warning_message = False  # Reset warning message
        except Exception as e:
            st.error(e)

# Update the config file
with open("config.yaml", "w") as file:
    yaml.dump(config, file, default_flow_style=False)
