import streamlit as st
import sys
import asyncio
import random
import string
import os
import json
from datetime import datetime 

# used for displaying messages from the agents
from autogen_agentchat.messages import MultiModalMessage, TextMessage, ToolCallExecutionEvent, ToolCallRequestEvent
from autogen_agentchat.base import TaskResult

from dotenv import load_dotenv
load_dotenv()

from magentic_one_helper import MagenticOneHelper
from magentic_one_custom_rag_agent import MAGENTIC_ONE_RAG_DESCRIPTION

#Enable asyncio for Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Initialize a global cancellation event
cancel_event = asyncio.Event()

MAGENTIC_ONE_DEFAULT_AGENTS = [
            {
            "input_key":"0001",
            "type":"MagenticOne",
            "name":"Coder",
            "system_message":"",
            "description":"",
            "icon":"👨‍💻"
            },
            {
            "input_key":"0002",
            "type":"MagenticOne",
            "name":"Executor",
            "system_message":"",
            "description":"",
            "icon":"💻"
            },
            {
            "input_key":"0003",
            "type":"MagenticOne",
            "name":"FileSurfer",
            "system_message":"",
            "description":"",
            "icon":"📂"
            },
            {
            "input_key":"0004",
            "type":"MagenticOne",
            "name":"WebSurfer",
            "system_message":"",
            "description":"",
            "icon":"🏄‍♂️"
            },
            ]

# Initialize session state for instructions
if 'instructions' not in st.session_state:
    st.session_state['instructions'] = ""
if 'running' not in st.session_state:
    st.session_state['running'] = False
if "final_answer" not in st.session_state:
    st.session_state["final_answer"] = None
if "stop_reason" not in st.session_state:
    st.session_state["stop_reason"] = None
if "run_mode_locally" not in st.session_state:
    st.session_state["run_mode_locally"] = True


if 'saved_agents' not in st.session_state:
    st.session_state.saved_agents = MAGENTIC_ONE_DEFAULT_AGENTS


if 'max_rounds' not in st.session_state:
    st.session_state.max_rounds = 30
if 'max_time' not in st.session_state:
    st.session_state.max_time = 25
if 'max_stalls_before_replan' not in st.session_state:
    st.session_state.max_stalls_before_replan = 5
if 'return_final_answer' not in st.session_state:
    st.session_state.return_final_answer = True
if 'start_page' not in st.session_state:
    st.session_state.start_page = "https://www.bing.com"
if 'save_screenshots' not in st.session_state:
    st.session_state.save_screenshots = True

if 'session_id' not in st.session_state:
    st.session_state.session_id = None

if 'planned' not in st.session_state:
    st.session_state.planned = False
st.set_page_config(layout="wide")
st.write("### Dream Team powered by AutoGen")


@st.dialog("Add agent")
def add_agent(item = None):
    # st.write(f"Setuup your agent:")
    st.caption("Note: Always use unique name with no spaces. Always fill System message and Description.")
    st.caption('In the system message use as last sentence: Reply "TERMINATE" in the end when everything is done.')
    # agent_type = st.selectbox("Type", ["MagenticOne","Custom"], key=f"type{input_key}", index=0 if agent and agent["type"] == "MagenticOne" else 1, disabled=is_disabled(agent["type"]) if agent else False)
    agent_type = "Custom"
    agent_name = st.text_input("Name", value=None)
    system_message = st.text_area("System Message", value=None)
    description = st.text_area("Description", value=None)
        
    if st.button("Submit"):
        # st.session_state.vote = {"item": item, "reason": reason}
        st.session_state.saved_agents.append({
            "input_key": random.choice(string.ascii_uppercase)+str(random.randint(0,999999)),
            "type": agent_type,
            "name": agent_name,
            "system_message": system_message,
            "description": description,
            "icon": generate_random_agent_emoji()
        })
        st.rerun()

