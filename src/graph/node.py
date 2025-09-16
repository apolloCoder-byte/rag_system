import json
import logging
import os
from typing import Annotated, Literal
from loguru import logger

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from src.agents import create_agent
from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
# from src.prompts.planner_model import Plan
from src.prompts.template import apply_prompt_template
# from src.tools import (
#     crawl_tool,
#     get_retriever_tool,
#     get_web_search_tool,
#     python_repl_tool,
# )
# from src.tools.search import LoggedTavilySearch
# from src.utils.json_utils import repair_json_output

# from ..config import SELECTED_SEARCH_ENGINE, SearchEngine
from .types import State
from src.utils.conversation_manager import conversation_manager
from src.schema.redis import MessageRole
from src.services.milvus import milvus_service
from src.utils.embedding import get_text_embeddings


@tool
def handoff_to_planner(
    research_topic: Annotated[str, "The topic of the research task to be handed off."],
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
):
    """Handoff to planner agent to do plan."""
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to hand off to planner agent
    return


def background_investigation_node(state: State, config: RunnableConfig):
    logger.info("background investigation node is running.")
    configurable = Configuration.from_runnable_config(config)
    query = state.get("research_topic")
    background_investigation_results = None
    if SELECTED_SEARCH_ENGINE == SearchEngine.TAVILY.value:
        searched_content = LoggedTavilySearch(
            max_results=configurable.max_search_results
        ).invoke(query)
        # check if the searched_content is a tuple, then we need to unpack it
        if isinstance(searched_content, tuple):
            searched_content = searched_content[0]
        if isinstance(searched_content, list):
            background_investigation_results = [
                f"## {elem['title']}\n\n{elem['content']}" for elem in searched_content
            ]
            return {
                "background_investigation_results": "\n\n".join(
                    background_investigation_results
                )
            }
        else:
            logger.error(
                f"Tavily search returned malformed response: {searched_content}"
            )
    else:
        background_investigation_results = get_web_search_tool(
            configurable.max_search_results
        ).invoke(query)
    return {
        "background_investigation_results": json.dumps(
            background_investigation_results, ensure_ascii=False
        )
    }


def planner_node(
    state: State, config: RunnableConfig
) -> Command[Literal["human_feedback", "reporter"]]:
    """Planner node that generate the full plan."""
    logger.info("Planner generating full plan")
    configurable = Configuration.from_runnable_config(config)
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    messages = apply_prompt_template("planner", state, configurable)

    if state.get("enable_background_investigation") and state.get(
        "background_investigation_results"
    ):
        messages += [
            {
                "role": "user",
                "content": (
                    "background investigation results of user query:\n"
                    + state["background_investigation_results"]
                    + "\n"
                ),
            }
        ]

    if configurable.enable_deep_thinking:
        llm = get_llm_by_type("reasoning")
    elif AGENT_LLM_MAP["planner"] == "basic":
        llm = get_llm_by_type("basic").with_structured_output(
            Plan,
            method="json_mode",
        )
    else:
        llm = get_llm_by_type(AGENT_LLM_MAP["planner"])

    # if the plan iterations is greater than the max plan iterations, return the reporter node
    if plan_iterations >= configurable.max_plan_iterations:
        return Command(goto="reporter")

    full_response = ""
    if AGENT_LLM_MAP["planner"] == "basic" and not configurable.enable_deep_thinking:
        response = llm.invoke(messages)
        full_response = response.model_dump_json(indent=4, exclude_none=True)
    else:
        response = llm.stream(messages)
        for chunk in response:
            full_response += chunk.content
    logger.debug(f"Current state messages: {state['messages']}")
    logger.info(f"Planner response: {full_response}")

    try:
        curr_plan = json.loads(repair_json_output(full_response))
    except json.JSONDecodeError:
        logger.warning("Planner response is not a valid JSON")
        if plan_iterations > 0:
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")
    if isinstance(curr_plan, dict) and curr_plan.get("has_enough_context"):
        logger.info("Planner response has enough context.")
        new_plan = Plan.model_validate(curr_plan)
        return Command(
            update={
                "messages": [AIMessage(content=full_response, name="planner")],
                "current_plan": new_plan,
            },
            goto="reporter",
        )
    return Command(
        update={
            "messages": [AIMessage(content=full_response, name="planner")],
            "current_plan": full_response,
        },
        goto="human_feedback",
    )


