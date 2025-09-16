import os
from datetime import datetime

from langchain_core.messages import SystemMessage
from langgraph.prebuilt.chat_agent_executor import AgentState

def load_prompt_from_file(prompt_name: str) -> str:
    """
    从 Python 文件中加载 prompt 模板。

    Args:
        prompt_name: prompt 文件名（不包含 .py 扩展名）

    Returns:
        模板字符串
    """
    try:
        # 构建文件路径
        current_dir = os.path.dirname(__file__)
        prompt_file_path = os.path.join(current_dir, f"{prompt_name}.py")
        
        # 检查文件是否存在
        if not os.path.exists(prompt_file_path):
            raise FileNotFoundError(f"Prompt file {prompt_file_path} not found")
        
        # 动态导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location(prompt_name, prompt_file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 获取模板变量（假设变量名为 {PROMPT_NAME}_PROMPT）
        template_var_name = f"{prompt_name.upper()}_PROMPT"
        if hasattr(module, template_var_name):
            return getattr(module, template_var_name)
        else:
            raise AttributeError(f"Template variable {template_var_name} not found in {prompt_name}.py")
        
    except Exception as e:
        raise ValueError(f"Error loading prompt file {prompt_name}: {e}")


def apply_prompt_template(
    prompt_name: str, state: AgentState, **kwargs
) -> list:
    """
    应用模板变量到 prompt 模板并返回格式化的消息。

    Args:
        prompt_name: 要使用的 prompt 模板名称
        state: 当前 agent 状态，包含要替换的变量

    Returns:
        包含系统 prompt 作为第一条消息的消息列表
    """
    template = load_prompt_from_file(prompt_name)
    current_time = datetime.now().strftime("%a %b %d %Y %H:%M:%S %z")
    locale = state.get("locale", "zh-CN")

    params = {**kwargs}

    system_prompt = template.format(
        CURRENT_TIME=current_time,
        locale=locale,
        **params
    )

    return [SystemMessage(content=system_prompt)]

if __name__ == "__main__":
    print(load_prompt_from_file("chat"))
