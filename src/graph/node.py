
from typing import Literal
from loguru import logger

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type

from src.prompts.template import apply_prompt_template
from .types import State
from src.utils.conversation_manager import conversation_manager
from src.schema.redis import MessageRole
from src.services.milvus import milvus_service
from src.utils.embedding import get_text_embeddings
from src.agents.agents import get_react_agent
from src.rag.retriever import retriever_tool


async def query_node(state: State, config: RunnableConfig) -> Command[Literal["route"]]:
    """处理用户查询，提取关键信息并加载历史对话"""
    logger.info("Query node processing user input and loading conversation history")

    # 从配置中获取用户ID和会话ID
    user_id = config.get("configurable", {}).get("user_id")
    thread_id = config.get("configurable", {}).get("thread_id")

    update_dict = {
        "user_query": state["messages"][-1].content,
        "current_iteration": 0,
        "max_retrieval_iterations": 3,
        "memory_threshold": 0.65,
        "needs_retrieval": False,
        "task_description": []
    }
    
    # 从redis中获取消息记录
    history_messages = conversation_manager.get_messages(
        session_id=thread_id,
        user_id=int(user_id),
        limit=19  # 限制最近19条消息，为当前消息留出空间
    )
    logger.info(f"Found {len(history_messages)} history messages in Redis")

    # convert redis message to langchain message
    historical_messages = []
    for msg in history_messages:
        if msg.message_role == MessageRole.USER:
            historical_messages.append(HumanMessage(content=msg.message))
        elif msg.message_role == MessageRole.ASSISTANT:
            historical_messages.append(AIMessage(content=msg.message))
    logger.info(f"deal with history messages to langchain messages")
    update_dict["messages"] = "delete"
    update_dict["history_messages"] = historical_messages

    return Command(
        update=update_dict,
        goto="route"
    )

async def route_node(state: State, config: RunnableConfig) -> Command[Literal["get_memory", "answer"]]:
    """判断是否需要检索相关信息"""
    logger.info("Route node determining if retrieval is needed")

    logger.info("get history messages")
    history_messages = state.get("history_messages", [])
    
    prepare_params = {
        "user_query": state.get("user_query")
    }

    system_msg = apply_prompt_template("route", state, ** prepare_params)
    llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))

    update_dict = {}

    update_dict["messages"] = history_messages
    msg = system_msg + history_messages
    response = await llm.ainvoke(msg)
    print(response.content.strip().lower())
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
    prepare_params = {
        "user_query": state.get("user_query")
    }
    system_msg = apply_prompt_template("general_answer", state, **prepare_params)
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
    
    memory_threshold = state["memory_threshold"]

    prepare_params = {"user_query": state.get("user_query")}

    system_msg = apply_prompt_template("get_memory", state, **prepare_params)
    msg = system_msg + state["messages"]
    llm = get_llm_by_type(AGENT_LLM_MAP.get("route", "basic"))
    response = await llm.ainvoke(msg)
    rewrite_question = response.content
    update_dict = {"rewrite_query": rewrite_question}
    logger.info(f"LLM将用户输入的问题进行重写以进行记忆搜索：{rewrite_question}")

    query_vector = get_text_embeddings(rewrite_question)
    memory = await milvus_service.search_data_by_single_vector(
        "memory", query_vector, "question_embedding", ["question", "answer"], 3
    )

    # 处理记忆模板返回的结果
    memory_info = []
    for item in memory:
        distance = item.get("distance", 0)
        if distance >= memory_threshold:
            memory_info.append(item.get("fields"))
    
    update_dict["memory_info"] = memory_info
    logger.info(f"过滤出{len(memory_info)}条memory可用")

    return Command(
        update=update_dict,
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
    # if need_more_info:
    #     need_more_info = False

    if need_more_info and task_description_item:
        task_description.append(task_description_item)
        update_dict["task_description"] = task_description
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
    tasks = state.get("task_description", [user_query])
    
    logger.info("获取react智能体")
    agent = get_react_agent([retriever_tool], "research")

    logger.info("开始推理")
    try:
        messages = agent.invoke({"messages": [("human", tasks[-1])]})
    except Exception as e:
        logger.error(f"推理发生错误：{e}")
        messages = {"messages": [AIMessage(content="未找到有效内容")]}
    logger.info("推理结束")

    logger.info("准备更新字段")
    retrieved_info = messages["messages"][-1].content
    retrieved_info_history = state.get("retrieved_information", [])
    retrieved_info_history.append(retrieved_info)
    update_dict = {
        "retrieved_information": retrieved_info_history
    }
    
    return Command(
        update=update_dict,
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

        msg = system_msg + state["messages"]

        response = await llm.ainvoke(msg)

        temp = response.content
        logger.info(f"总结出的记忆：{temp}")
        if temp:
            # 写入向量数据库
            rewrite_query = state.get("rewrite_query")
            data = [{
                "question": rewrite_query,
                "question_embedding": get_text_embeddings(rewrite_query),
                "answer": temp
            }]
            result = await milvus_service.insert_data("memory", data)

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