def human_feedback_node(
    state,
) -> Command[Literal["planner", "research_team", "reporter", "__end__"]]:
    current_plan = state.get("current_plan", "")
    # check if the plan is auto accepted
    auto_accepted_plan = state.get("auto_accepted_plan", False)
    if not auto_accepted_plan:
        feedback = interrupt("Please Review the Plan.")

        # if the feedback is not accepted, return the planner node
        if feedback and str(feedback).upper().startswith("[EDIT_PLAN]"):
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=feedback, name="feedback"),
                    ],
                },
                goto="planner",
            )
        elif feedback and str(feedback).upper().startswith("[ACCEPTED]"):
            logger.info("Plan is accepted by user.")
        else:
            raise TypeError(f"Interrupt value of {feedback} is not supported.")

    # if the plan is accepted, run the following node
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    goto = "research_team"
    try:
        current_plan = repair_json_output(current_plan)
        # increment the plan iterations
        plan_iterations += 1
        # parse the plan
        new_plan = json.loads(current_plan)
    except json.JSONDecodeError:
        logger.warning("Planner response is not a valid JSON")
        if plan_iterations > 1:  # the plan_iterations is increased before this check
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")

    return Command(
        update={
            "current_plan": Plan.model_validate(new_plan),
            "plan_iterations": plan_iterations,
            "locale": new_plan["locale"],
        },
        goto=goto,
    )


def coordinator_node(
    state: State, config: RunnableConfig
) -> Command[Literal["planner", "background_investigator", "__end__"]]:
    """Coordinator node that communicate with customers."""
    logger.info("Coordinator talking.")
    configurable = Configuration.from_runnable_config(config)
    messages = apply_prompt_template("coordinator", state)
    response = (
        get_llm_by_type(AGENT_LLM_MAP["coordinator"])
        .bind_tools([handoff_to_planner])
        .invoke(messages)
    )
    logger.debug(f"Current state messages: {state['messages']}")

    goto = "__end__"
    locale = state.get("locale", "en-US")  # Default locale if not specified
    research_topic = state.get("research_topic", "")

    if len(response.tool_calls) > 0:
        goto = "planner"
        if state.get("enable_background_investigation"):
            # if the search_before_planning is True, add the web search tool to the planner agent
            goto = "background_investigator"
        try:
            for tool_call in response.tool_calls:
                if tool_call.get("name", "") != "handoff_to_planner":
                    continue
                if tool_call.get("args", {}).get("locale") and tool_call.get(
                    "args", {}
                ).get("research_topic"):
                    locale = tool_call.get("args", {}).get("locale")
                    research_topic = tool_call.get("args", {}).get("research_topic")
                    break
        except Exception as e:
            logger.error(f"Error processing tool calls: {e}")
    else:
        logger.warning(
            "Coordinator response contains no tool calls. Terminating workflow execution."
        )
        logger.debug(f"Coordinator response: {response}")
    messages = state.get("messages", [])
    if response.content:
        messages.append(HumanMessage(content=response.content, name="coordinator"))
    return Command(
        update={
            "messages": messages,
            "locale": locale,
            "research_topic": research_topic,
            "resources": configurable.resources,
        },
        goto=goto,
    )


def reporter_node(state: State, config: RunnableConfig):
    """Reporter node that write a final report."""
    logger.info("Reporter write final report")
    configurable = Configuration.from_runnable_config(config)
    current_plan = state.get("current_plan")
    input_ = {
        "messages": [
            HumanMessage(
                f"# Research Requirements\n\n## Task\n\n{current_plan.title}\n\n## Description\n\n{current_plan.thought}"
            )
        ],
        "locale": state.get("locale", "en-US"),
    }
    invoke_messages = apply_prompt_template("reporter", input_, configurable)
    observations = state.get("observations", [])

    # Add a reminder about the new report format, citation style, and table usage
    invoke_messages.append(
        HumanMessage(
            content="IMPORTANT: Structure your report according to the format in the prompt. Remember to include:\n\n1. Key Points - A bulleted list of the most important findings\n2. Overview - A brief introduction to the topic\n3. Detailed Analysis - Organized into logical sections\n4. Survey Note (optional) - For more comprehensive reports\n5. Key Citations - List all references at the end\n\nFor citations, DO NOT include inline citations in the text. Instead, place all citations in the 'Key Citations' section at the end using the format: `- [Source Title](URL)`. Include an empty line between each citation for better readability.\n\nPRIORITIZE USING MARKDOWN TABLES for data presentation and comparison. Use tables whenever presenting comparative data, statistics, features, or options. Structure tables with clear headers and aligned columns. Example table format:\n\n| Feature | Description | Pros | Cons |\n|---------|-------------|------|------|\n| Feature 1 | Description 1 | Pros 1 | Cons 1 |\n| Feature 2 | Description 2 | Pros 2 | Cons 2 |",
            name="system",
        )
    )

    for observation in observations:
        invoke_messages.append(
            HumanMessage(
                content=f"Below are some observations for the research task:\n\n{observation}",
                name="observation",
            )
        )
    logger.debug(f"Current invoke messages: {invoke_messages}")
    response = get_llm_by_type(AGENT_LLM_MAP["reporter"]).invoke(invoke_messages)
    response_content = response.content
    logger.info(f"reporter response: {response_content}")

    return {"final_report": response_content}


