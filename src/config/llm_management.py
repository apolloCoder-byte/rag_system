import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from src.llms.llm import get_basic_llm_config_param

load_dotenv()

DEFAULT_TEMPERATURE = 0
MODEL_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "model": "deepseek-chat"
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "api_key": os.getenv("ZHIPU_API_KEY"),
        "model": "GLM-4-Long"
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": os.getenv("QWEN_API_KEY"),
        "model": "qwen-plus"
    }
}


def create_llm(llm_type: str):
    model = ChatOpenAI(
        base_url=MODEL_CONFIG[llm_type]["base_url"],
        api_key=MODEL_CONFIG[llm_type]["api_key"],
        model=MODEL_CONFIG[llm_type]["model"],
        temperature=DEFAULT_TEMPERATURE,
        streaming=True)
    return model

def create_basic_llm():
    params = get_basic_llm_config_param("route")
    model = ChatOpenAI(
        base_url=params[0],
        api_key=params[2],
        model=params[1],
        temperature=DEFAULT_TEMPERATURE,
        streaming=True)
    return model


if __name__ == '__main__':
    model = create_basic_llm()
    respond = model.invoke("hello!")
    print("llm respond: ", respond.content)
