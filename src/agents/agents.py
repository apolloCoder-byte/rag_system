from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts import apply_prompt_template
from src.config.llm_management import create_basic_llm


# Create agents using configured LLM types
def create_agent(agent_name: str, agent_type: str, tools: list, prompt_template: str):
    """Factory function to create agents with consistent configuration."""
    return create_react_agent(
        name=agent_name,
        model=get_llm_by_type(AGENT_LLM_MAP[agent_type]),
        tools=tools,
        prompt=lambda state: apply_prompt_template(prompt_template, state),
    )

def get_react_agent(tools: list, prompt_template: str):
    llm = create_basic_llm()
    print(type(llm))
    agent = create_react_agent(
        model=llm, 
        tools=tools,
        prompt=apply_prompt_template(prompt_template, AgentState())[0]
    )
    return agent