def research_team_node(state: State):
    """Research team node that collaborates on tasks."""
    logger.info("Research team is collaborating on tasks.")
    pass


async def _execute_agent_step(
    state: State, agent, agent_name: str
) -> Command[Literal["research_team"]]:
    """Helper function to execute a step using the specified agent."""
    current_plan = state.get("current_plan")
    plan_title = current_plan.title
    observations = state.get("observations", [])

    # Find the first unexecuted step
    current_step = None
    completed_steps = []
    for step in current_plan.steps:
        if not step.execution_res:
            current_step = step
            break
        else:
            completed_steps.append(step)

    if not current_step:
        logger.warning("No unexecuted step found")
        return Command(goto="research_team")

    logger.info(f"Executing step: {current_step.title}, agent: {agent_name}")

    # Format completed steps information
    completed_steps_info = ""
    if completed_steps:
        completed_steps_info = "# Completed Research Steps\n\n"
        for i, step in enumerate(completed_steps):
            completed_steps_info += f"## Completed Step {i + 1}: {step.title}\n\n"
            completed_steps_info += f"<finding>\n{step.execution_res}\n</finding>\n\n"

    # Prepare the input for the agent with completed steps info
    agent_input = {
        "messages": [
            HumanMessage(
                content=f"# Research Topic\n\n{plan_title}\n\n{completed_steps_info}# Current Step\n\n## Title\n\n{current_step.title}\n\n## Description\n\n{current_step.description}\n\n## Locale\n\n{state.get('locale', 'en-US')}"
            )
        ]
    }

    # Add citation reminder for researcher agent
    if agent_name == "researcher":
        if state.get("resources"):
            resources_info = "**The user mentioned the following resource files:**\n\n"
            for resource in state.get("resources"):
                resources_info += f"- {resource.title} ({resource.description})\n"

            agent_input["messages"].append(
                HumanMessage(
                    content=resources_info
                    + "\n\n"
                    + "You MUST use the **local_search_tool** to retrieve the information from the resource files.",
                )
            )

        agent_input["messages"].append(
            HumanMessage(
                content="IMPORTANT: DO NOT include inline citations in the text. Instead, track all sources and include a References section at the end using link reference format. Include an empty line between each citation for better readability. Use this format for each reference:\n- [Source Title](URL)\n\n- [Another Source](URL)",
                name="system",
            )
        )

    # Invoke the agent
    default_recursion_limit = 25
    try:
        env_value_str = os.getenv("AGENT_RECURSION_LIMIT", str(default_recursion_limit))
        parsed_limit = int(env_value_str)

        if parsed_limit > 0:
            recursion_limit = parsed_limit
            logger.info(f"Recursion limit set to: {recursion_limit}")
        else:
            logger.warning(
                f"AGENT_RECURSION_LIMIT value '{env_value_str}' (parsed as {parsed_limit}) is not positive. "
                f"Using default value {default_recursion_limit}."
            )
            recursion_limit = default_recursion_limit
    except ValueError:
        raw_env_value = os.getenv("AGENT_RECURSION_LIMIT")
        logger.warning(
            f"Invalid AGENT_RECURSION_LIMIT value: '{raw_env_value}'. "
            f"Using default value {default_recursion_limit}."
        )
        recursion_limit = default_recursion_limit

    logger.info(f"Agent input: {agent_input}")
    result = await agent.ainvoke(
        input=agent_input, config={"recursion_limit": recursion_limit}
    )

    # Process the result
    response_content = result["messages"][-1].content
    logger.debug(f"{agent_name.capitalize()} full response: {response_content}")

    # Update the step with the execution result
    current_step.execution_res = response_content
    logger.info(f"Step '{current_step.title}' execution completed by {agent_name}")

    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=response_content,
                    name=agent_name,
                )
            ],
            "observations": observations + [response_content],
        },
        goto="research_team",
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
) -> Command[Literal["research_team"]]:
    """Helper function to set up an agent with appropriate tools and execute a step.

    This function handles the common logic for both researcher_node and coder_node:
    1. Configures MCP servers and tools based on agent type
    2. Creates an agent with the appropriate tools or uses the default agent
    3. Executes the agent on the current step

    Args:
        state: The current state
        config: The runnable config
        agent_type: The type of agent ("researcher" or "coder")
        default_tools: The default tools to add to the agent

    Returns:
        Command to update state and go to research_team
    """
    configurable = Configuration.from_runnable_config(config)
    mcp_servers = {}
    enabled_tools = {}

    # Extract MCP server configuration for this agent type
    if configurable.mcp_settings:
        for server_name, server_config in configurable.mcp_settings["servers"].items():
            if (
                server_config["enabled_tools"]
                and agent_type in server_config["add_to_agents"]
            ):
                mcp_servers[server_name] = {
                    k: v
                    for k, v in server_config.items()
                    if k in ("transport", "command", "args", "url", "env", "headers")
                }
                for tool_name in server_config["enabled_tools"]:
                    enabled_tools[tool_name] = server_name

    # Create and execute agent with MCP tools if available
    if mcp_servers:
        client = MultiServerMCPClient(mcp_servers)
        loaded_tools = default_tools[:]
        all_tools = await client.get_tools()
        for tool in all_tools:
            if tool.name in enabled_tools:
                tool.description = (
                    f"Powered by '{enabled_tools[tool.name]}'.\n{tool.description}"
                )
                loaded_tools.append(tool)
        agent = create_agent(agent_type, agent_type, loaded_tools, agent_type)
        return await _execute_agent_step(state, agent, agent_type)
    else:
        # Use default tools if no MCP servers are configured
        agent = create_agent(agent_type, agent_type, default_tools, agent_type)
        return await _execute_agent_step(state, agent, agent_type)


