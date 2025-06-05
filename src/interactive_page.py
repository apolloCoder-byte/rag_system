import streamlit as st
import uuid
from datetime import datetime
import requests

# 设置页面配置
st.set_page_config(
    page_title="AI 对话助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS - 苹果风格
st.markdown("""
<style>
    /* 主容器样式 */
    .main {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* 标题样式 */
    .header {
        text-align: center;
        margin-bottom: 20px;
    }

    .header h1 {
        font-size: 28px;
        font-weight: 600;
        letter-spacing: -0.5px;
        color: #1d1d1f;
        margin-bottom: 8px;
    }

    .header p {
        color: #86868b;
        font-size: 16px;
        margin-top: 0;
    }

    /* 聊天容器 */
    .chat-container {
        background-color: #f5f5f7;
        border-radius: 18px;
        padding: 20px;
        height: 65vh;
        overflow-y: auto;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 15px;
    }

    /* 消息气泡 */
    .message {
        margin-bottom: 12px;
        max-width: 80%;
        padding: 10px 14px;
        border-radius: 18px;
        line-height: 1.4;
        font-size: 15px;
        word-wrap: break-word;
    }

    .user-message {
        background-color: #0071e3;
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }

    .ai-message {
        background-color: #e8e8ed;
        color: #1d1d1f;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }

    /* 输入区域 */
    .input-container {
        display: flex;
        gap: 10px;
        margin-top: 15px;
    }

    .input-container textarea {
        flex: 1;
        padding: 12px 16px;
        border: 1px solid #d2d2d7;
        border-radius: 12px;
        font-size: 15px;
        font-family: inherit;
        resize: none;
        outline: none;
        min-height: 60px;
    }

    .input-container textarea:focus {
        border-color: #0071e3;
    }

    .input-container button {
        background-color: #0071e3;
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0 20px;
        font-size: 15px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        height: 60px;
    }

    .input-container button:hover {
        background-color: #0062c3;
    }

    /* 侧边栏样式 */
    .sidebar .sidebar-content {
        padding: 20px 15px;
    }

    .thread-item {
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 8px;
        cursor: pointer;
        font-size: 14px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .thread-item:hover {
        background-color: #f1f1f1;
    }

    .thread-item.active {
        background-color: #e0e0e0;
        font-weight: 500;
    }

    .new-thread-btn {
        width: 100%;
        padding: 10px;
        margin-top: 15px;
        background-color: #0071e3;
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 500;
        cursor: pointer;
    }

    .new-thread-btn:hover {
        background-color: #0062c3;
    }

    /* 滚动条样式 */
    ::-webkit-scrollbar {
        width: 6px;
    }

    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
</style>
""", unsafe_allow_html=True)

# 初始化会话状态
if "threads" not in st.session_state:
    st.session_state.threads = {}
    # 创建一个初始线程
    initial_thread_id = str(uuid.uuid4())
    st.session_state.threads[initial_thread_id] = {
        "id": initial_thread_id,
        "title": "新对话",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages": []
    }
    st.session_state.current_thread = initial_thread_id

if "current_thread" not in st.session_state:
    st.session_state.current_thread = list(st.session_state.threads.keys())[0]

# 侧边栏 - 线程列表
with st.sidebar:
    st.markdown("### 对话列表")

    # 显示所有线程
    for thread_id, thread in st.session_state.threads.items():
        thread_title = thread["title"]
        if len(thread["messages"]) > 0:
            # 使用第一条用户消息的前20个字符作为标题
            for msg in thread["messages"]:
                if msg["role"] == "user":
                    thread_title = msg["content"][:20] + ("..." if len(msg["content"]) > 20 else "")
                    break

        is_active = thread_id == st.session_state.current_thread
        thread_class = "thread-item active" if is_active else "thread-item"

        # 使用st.button实现可点击的线程项
        if st.button(
                thread_title,
                key=f"thread_{thread_id}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
        ):
            st.session_state.current_thread = thread_id
            st.rerun()

    # 新建线程按钮
    if st.button("+ New conversation", key="new_thread", use_container_width=True):
        new_thread_id = str(uuid.uuid4())
        st.session_state.threads[new_thread_id] = {
            "id": new_thread_id,
            "title": "新对话",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "messages": []
        }
        st.session_state.current_thread = new_thread_id
        st.rerun()

# 主界面
st.markdown("""
<div class="header">
    <h1>AI 对话助手</h1>
    <p>体验智能对话，探索无限可能</p>
</div>
""", unsafe_allow_html=True)

# 获取当前线程
current_thread = st.session_state.threads[st.session_state.current_thread]
# print(current_thread["id"])

# 聊天容器
chat_container = st.empty()


# 动态更新聊天显示
def update_chat_display():
    with chat_container.container():
        for message in current_thread["messages"]:
            if message["role"] == "user":
                st.markdown(f"""
                <div class="message user-message">
                    {message["content"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="message ai-message">
                    {message["content"]}
                </div>
                """, unsafe_allow_html=True)

        # 添加自动滚动到最新的JavaScript
        st.markdown("""
        <script>
            window.scrollTo(0, document.body.scrollHeight);
        </script>
        """, unsafe_allow_html=True)


# 初始化时显示历史消息
update_chat_display()

# 用户输入框
if prompt := st.chat_input("请输入您的问题..."):
    current_thread["messages"].append({"role": "user", "content": prompt})

    # 添加用户消息到历史
    # st.session_state.messages.append({"role": "user", "content": prompt})
    if len(current_thread["messages"]) == 1:
        current_thread["title"] = prompt.strip()[:20] + ("..." if len(prompt.strip()) > 20 else "")
    update_chat_display()  # 及时更新显示

    # 模拟AI回复
    # ai_response = f"我已收到你的消息: '{prompt.strip()}'。这是一个模拟回复，实际使用时需要连接真实的AI API。"
    # 向后端发送请求
    backend_url = "http://localhost:8001/chat"
    request_data = {
        "thread_id": current_thread["id"],
        "content": prompt
    }
    try:
        response = requests.post(backend_url, json=request_data)
        response.raise_for_status()
        response = response.json().get('response', "未收到有效响应")

    except Exception as e:
        response = f"请求后端失败: {str(e)}"

    # 添加AI回复到历史
    current_thread["messages"].append({"role": "assistant", "content": response})
    update_chat_display()  # 及时更新显示

    st.rerun()

# 确保每次页面加载都滚动到底部
st.markdown("""
<script>
    window.onload = function() {
        window.scrollTo(0, document.body.scrollHeight);
    };
</script>
""", unsafe_allow_html=True)
