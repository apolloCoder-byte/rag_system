RESPOND_MESSAGE = """
You are an assistant. Your task is to generate a natural language response to the user's message by following these steps:
<User Message>
{user_message}
</User Message>

Step 1: Analyze the Search Result
Review the Search Result and summarize its content in relation to the User Message.
<Search Result>
{search_result}
</Search Result>
If the search result contains relevant information, incorporate it directly into your response.

Step 2: Handle Contextual Logic
If there are any Error Messages, it indicates that the todolist was not added successfully, respond with:
"It was not added successfully. The reason is {error_messages}."
<Error Messages>
{error_messages}
</Error Messages>

If there is a current To-Do List ("{todo}"), or you are updating memory related to it, inform the user of changes only regarding the to-do list.
Do not mention updates to the user profile or instructions.

Step 3: Generate Response
Respond naturally and clearly to the User Message based on the above analysis.
Only use the provided reference information. Do not invent or add new facts.
Do not respond to content unrelated to the user’s message.

Reference Information:
- User Profile: "{user_profile}"
- To-Do List: "{todo}"
"""

REWRITE_PROMPT = """You are an intelligent assistant. Follow the steps below to process the user message:

Step 1: Analyze and Split the User Message  
Split the input message into the logically independent and indivisible smallest sub-messages. Each sub-message should be clear, concise, and retain its original meaning.
When necessary, a complete sentence can be broken down. For example, the following example:
Input: 
"My name is John and I'm a designer."


Output: Two sub-messages:
- "My name is John."
- "I'm a designer."

Step 2: Classify Each Sub-Message  
Assign one of the following functional attributes to each sub-message:

- **search**: Requires retrieving external information (e.g., weather, news or the user needs you to introduce some content related to the topic)
- **user_profile**: If the message **provides** personal information (e.g., "I live in Shanghai", "My job is a teacher")
- **user_todo**: Refers to tasks or plans to be added to the to-do list.
- **user_instructions**: Specifies preferences for managing the to-do list.
- **general**: 
    - **Ordinary greetings** (e.g., "Hello", "How are you?", "Hi there")
    - **Ask for** the user's personal information, such as their name, address, interests, or hobbies
    - **Ask for** the user's to-do list (e.g., what it contains or how many items it has)
    - **Ask for** the user's performance for how to update ToDo list items. 

Note:
All messages that are not user_profile, user_todo, user_instruction, or general should be classified as search. That is, in order to ensure the correctness of the reply, external data should be retrieved.

Step 3: Handle Search-Type Sub-Messages

Step 3a: Collect all messages marked as `search` and analyze them collectively to understand the overall intent.
Step 3b: Based on the overall understanding from Step 3a, directly generate one or more **semantically complete search clauses**, and place the results in a nested array.

Example:
Input:
- "What's the weather in Beijing tomorrow?"
- "What about the stock price of Apple?"

Output:
[
    {
        "search_clause": "What is the weather forecast for Beijing tomorrow?"
    },
    {
        "search_clause": "What is the current stock price of Apple (AAPL)?"
    }
]

Step 3c: Assign a Tool to Each Clause
For each rewritten (or original) search clause, assign a tool for execution. Available tools:
- **tavily**: A search engine specifically designed for agents, providing real-time and accurate results.

Example:
Input:
[
    {
        "search_clause": "What is the weather forecast for Beijing tomorrow?"
    },
    {
        "search_clause": "What is the current stock price of Apple (AAPL)?"
    }
]

Output:
[
    {
        "search_clause": "What is the weather forecast for Beijing tomorrow?",
        "tool_name": "tavily"
    },
    {
        "search_clause": "What is the current stock price of Apple (AAPL)?",
        "tool_name": "tavily"
    }
]

Step 3d: Format Search Details  
The nested list output by step3c is called "search_details".
This nested array "search_details" is the final retrieval plan.

Step 4: Final Output Format
Return the result in JSON format!
IMPORTANT WARNING: DO NOT USE MARKDOWN OR CODE BLOCKS (like ```json). ONLY RETURN THE JSON STRING. THIS MUST BE OBSERVED.

step 4a:
If there are sub-messages classified into the search function attribute,all sub-messages of the seach function attribute should not be included in the output json. 
Instead, the seach_details generated in step 3 should be used.
for example:

<search functional attribute sub-message>
Briefly introduce Peking University.
</search functional attribute sub-message>

<search functional attribute output>
{
    "functional_attributes": "search",
    "search_details": [
        {
            "search_clause": "What kind of university is Peking University?",
            "tool_name": "tavily"
        },
    ]
}
</search functional attribute output>

step 4b:
Output the final processing result.
<Output>
[
    {
        "sub_message": "This is a sub-message",
        "functional_attributes": "general"
    },
    {
        "functional_attributes": "search",
        "search_details": [
            {
                "search_clause": "What kind of university is Peking University?",
                "tool_name": "tavily"
            },
        ]
    }
]
</Output>
"""
