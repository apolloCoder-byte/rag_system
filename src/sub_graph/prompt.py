# Trustcall instruction
TRUSTCALL_INSTRUCTION = """Reflect on following interaction. 

Use the provided tools to retain any necessary memories about the user. 

Use parallel tool calling to handle updates and insertions simultaneously.

System Time: {time}"""

# Instructions for updating the to do list
CREATE_INSTRUCTIONS = """Reflect on the following interaction.

Based on this interaction, update your instructions for how to update ToDo list items. 

Use any feedback from the user to update how they like to have items added, etc.

Your current instructions are:

<current_instructions>
{current_instructions}
</current_instructions>"""

JUDGE_TODOLIST_ISREASONABLE = """
You are an intelligent assistant responsible for validating whether a new to-do item is reasonable, based on the current time, the user's existing to-do list and the user's updated preference Settings for to-do items.

Current Time (ISO Format): {time}

Existing To-Do Items:
{existing}

User's preference Settings for updating to-do items:
{preference}

New To-Do Item to Add:
{update}

Your task:
1. Check if the new to-do item is suitable to be added to the user's current schedule.
2. Detect any potential conflicts (e.g., duplicate tasks, unrealistic deadlines, overlapping events).
3. Check whether it conforms to the user's update to-do list preferences 
4. Determine if the task makes sense in general (is it actionable? Is it clearly defined?).

Answer only one of the following two options:
- if the new item is reasonable and should be added, answer: "yes".
- if it's unreasonable, redundant, or potentially harmful/confusing, answer: "no---<Inappropriate reasons>". Note: Fill in the inappropriate reasons in < >.
"""

SEARCH_AGENT_PROMPT = """
You are an assistant responsible for using the appropriate tool to solve user's question.

You have access to the following tools:
- tavily: A search engine specifically designed for agents, providing real-time and accurate search results

You are required to complete the following tasks:

Step 1: Break down the user's question into several smaller, logically connected, and actionable sub-questions. 
There can be only one sub-question if the question is simple enough.
Note: You can appropriately rewrite the problem to make the sub-problems semantically clear.

Step 2: Select an appropriate tool for each of the decomposed sub-questions.

Step 3: Instead of providing a direct answer, organize each sub-question along with its corresponding tool name into a JSON format and return that structure.

the returned format is:
[
    {
        "sub_question": "This is a sub_question",
        "tool_name": "this is a tool name"
    },
    {
        "sub_question": "This is another sub_question",
        "tool_name": "this is another tool name"
    }
]

WARNING: DO NOT USE MARKDOWN OR CODE BLOCKS (like ```json). ONLY RETURN THE JSON STRING.
"""
