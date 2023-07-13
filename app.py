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
from transformers import GPT2TokenizerFast

tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

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

if authentication_status:
    authenticator.logout('Logout', 'main', key='unique_key')
    st.write(f'Welcome *{name}*')
    st.title('Your personal dating coach')

    # Construct messages from chat history
    # def construct_messages(history): # old ottley version 
    #     messages = [{"role": "system", "content": prompts.system_message}] # old ottley version seems to give the prompt twice - let's try with it empty
    #     #messages = [{"role": "system", "content": "Intentionally left blank"}]
    #     for entry in history:
    #         role = "user" if entry["is_user"] else "assistant"
    #         print("This is the message in the history", entry["message"])
    #         messages.append({"role": role, "content": entry["message"]})
        
    #     return messages

    def construct_messages(history): # this version only takes the latest 500 tokens of history of the convo
        messages = [{"role": "system", "content": prompts.system_message}]
        tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        cumulative_token_count = 0

        for entry in history[::-1]:  # Reverse the history to start from the latest message
            role = "user" if entry["is_user"] else "assistant"
            tokens = tokenizer.encode(entry["message"], add_special_tokens=False)
            token_count = len(tokens)
            # the prompt is around 742 which doesnt include
            # at 2000 tokens for the messages below, have 1500-742 to play with
            if cumulative_token_count + token_count > 700: #higher tokens means longer memory
                # Skip appending messages that exceed the token limit
                break

            cumulative_token_count += token_count
            messages.append({"role": role, "content": entry["message"]})

        return messages[::-1]  # Reverse the messages to maintain the original order




    # Generate response to user prompt
    def generate_response():
        st.session_state.history.append({
            "message": st.session_state.prompt,
            "is_user": True
        })

        # Perform semantic search and format results
        top_k = 8  # how many of the top results we want
        non_random_snip = 1  # how many snippets will be non-random. so i.e., 1 = means the top 1 will always be sent to GPT. Typically, at the moment GPT is only getting 2 snippets due to the cutoff of 4096 tokens.
        search_results = semantic_search(st.session_state.prompt, top_k=top_k)
        context = ""
        selected_indices = list(range(len(search_results)))  # Create a list of indices
        random.shuffle(selected_indices)  # Randomly shuffle the indices

        # Find the indices of search results with title "Full course"
        full_course_indices = [i for i, (_, title) in enumerate(search_results) if title == "zzzFull Dating Course"] # change this to "Full Dating Course" to give pref to the pdf

        if full_course_indices:
            # Sort the full course indices in descending order based on their search result rankings
            full_course_indices = sorted(full_course_indices, key=lambda i: selected_indices.index(i), reverse=True)
            full_course_index = full_course_indices[0]  # Take the highest-ranked full course search result
            selected_indices.remove(full_course_index)  # Remove the full course search result index from selected_indices

            # Add the full course search result to the context string first
            transcript, title = search_results[full_course_index]
            context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        # Get the top non-random_snip-1 results
        top_results = selected_indices[:non_random_snip-1]
        remaining_results = selected_indices[non_random_snip-1:]

        for i in top_results:
            transcript, title = search_results[i]
            context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        # Shuffle the remaining results
        random.shuffle(remaining_results)

        for i in remaining_results:
            transcript, title = search_results[i]
            context += f"\n Snippet from:\n Video title: {title}\n Snippet: {transcript}\n\n"

        # Generate human prompt template and convert to API message format
        query = st.session_state.prompt
        query_with_context = prompts.human_template.format(query=query, context=context)
        
        max_context_length = 2500
        context_tokens = tokenizer.tokenize(query_with_context)
        if len(context_tokens) > max_context_length:
            context_tokens = context_tokens[:max_context_length]
            query_with_context_limited = tokenizer.convert_tokens_to_string(context_tokens)
        else: 
            query_with_context_limited = query_with_context

               
        
        print("here's the whole query: ", query_with_context_limited.encode('utf-8'))
        print("here's the length of the whole query: ", len(tokenizer.tokenize(query_with_context_limited)))
        # Convert chat history to a list of messages
        messages = construct_messages(st.session_state.history)
        
        cumcount = 0 
        for msg in messages:
            msg_tokens = tokenizer.tokenize(msg["content"])
            cumcount += len(msg_tokens)
            print("This is the count of the number of tokens", cumcount)
            content = msg["content"]
            print("this is a message:", content.encode('utf-8'))


        messages.append({"role": "user", "content": query_with_context_limited})

        # Run the LLMChain
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
        for msg in messages:
            content = msg["content"]
            print("after recent append: this is a message:", content.encode('utf-8'))


        # Parse response
        bot_response = response["choices"][0]["message"]["content"]
        st.session_state.history.append({
            "message": bot_response,
            "is_user": False
        })

    # Display chat history
    for message in st.session_state.history:
        if message["is_user"]:
            st.write(user_msg_container_html_template.replace("$MSG", message["message"]), unsafe_allow_html=True)
        else:
            st.write(bot_msg_container_html_template.replace("$MSG", message["message"]), unsafe_allow_html=True)



    # User input prompt
    st.text_input("Enter your prompt:",
                  key="prompt",
                  placeholder="e.g. 'Give me advice on texting in online dating",
                  on_change=generate_response
                  )

    # Anchor point for scrolling to the bottom
    st.markdown('<div id="bottom"></div>', unsafe_allow_html=True)

elif authentication_status is False:
    st.error('Username/password is incorrect')
elif authentication_status is None:
    st.warning('Please enter your username and password')