async def researcher_node(
    state: State, config: RunnableConfig
) -> Command[Literal["research_team"]]:
    """Researcher node that do research"""
    logger.info("Researcher node is researching.")
    configurable = Configuration.from_runnable_config(config)
    tools = [get_web_search_tool(configurable.max_search_results), crawl_tool]
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        tools.insert(0, retriever_tool)
    logger.info(f"Researcher tools: {tools}")
    return await _setup_and_execute_agent_step(
        state,
        config,
        "researcher",
        tools,
    )


async def coder_node(
    state: State, config: RunnableConfig
) -> Command[Literal["research_team"]]:
    """Coder node that do code analysis."""
    logger.info("Coder node is coding.")
    return await _setup_and_execute_agent_step(
        state,
        config,
        "coder",
        [python_repl_tool],
    )

async def query_node(state: State, config: RunnableConfig) -> Command[Literal["route"]]:
    """处理用户查询，提取关键信息并加载历史对话"""
    logger.info("Query node processing user input and loading conversation history")

    # 从配置中获取用户ID和会话ID
    user_id = config.get("configurable", {}).get("user_id")
    thread_id = config.get("configurable", {}).get("thread_id")
    
    # 从redis中获取消息记录
    history_messages = conversation_manager.get_messages(
        session_id=thread_id,
        user_id=int(user_id),
        limit=19  # 限制最近19条消息，为当前消息留出空间
    )

    update_dict = {
        "user_query": state["messages"][-1].content,
        "current_iteration": 0,
        "max_retrieval_iterations": 3,
        "memory_threshold": 0.65,
        "needs_retrieval": False
    }

    if not history_messages:
        logger.warning("No history messages found in Redis")
    
    else:
        logger.info(f"Found {len(history_messages)} history messages in Redis")
        num = len(state["messages"])
        if num == 1:
            logger.info("no history messages in state")
            try:
                historical_messages = []
                # 将历史消息转换为LangChain消息格式
                for msg in history_messages:
                    if msg.message_role == MessageRole.USER:
                        historical_messages.append(HumanMessage(content=msg.message))
                    elif msg.message_role == MessageRole.ASSISTANT:
                        historical_messages.append(AIMessage(content=msg.message))
                
                logger.info(f"deal with history messages to langchain messages")
                
                update_dict["messages"] = "delete"
                update_dict["history_messages"] = historical_messages
                
            except Exception as e:
                logger.error(f"Failed to load conversation history: {e}")
        else:
            logger.info("history messages have been loaded state['messages']")
    return Command(
        # 如果有历史消息且没有被加载进state中，则更新三个字段(user_query, history_messages, messages被清空)
        # 如果没有历史消息或者有历史消息且已经被加载进state中，则更新一个字段(user_query)
        update=update_dict,
        goto="route"
    )