@st.dialog("Add RAG agent")
def add_rag_agent(item = None):
    # st.write(f"Setuup your agent:")
    st.caption("Note: Always use unique name with no spaces.")
    st.caption('Index Name must be your existing index in AI Search service which is filled with data. We expect a structure of index:')
    st.caption('"parent_id", "chunk_id", "chunk","text_vector"')
    st.caption("This structure is default when you ingest and vectorize document directly from Azure AI Search.")
    
    # agent_type = st.selectbox("Type", ["MagenticOne","Custom"], key=f"type{input_key}", index=0 if agent and agent["type"] == "MagenticOne" else 1, disabled=is_disabled(agent["type"]) if agent else False)
    agent_type = "RAG"
    agent_name = st.text_input("Name", value="RAGAgent")
    # system_message = st.text_area("System Message", value=None)
    # description = st.text_area("Description", value=MAGENTIC_ONE_RAG_DESCRIPTION)
    # TODO remove
    description = st.text_area("Description", value="An agent that has access to a knowledge base of International Energy Agency (IEA) Analysis and forecast to 2030 and OPEC Monthly Oil Market Report as of January 2025 and can handle RAG tasks, call this agent if you are getting questions on your knowledge base")

    index_name = st.text_input("Index Name", value="vector-autogen-rag")
        
    if st.button("Submit"):
        # st.session_state.vote = {"item": item, "reason": reason}
        st.session_state.saved_agents.append({
            "input_key": random.choice(string.ascii_uppercase)+str(random.randint(0,999999)),
            "type": agent_type,
            "name": agent_name,
            # "system_message": system_message,
            "description": description,
            
            "icon": "🔍",
            "index_name": index_name
        })
        st.rerun()


@st.dialog("Edit agent")
def edit_agent(input_key = None):
    agent = next((i for i in st.session_state.saved_agents if i["input_key"] == input_key), None)
    # st.write(f"Setuup your agent:")
    st.caption("Note: Always use unique name with no spaces. Always fill System message and Description.")
    # agent_type = st.selectbox("Type", ["MagenticOne","Custom"], key=f"type{input_key}", index=0 if agent and agent["type"] == "MagenticOne" else 1, disabled=is_disabled(agent["type"]) if agent else False)
    # agent_type = "Custom"
    # agent_name = st.text_input("Name", value=None)
    # system_message = st.text_area("System Message", value=None)
    # description = st.text_area("Description", value=None)
    if agent["type"] == "MagenticOne":
        disabled = True
        st.info("MagenticOne agents cannot be edited. Only deleted.")
    else:
        disabled = False
    agent_type = "Custom"
    agent_name = st.text_input("Name", key=f"name{input_key}", value=agent["name"] if agent else None, disabled=disabled)
    system_message = st.text_area("System Message", key=f"sys{input_key}", value=agent["system_message"] if agent else None, disabled=disabled)
    description = st.text_area("Description", key=f"desc{input_key}", value=agent["description"] if agent else None, disabled=disabled)

        
    if st.button("Submit", disabled=disabled):
        agent["name"] = agent_name
        agent["system_message"] = system_message
        agent["description"] = description
        st.rerun()
    
    if st.button("Delete", key=f'delete{agent["input_key"]}', type="primary"):
        st.session_state.saved_agents = [i for i in st.session_state.saved_agents if i["input_key"] != input_key]
        st.rerun()


@st.dialog("Delete agent")
def delete_agent(input_key = None):
    # find the agent by input_key
    agent = next((i for i in st.session_state.saved_agents if i["input_key"] == input_key), None)
    if agent:
        st.write(f"Are you sure you want to remove: {agent['icon']} {agent['name']}?")
        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("Cancel"):
                st.rerun()
        with col2:
            if st.button("Delete", type="primary"):
                st.session_state.saved_agents = [i for i in st.session_state.saved_agents if i["input_key"] != input_key]
                st.rerun()
    

image_path = "contoso.png"  
  
# Display the image in the sidebar  
with st.sidebar:
    st.image(image_path, use_container_width=True) 
    st.caption("v0.4.0.b4")

    with st.expander("Settings", expanded=False):
        # st.caption("Settings:")
        st.session_state.max_rounds = st.number_input("Max Rounds", min_value=1, value=100)
        st.session_state.max_time = st.number_input("Max Time (Minutes)", min_value=1, value=30)
        st.session_state.max_stalls_before_replan = st.number_input("Max Stalls Before Replan", min_value=1, max_value=10, value=5)
        st.session_state.return_final_answer = st.checkbox("Return Final Answer", value=True)

        st.session_state.start_page = st.text_input("Start Page URL", value="https://www.bing.com")
    
    # if st.session_state.session_id:
    with st.container(border=True):
    #     st.caption("Plan:")
        SESSION_INFO = st.empty()
        PLAN_PLACE = st.empty()
            
        
