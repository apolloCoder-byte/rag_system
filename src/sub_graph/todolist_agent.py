import asyncio
import uuid
from datetime import datetime

from langgraph.graph import END, START, StateGraph
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langchain_core.messages import HumanMessage, SystemMessage
from trustcall import create_extractor

from config.llm_management import create_llm
from sub_graph.sub_graph_states import ToDOListSchema, InputSchema, Profile, ToDo
from sub_graph.prompt import TRUSTCALL_INSTRUCTION, CREATE_INSTRUCTIONS, JUDGE_TODOLIST_ISREASONABLE


class ToDoListAgent:

    def __init__(self, with_thread, across_thread):
        self.agent = self.construct_graph(with_thread, across_thread)

    async def update_profile(self, state: ToDOListSchema, config: RunnableConfig, store: BaseStore):
        user_id = config["configurable"]["user_id"]
        namespace = ("profile", user_id)
        existing_items = store.search(namespace)

        tool_name = "Profile"
        existing_memories = [(existing_item.key, tool_name, existing_item.value) for existing_item in
                             existing_items] if existing_items else None

        system_message = TRUSTCALL_INSTRUCTION.format(time=datetime.now().isoformat())

        updated_conversation = [SystemMessage(content=system_message)] + [HumanMessage(state.update_object.sub_message)]

        model = create_llm("deepseek")

        profile_extractor = create_extractor(
            model,
            tools=[Profile],
            tool_choice="Profile",
        )

        result = await profile_extractor.ainvoke({"messages": updated_conversation, "existing": existing_memories})

        for r, rmeta in zip(result["responses"], result["response_metadata"]):
            store.put(
                namespace,
                rmeta.get("json_doc_id", str(uuid.uuid4())),
                r.model_dump(mode="json")
            )

        return {"updated_status": "ok"}

    async def update_instructions(self, state: ToDOListSchema, config: RunnableConfig, store: BaseStore):
        user_id = config["configurable"]["user_id"]

        namespace = ("instructions", user_id)

        existing_memory = store.get(namespace, "user_instructions")

        # Format the memory in the system prompt
        system_msg = CREATE_INSTRUCTIONS.format(current_instructions=existing_memory.value if existing_memory else None)

        # construct messages
        messages = [SystemMessage(content=system_msg)] + [HumanMessage(state.update_object.sub_message)] + \
                   [HumanMessage(content="Please update the instructions based on the conversation")]
        model = create_llm("deepseek")
        new_memory = await model.ainvoke(messages)
        # Overwrite the existing memory in the store
        key = "user_instructions"
        store.put(namespace, key, {"memory": new_memory.content})

        return {"updated_status": "ok"}

    async def update_todos(self, state: ToDOListSchema, config: RunnableConfig, store: BaseStore):
        user_id = config["configurable"]["user_id"]
        namespace = ("todo", user_id)
        existing_items = store.search(namespace)
        tool_name = "ToDo"
        existing_memories = [(existing_item.key, tool_name, existing_item.value) for existing_item in
                             existing_items] if existing_items else None
        system_message = TRUSTCALL_INSTRUCTION.format(time=datetime.now().isoformat())
        updated_messages = [SystemMessage(content=system_message)] + [HumanMessage(state.update_object.sub_message)]

        model = create_llm("deepseek")

        todo_extractor = create_extractor(
            model,
            tools=[ToDo],
            tool_choice="ToDo",
            enable_inserts=True
        )

        result = await todo_extractor.ainvoke({"messages": updated_messages, "existing": existing_memories})
        for r, rmeta in zip(result["responses"], result["response_metadata"]):
            store.put(
                namespace,
                rmeta.get("json_doc_id", str(uuid.uuid4())),
                r.model_dump(mode="json")
            )

        return {"updated_status": "ok"}

    async def judge_reasonable(self, state: ToDOListSchema, config: RunnableConfig, store: BaseStore):
        update_todolist = state.update_object.sub_message

        user_id = config["configurable"]["user_id"]
        namespace = ("todo", user_id)
        memories = store.search(namespace)
        existing = "\n".join(f"{mem.value}" for mem in memories)

        # get preference
        namespace_prefer = ("instructions", user_id)
        existing_memory = store.get(namespace_prefer, "user_instructions")
        if existing_memory is not None:
            instructions = existing_memory.value["memory"]
        else:
            instructions = None
        # print(existing_memory)

        system_message = JUDGE_TODOLIST_ISREASONABLE.format(time=datetime.now().isoformat(), existing=existing,
                                                            update=update_todolist, preference=instructions)
        input_message = [SystemMessage(content=system_message)]
        model = create_llm("deepseek")
        result = await model.ainvoke(input_message)
        if result.content == "yes":
            return {"updated_status": "ok"}
        else:
            error_message = result.content.split('---<')[1].split('>')[0]
            return {"updated_status": "no", "error_messages": [error_message]}

    def route_message(self, state: InputSchema):
        update_object = state.update_object
        type = update_object.router_type
        if type == "user_profile":
            return "update_profile"
        elif type == "user_todo":
            return "judge_reasonable"
        elif type == "user_instructions":
            return "update_instructions"
        else:
            raise ValueError

    def check_reasonable(self, state: ToDOListSchema):
        status = state.updated_status
        if status == "ok":
            return "update_todos"
        else:
            return "END"

    def construct_graph(self, with_thread, across_thread):
        builder = StateGraph(ToDOListSchema, input=InputSchema)
        # add nodes
        builder.add_node("update_profile", self.update_profile)
        builder.add_node("update_todos", self.update_todos)
        builder.add_node("update_instructions", self.update_instructions)
        builder.add_node("judge_reasonable", self.judge_reasonable)

        # add edges
        builder.add_conditional_edges(START, self.route_message)
        builder.add_edge("update_profile", END)
        builder.add_edge("update_instructions", END)
        builder.add_conditional_edges("judge_reasonable", self.check_reasonable)
        builder.add_edge("update_todos", END)

        return builder.compile(checkpointer=with_thread, store=across_thread)

    async def ainvoke(self, state: InputSchema, config: RunnableConfig):
        result = await self.agent.ainvoke(state, config)
        return result


async def main():
    import time
    from main_graph.main_graph_states import Router
    from langgraph.store.memory import InMemoryStore
    from langgraph.checkpoint.memory import MemorySaver

    config = {"configurable": {"thread_id": "1", "user_id": "Lance"}}
    across_thread_memory = InMemoryStore()

    within_thread_memory = MemorySaver()

    agent = ToDoListAgent(within_thread_memory, across_thread_memory)

    while True:
        content = input("you: ")
        if content == "exit":
            break

        inputs = Router(sub_message=content, router_type="user_profile")
        state = InputSchema(update_object=inputs)
        start = time.time()
        result = await agent.ainvoke(state, config)
        end = time.time()
        print("consume time: ", end - start)
        print(result)


if __name__ == '__main__':
    asyncio.run(main())