async def route_node(state: State, config: RunnableConfig) -> Command[Literal["get_memory", "answer"]]:
    """判断是否需要检索相关信息"""
    logger.info("Route node determining if retrieval is needed")

    history_messages = state.get("history_messages", [])

    system_msg = apply_prompt_template("route", state)
    llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))

    update_dict = {}

    if history_messages:
        logger.info("get history messages")
        question = state["history_messages"]
        logger.info(question)
        update_dict["messages"] = question
        msg = system_msg + question
        response = await llm.ainvoke(msg)
        needs_retrieval = response.content.strip().lower() == "true"

    else:
        logger.info("use state['messages'] to invoke llm")
        question = state["messages"]
        logger.info(question)
        msg = system_msg + question
        response = await llm.ainvoke(msg)
        needs_retrieval = response.content.strip().lower() == "true"
    
    # 测试，直接生成
    # if needs_retrieval:
    #     needs_retrieval = False

    if needs_retrieval:
        return Command(
            update=update_dict,
            goto="get_memory"
        )
    else:
        return Command(
            update=update_dict,
            goto="answer"
        )

async def generate_answer(state: State, config: RunnableConfig) -> Command[Literal["__end__"]]:
    """不需要检索，直接回复节点"""
    logger.info("generate answer.")
    system_msg = apply_prompt_template("answer", state)
    msg = system_msg + state["messages"]
    llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))
    response = await llm.ainvoke(msg)
    update_dict = {"messages": AIMessage(content=response.content)}
    return Command(
        update=update_dict,
        goto="__end__"
    )

async def get_memory_node(state: State, config: RunnableConfig) -> Command[Literal["supervisor"]]:
    """从记忆中获取相关信息"""
    logger.info("Get memory node retrieving relevant information")
    
    user_query = state["user_query"]
    memory_threshold = state["memory_threshold"]

    query_vector = get_text_embeddings(user_query)
    memory = await milvus_service.search_data_by_single_vector(
        "memory", query_vector, "question_embedding", ["question", "answer"], 3
    )

    # 处理记忆模板返回的结果
    memory_info = []
    for item in memory:
        distance = item.get("distance", 0)
        if distance >= memory_threshold:
            memory_info.append(item.get("fields"))

    return Command(
        update={"memory_info": memory_info},
        goto="supervisor"
    )

async def supervisor_node(state: State, config: RunnableConfig) -> Command[Literal["retrieval_agent", "deal_with_results"]]:
    """监督者节点，判断是否需要更多信息"""
    logger.info("Supervisor node evaluating if more information is needed")

    user_query = state.get("user_query")
    memory_info = state.get("memory_info", [])
    retrieved_information = state.get("retrieved_information", [])
    task_description = state.get("task_description", [])
    needs_retrieval = state.get("needs_retrieval", False)

    current_iteration = state.get("current_iteration")
    max_iterations = state.get("max_retrieval_iterations")
    
    # 检查是否达到最大迭代次数
    if current_iteration >= max_iterations:
        logger.info(f"Reached max iterations ({max_iterations}), proceeding to validation")
        return Command(
            update={"needs_more_info": False},
            goto="deal_with_results"
        )
    
    # 使用LLM判断当前信息是否足够
    llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))
    prepare_params = {
        "user_query": user_query,
        "memory_info": memory_info,
        "retrieved_information": retrieved_information,
        "task_description": task_description
    }
    supervisor_msg = apply_prompt_template("supervisor", state, ** prepare_params)
    msg = supervisor_msg + state["messages"]

    class structured_schema(BaseModel):
        needs_more_info: bool
        task_description_item: str

    response = await llm.with_structured_output(structured_schema).ainvoke(msg)
    need_more_info = response.needs_more_info
    task_description_item = response.task_description_item

    update_dict = {}
    if need_more_info and not needs_retrieval:
        update_dict["needs_retrieval"] = True

    # 测试
    if need_more_info:
        need_more_info = False

    if need_more_info:
        tasks = task_description.append(task_description_item)
        update_dict["task_description"] = tasks
        update_dict["current_iteration"] = current_iteration + 1
        return Command(update=update_dict, goto="retrieval_agent")
    else:
        return Command(
            update=update_dict,
            goto="deal_with_results"
        )