def generate_random_agent_emoji() -> str:
    emoji_list = ["🤖", "🔄", "😊", "🚀", "🌟", "🔥", "💡", "🎉", "👍"]
    return random.choice(emoji_list)


run_button_text = "Run Agents"
if not st.session_state['running']:


    with st.expander("Agents configuration", expanded=True):
        st.caption("You can configure your agents here.")
        agents = st.session_state.saved_agents
        # st.write(agents)
        # create st.columns for each agent
        cols = st.columns(len(agents))
        for col, agent in zip(cols, agents):

            with col:
                with st.container(border=True):
                    st.write(agent["icon"]) 
                    st.write(agent["name"])
                    st.caption(agent["type"])
                    # st.caption(agent["description"])
                    # if st.button("❌", key=f'delete{agent["input_key"]}'):
                    #     delete_agent(agent["input_key"])
                    if st.button("✏️", key=f'edit{agent["input_key"]}'):
                        edit_agent(agent["input_key"])

        # with cols[-1]:
        col1, col2, col3 = st.columns([3,1,1])
        with col1:
            if st.button("Restore MagenticOne agents", icon="🔄"):
                st.session_state.saved_agents = MAGENTIC_ONE_DEFAULT_AGENTS
                st.rerun()
        with col3:
            if st.button("Add Agent", type="primary", icon="➕"):
                add_agent("A")
            if st.button("Add RAG Agent", type="primary", icon="➕"):
                add_rag_agent("A")
                
    # TODO remove - testing record for RAG
    # Define predefined values
    predefined_values = [
        # "how do I setup my Surface?",
        # "Generate a python script to print and execute Fibonacci series below 1000",
        "Act as a multi-agent system that harnesses advanced financial modeling, scenario analysis, geopolitical forecasting, and risk quantification to produce a comprehensive, data-driven assessment of current market forecasts, commodity price trends, and OPEC announcements. In this process, identify and deeply evaluate the relative growth potential of various upstream investment areas—ranging from unconventional reservoirs to deepwater projects and advanced EOR techniques—across Africa, the Middle East, and Central Europe. Based on publicly available data (e.g., IEA, EIA, and OPEC bulletins), synthesize your findings into specific, country-level recommendations that incorporate ROI calculations, scenario-based risk assessments, and robust justifications reflecting both market and geopolitical considerations. Present the final deliverable as a well-structured table, demonstrating the rigor and depth of an analytical team’s extended research, including key assumptions, financial metrics, and any pivotal policy or infrastructural factors relevant to strategic decision-making.",
        "Find me a French restaurant in Dubai with 2 Michelin stars?",
        "When and where is the next game of Arsenal, print a link for purchase",
        "Based on your knowledge base how many taxes Elon Musk paid?",
        "Generate a python script and execute Fibonacci series below 1000",
    ]

    # Add an option for custom input
    custom_option = "Write your own query"

    # Use selectbox for predefined values and custom option
    selected_option = st.selectbox("Select your instructions:", options=predefined_values + [custom_option])

    # If custom option is selected, show text input for custom instructions
    if selected_option == custom_option:
        instructions = st.text_area("Enter your custom instructions:", height=200)
    else:
        instructions = selected_option

    # Update session state with instructions
    st.session_state['instructions'] = instructions
    
    run_mode_locally = st.toggle("Run Locally", value=False)
    if run_mode_locally:
        st.session_state["run_mode_locally"] = True
        st.caption("Run Locally: Run the workflow in a Docker container on your local machine.")
    else:
        st.caption("Run in Azure: Run the workflow in a ACA Dynamic Sessions on Azure.")
        # check if the Azure infra is setup
        _pool_endpoint=os.getenv("POOL_MANAGEMENT_ENDPOINT")
        if not _pool_endpoint:
            st.error("You need to setup the Azure infra first. Try `azd up` in your project.")
            # st.session_state["run_mode_locally"] = True
            # st.rerun()
        st.session_state["run_mode_locally"] = False
else:
    run_button_text = "Cancel Run"



