import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

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


if __name__ == '__main__':
    model_zhipu = create_llm("zhipu")
    model_deepseek = create_llm("deepseek")
    zhipu_respond = model_zhipu.invoke("hello!")
    deepseek_respond = model_deepseek.invoke("hello!")
    print("zhipu_respond: ", zhipu_respond.content)
    print("deepseek_respond: ", deepseek_respond.content)