async def retrieval_agent_node(state: State, config: RunnableConfig) -> Command[Literal["supervisor"]]:
    """检索agent - 使用向量数据库进行检索相关信息"""
    logger.info("检索agent - 使用向量数据库进行检索相关信息")
    
    user_query = state["user_query"]
    
    # 这里实现具体的检索逻辑 使用一个子图实现
    # 可以是向量检索、知识库检索等
    retrieved_info = RetrievedInfo(
        content=f"技术检索结果: {user_query}的相关技术信息",
        source="technical_knowledge_base",
        relevance_score=0.85,
        metadata={"type": "technical", "timestamp": "2024-01-01"}
    )
    
    # 更新检索到的信息
    current_info = state["retrieved_information"]
    current_info.append(retrieved_info)
    
    # 更新上下文
    context_parts = [state["current_context"]] if state["current_context"] else []
    context_parts.append(f"技术检索结果: {retrieved_info.content}")
    new_context = "\n\n".join(context_parts)
    
    return Command(
        update={
            "retrieved_information": current_info,
            "current_context": new_context
        },
        goto="supervisor"
    )


async def deal_with_results_node(state: State, config: RunnableConfig) -> Command[Literal["update_memory"]]:
    """处理结果，生成最终答案"""
    logger.info("generating final answer")
    
    user_query = state.get("user_query")
    memory_info = state.get("memory_info", [])
    retrieved_information = state.get("retrieved_information", [])
    
    # 使用LLM生成最终答案
    llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))

    prepare_params = {
        "user_query": user_query,
        "memory_info": memory_info,
        "retrieved_information": retrieved_information
    }
    system_msg = apply_prompt_template("answer", state, ** prepare_params)
    msg = system_msg + state["messages"] + [HumanMessage(content="请根据以上参考信息，来回答用户最新的问题。")]
    
    response = await llm.ainvoke(msg)
    final_answer = response.content
    
    return Command(
        update={"final_answer": final_answer},
        goto="update_memory"
    )


async def update_memory_node(state: State, config: RunnableConfig) -> Command[Literal["__end__"]]:
    """更新记忆，存储检索到的信息"""
    logger.info("Update memory node storing retrieved information")
    
    final_answer = state.get("final_answer")
    user_query = state.get("user_query")
    memory_info = state.get("memory_info", [])
    needs_retrieval = state.get("needs_retrieval", False)

    if needs_retrieval:
        logger.info("使用了知识库进行检索，判断是否需要更新记忆")
    
        llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))

        prepare_params = {
            "user_query": user_query,
            "answer": final_answer,
            "memory_info": memory_info
        }

        system_msg = apply_prompt_template("update_memory", state, ** prepare_params)

        msg = system_msg + [HumanMessage(content="判断当前问答对是否需要更新到记忆数据库中。")]

        response = await llm.ainvoke(msg)

        update_memory = response.content

        if update_memory:
            # 写入向量数据库
            data = {
                "question": user_query,
                "question_embedding": get_text_embeddings(user_query),
                "answer": update_memory
            }
            result = milvus_service.insert_data("memory", data)

            if result:
                logger.info("写入成功")
            else:
                logger.warning("写入失败！")
        else:
            logger.info("无需更新记忆")
    else:
        logger.info("没有使用知识库检索，无需更新记忆")

    # 构造更新字段
    update_dict = {
        "messages": AIMessage(content=final_answer),
    }
    
    return Command(
        update=update_dict,
        goto="__end__"
    )
