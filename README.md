personal assistant
---

## Function description

This system has the ability of information retrieval and memory. It can remember the personal information, to-do items and preference settings you input, and can call external tools to retrieve real-time information and generate accurate answers.

The "src" folder is the source file.

* `interactive_page.py` A front-end page written using streamlit.
* `main.py` A back-end application written using fastapi, with services provided by agent written using langgraph.

## how to start
the first step is to prepare your environment.

```bash
pip install uv
uv sync --frozen
```
the second step is to prepare the api key of deepseek, zhipu, qwen, and tavily

the third step is to run the mcp server
```bash
python src/sub_graph/search_server.py
```

the fourth step is to run the back end
```bash
python src/main.py
```
The fifth step is to run the front-end page

```bash
streamlit run src/interactive_page.py
```

## note
You need to ensure that the mcp server runs on port 8000 and the fastapi runs on port 8001.