if st.button(run_button_text, type="primary"):
    if not st.session_state['running']:
        st.session_state['instructions'] = instructions
        st.session_state['running'] = True
        st.session_state['final_answer'] = None
        cancel_event.clear()  # Clear the cancellation event
        st.rerun()
    else:
        st.session_state['running'] = False
        st.session_state['instructions'] = ""
        st.session_state['final_answer'] = None
        st.session_state["run_mode_locally"] = True
        st.session_state["session_id"] = None
        st.session_state["planned"] = False
        cancel_event.set()  # Set the cancellation event
        st.rerun()


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def get_agent_icon(agent_name) -> str:
    if agent_name == "MagenticOneOrchestrator":
        agent_icon = "🎻"
    elif agent_name == "WebSurfer":
        agent_icon = "🏄‍♂️"
    elif agent_name == "Coder":
        agent_icon = "👨‍💻"
    elif agent_name == "FileSurfer":
        agent_icon = "📂"
    elif agent_name == "Executor":
        agent_icon = "💻"
    elif agent_name == "user":
        agent_icon = "👤"
    else:
        agent_icon = "🤖"
    return agent_icon

def write_log(path, log_entry):
    # check if the file exists if not create it
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("")
    # append the log entry to a file
    with open(path, "a") as f:
        f.write(f"{json.dumps(log_entry)}\n")

async def summarize_plan(plan, client):
    prompt = "You are a project manager."
    text = f"""Summarize the plan for each agent into single-level only bullet points.

    Plan:
    {plan}
    """
    
    from autogen_core.models import UserMessage, SystemMessage
    messages = [
        UserMessage(content=text, source="user"),
        SystemMessage(content=prompt)
    ]
    result = await client.create(messages)
    # print(result.content)
    
    plan_summary = result.content
    return plan_summary
async def display_log_message(log_entry, logs_dir, session_id, client = None):     
    # _log_entry_json  = json.loads(log_entry)
    _log_entry_json  = log_entry

    log_file_name = f"{session_id}.log"
    log_path = os.path.join(logs_dir,log_file_name)
    log_message_json = {
        "time": get_current_time(),
        "type": None,
        "source": None,
        "content": None,
        "stop_reason": None,
        "models_usage": None,
    }


    # check if the message is a TaskResult class
    if isinstance(_log_entry_json, TaskResult):
        # st.write("TaskResult")
        # it is TaskResult class wth messages (list of all messages) and stop_reason
        # display last message
        _type = "TaskResult"
        _source = "TaskResult"
        _content = _log_entry_json.messages[-1]
        _stop_reason = _log_entry_json.stop_reason
        _timestamp = get_current_time()
        icon_result = "🎯"
        # do not display the final answer just yet, only set it in the session state
        st.session_state["final_answer"] = _content.content
        st.session_state["stop_reason"] = _stop_reason

        log_message_json["type"] = _type
        log_message_json["source"] = _source
        log_message_json["content"] = _content.content
        log_message_json["stop_reason"] = _stop_reason


    elif isinstance(_log_entry_json, MultiModalMessage):
        # message type, e.g.: TextMessage,'MultiModalMessage'
        _type = _log_entry_json.type
        # source of the message, e.g.: user, MagenticOneOrchestrator,'WebSurfer','Coder'
        _source = _log_entry_json.source
        # actual message content - if multimodal it will be list of contents, one of them is autogen_core._image.Image object where data_uri is base64 encoded image, image is PIL image
        _content = _log_entry_json.content
        _timestamp = get_current_time()

        agent_icon = get_agent_icon(_source)
        with st.expander(f"{agent_icon} {_source} @ {_timestamp}", expanded=False):
            st.write("Message:")
            st.write(_content[0])
            st.image(_content[1].image)
        
        log_message_json["type"] = _type
        log_message_json["source"] = _source
        log_message_json["content"] = _content[0]


    elif isinstance(_log_entry_json, TextMessage):
        # message type, e.g.: TextMessage,'MultiModalMessage'
        _type = _log_entry_json.type
        # source of the message, e.g.: user, MagenticOneOrchestrator,'WebSurfer','Coder'
        _source = _log_entry_json.source
        # actual message content - if multimodal it will be list of contents, one of them is autogen_core._image.Image object where data_uri is base64 encoded image, image is PIL image
        _content = _log_entry_json.content
        _timestamp = get_current_time()

        agent_icon = get_agent_icon(_source)
        if (_source == "MagenticOneOrchestrator" and not st.session_state["planned"]):
            plan_summary = await summarize_plan(_content, client)
            SESSION_INFO.write(f"Session ID: `{st.session_state.session_id}`")
            PLAN_PLACE.write(plan_summary)
            st.session_state["planned"] = True
        with st.expander(f"{agent_icon} {_source} @ {_timestamp}", expanded=False):
            st.write("Message:")
            st.write(_content)

        log_message_json["type"] = _type
        log_message_json["source"] = _source
        log_message_json["content"] = _content

    elif isinstance(_log_entry_json, ToolCallExecutionEvent):
        # message type, ToolCallRequestEvent, ToolCallExecutionEvent
        _type = _log_entry_json.type
        # source of the message, e.g.: user, MagenticOneOrchestrator,'WebSurfer','Coder'
        _source = _log_entry_json.source
        # actual message content - if multimodal it will be list of contents, one of them is autogen_core._image.Image object where data_uri is base64 encoded image, image is PIL image
        _content = _log_entry_json.content
        _timestamp = get_current_time()

        agent_icon = get_agent_icon(_source)
        with st.expander(f"{agent_icon} {_source} @ {_timestamp}", expanded=False):
            st.write("Message:")
            st.write(_content)
        
        log_message_json["type"] = _type
        log_message_json["source"] = _source
        log_message_json["content"] = _content[0].content

    
    elif isinstance(_log_entry_json, ToolCallRequestEvent):
        # message type, ToolCallRequestEvent, ToolCallExecutionEvent
        _type = _log_entry_json.type
        # source of the message, e.g.: user, MagenticOneOrchestrator,'WebSurfer','Coder'
        _source = _log_entry_json.source
        # actual message content - if multimodal it will be list of contents, one of them is autogen_core._image.Image object where data_uri is base64 encoded image, image is PIL image
        _content = _log_entry_json.content
        _timestamp = get_current_time()
        _models_usage = _log_entry_json.models_usage

        agent_icon = get_agent_icon(_source)
        with st.expander(f"{agent_icon} {_source} @ {_timestamp}", expanded=True):
            st.write("Message:")
            st.write(_content)

        log_message_json["type"] = _type
        log_message_json["source"] = _source
        log_message_json["content"] = _content[0].arguments
        # log_message_json["models_usage"] = _models_usage

    else:
        st.caption("🤔 Agents mumbling...")

        log_message_json["type"] = "N/A"
        log_message_json["content"] = "Agents mumbling."
    
    write_log(log_path, log_message_json)

