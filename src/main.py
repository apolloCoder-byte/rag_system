from fastapi import FastAPI, Depends
from langchain_core.messages import HumanMessage

from config.setting import configs
from entity.dto import ConversationRequest
from main_graph.main_graph_states import InputState


def get_configs():
    return configs


app = FastAPI()


@app.post("/chat")
async def chat(request: ConversationRequest, setting=Depends(get_configs)):
    thread_id = request.thread_id
    config = {"configurable": {"thread_id": str(thread_id), "user_id": "Li"}}

    # get agent
    agent = setting.agent

    # input
    input_state = InputState(messages=[HumanMessage(content=request.content)])

    # ai respond
    result = await agent.ainvoke(input_state, config)
    # print(result)
    response = result["response"]

    return {"response": response}


@app.get("/")
async def test():
    return {"test": "test"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8001, reload=False)
