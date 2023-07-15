import os
import openai
import streamlit as st
import time
from dotenv import load_dotenv
from render import bot_msg_container_html_template, user_msg_container_html_template
from utils import semantic_search
import prompts
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import random
from transformers import GPT2TokenizerFast

tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

load_dotenv()

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

if authentication_status:
    authenticator.logout('Logout', 'main', key='unique_key')
    st.write(f'Welcome *{name}*')
    st.title('Your personal dating coach')

    # Construct messages from chat history
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

    # Generate response to user prompt
    def generate_response():
        global message_count, last_reset_time

        # Check if the rate limit has been reached
        current_time = time.time()
        elapsed_time = current_time - last_reset_time

        if elapsed_time > 3600:
            # Reset the message count and update the reset time
            message_count = 0
            last_reset_time = current_time

        if st.session_state.message_count >= 1:
            # Display an error message to the user
            st.error(f"Message limit exceeded. You can only send 2 messages per hour.")
            st.stop()
            
            return

        # Increment the message count
        message_count += 1

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

    st.text_input("Enter your prompt:",
                  key="prompt",
                  placeholder="e.g. 'Give me advice on texting in online dating",
                  on_change=generate_response
                  )

    st.markdown('<div id="bottom"></div>', unsafe_allow_html=True)

elif authentication_status is False:
    st.error('Username/password is incorrect')
elif authentication_status is None:
    st.warning('Please enter your username and password')
