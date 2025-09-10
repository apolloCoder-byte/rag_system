import json
import asyncio
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from src.main_graph.main_graph_states import InputState, AgentState, Router, GeneralState, OutputState
from src.sub_graph.search_tools import SearchSubGraph
from src.sub_graph.sub_graph_states import InputSchema
from src.sub_graph.sub_graph_states import SearchInputSchema
from src.config.llm_management import create_llm
from src.main_graph.prompt import RESPOND_MESSAGE, REWRITE_PROMPT
from src.sub_graph.todolist_agent import ToDoListAgent


class MultiAgentGraph:
    def __init__(self, across_thread_memory, within_thread_memory):
        self.across_thread_memory = across_thread_memory
        self.within_thread_memory = within_thread_memory

        self.todolist_agent = ToDoListAgent(self.within_thread_memory, self.across_thread_memory)
        self.search_tools = SearchSubGraph().construct_graph()

    async def judge_route_agent(self, state: InputState) -> dict[str, Any]:
        print(state)
        model = create_llm("qwen")
        # system_prompt = SYSTEM_ROMPT
        system_prompt = REWRITE_PROMPT  # 优化过的prompt，实现了分类和生成search计划
        messages = [SystemMessage(system_prompt)] + state.messages
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    async def general(self, state: GeneralState) -> dict[str, Any]:
        return {"a": "a"}

    async def todolist_agent_invoke(self, state: InputSchema, config: RunnableConfig) -> dict[str, Any]:
        result = await self.todolist_agent.ainvoke(state, config)
        # print(result)
        if "error_messages" in result:
            message = result["error_messages"]
        else:
            message = [""]
        # print(message)
        return {"error_messages": message}

    async def search_tools(self, state: SearchInputSchema) -> dict[str, Any]:
        result = await self.search_tools.ainvoke(state)
        respond_list = result["search_result"]
        return {"search_result": respond_list}

    async def respond(self, state: AgentState, config: RunnableConfig, store: BaseStore) -> dict[str, Any]:
        # get user query and error messages
        user_message = state.messages[0].content

        if hasattr(state, "error_messages"):
            error_messages = state.error_messages
            error_messages = "\n".join(error_messages)
        else:
            error_messages = ""

        if hasattr(state, "search_result"):
            # 解析搜索结果
            search_result = state.search_result
            formatted_string = "\n---\n".join(
                f"**Q**: {item['search_clause']}\n\n**A**: {item['search_result']}"
                for item in search_result
            )
            search_result = formatted_string
        else:
            search_result = ""

        user_id = config["configurable"]["user_id"]
        # get profile, collections
        namespace = ("profile", user_id)
        memories = store.search(namespace)
        user_profile = memories[0].value if memories else None

        namespace = ("todo", user_id)
        memories = store.search(namespace)
        todo = "\n".join(f"{mem.value}" for mem in memories)

        # messages
        system_message = RESPOND_MESSAGE.format(
            user_message=user_message, error_messages=error_messages, search_result=search_result,
            user_profile=user_profile, todo=todo
        )

        # llm
        model = create_llm("qwen")
        # 如果是智普，这里是HumanMessage，如果是deepseek，这里可以是SystemMessage
        response = await model.ainvoke([HumanMessage(system_message)])
        # print(response)

        # return respond
        result = {"response": response.content, "messages": "delete"}
        if hasattr(state, "error_messages"):
            result["error_messages"] = "delete"
        if hasattr(state, "search_result"):
            result["search_result"] = "delete"
        return result

    def route_to_execute(self, state: AgentState):
        ai_content = state.messages[-1].content
        print(ai_content)
        data = json.loads(ai_content)

        send_all = []
        for item in data:
            category = item["functional_attributes"]
            if category == "general":
                temp = [Send("general", GeneralState())]
                send_all.extend(temp)
            elif category in ["user_profile", "user_todo", "user_instructions"]:
                router = Router(sub_message=item["sub_message"], router_type=category)
                temp = [Send("todolist_agent", InputSchema(update_object=router))]
                send_all.extend(temp)
            elif category == "search":
                search_plan = item["search_details"]
                for sub_plan in search_plan:
                    clause = sub_plan["search_clause"]
                    tool_name = sub_plan["tool_name"]
                    temp = [Send("search_tools", SearchInputSchema(question=clause, tool_name=tool_name))]
                    send_all.extend(temp)
            else:
                raise ValueError
        return send_all

    def construct_graph(self):
        builder = StateGraph(AgentState, input=InputState, output=OutputState)
        # add nodes
        builder.add_node("judge_route_agent", self.judge_route_agent)
        builder.add_node('general', self.general)
        builder.add_node("todolist_agent", self.todolist_agent_invoke)
        builder.add_node("search_tools", self.search_tools)
        builder.add_node("respond", self.respond)
        # add edges
        builder.add_edge(START, "judge_route_agent")
        builder.add_conditional_edges("judge_route_agent", self.route_to_execute)
        builder.add_edge("general", "respond")
        builder.add_edge("todolist_agent", "respond")
        builder.add_edge("search_tools", "respond")
        builder.add_edge("respond", END)
        # builder.add_edge("judge_route_agent", END)

        return builder.compile(checkpointer=self.within_thread_memory, store=self.across_thread_memory)


async def main():
    import time

    across_thread_memory = InMemoryStore()

    within_thread_memory = MemorySaver()

    graph = MultiAgentGraph(across_thread_memory, within_thread_memory).construct_graph()

    content = "hello!"
    input_state = InputState(messages=[HumanMessage(content=content)])
    config = {"configurable": {"thread_id": "1", "user_id": "Lance"}}
    start = time.time()
    result = await graph.ainvoke(input_state, config)
    end = time.time()
    print("consume time: ", end - start)
    print(result)  # dict

    # while True:
    #     config = {"configurable": {"thread_id": "1", "user_id": "Lance"}}
    #     content = input("you: ")
    #     if content == "exit":
    #         break
    #
    #     input_state = InputState(messages=[HumanMessage(content=content)])
    #
    #     start = time.time()
    #     result = await graph.ainvoke(input_state, config)
    #     end = time.time()
    #     print("consume time: ", end - start)
    #     print(result)


if __name__ == '__main__':
    asyncio.run(main())
