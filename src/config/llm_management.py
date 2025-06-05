from langchain_openai import ChatOpenAI

DEFAULT_TEMPERATURE = 0
MODEL_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "***REMOVED***",
        "model": "deepseek-chat"
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "api_key": "66614966e28343458665aa5db5a73707.Q0NjF5Z6ZI7QtH1e",
        "model": "GLM-4-Plus"
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