async def main(task, logs_dir="./logs"):
    
    # create folder for logs if not exists
    if not os.path.exists(logs_dir):    
        os.makedirs(logs_dir)


    # Initialize the MagenticOne system
    magentic_one = MagenticOneHelper(logs_dir=logs_dir, save_screenshots=st.session_state.save_screenshots, run_locally=st.session_state["run_mode_locally"])
    await magentic_one.initialize(agents=st.session_state.saved_agents)
    st.session_state.session_id = magentic_one.session_id

    stream = magentic_one.main(task = task)
   
    with st.container(border=True):    
        # Stream and process logs
        async for log_entry in stream:
            await display_log_message(log_entry=log_entry, logs_dir=logs_dir, session_id=magentic_one.session_id, client=magentic_one.client)



if st.session_state['running']:
    assert st.session_state['instructions'] != "", "Instructions can't be empty."

    if not st.session_state["final_answer"]:
        with st.spinner("Dream Team is running..."):
            asyncio.run(main(st.session_state['instructions']))

    final_answer = st.session_state["final_answer"]
    if final_answer:
        st.success("Task completed successfully.")
        st.write("## Final answer:")
        st.write(final_answer)
        st.write("## Stop reason:")
        st.write(st.session_state["stop_reason"])
        session_id = st.session_state.session_id
        final_report_path = f"./logs/{session_id}.log"
        st.write(f"Final report is saved at: {final_report_path}")
        # download button to download the final report
        with open(final_report_path, "r") as file:
            st.download_button(
                label="Download Final Report",
                data=file,
                file_name=f"{session_id}.log",
                mime="text/plain",
            )
        cancel_event.set()  # Set the cancellation event
    else:
        st.error("Task failed.")
        st.write("Final answer not found.")
