"""Chatbot API endpoints for handling chat interactions."""

import asyncio
import json
from typing import List, AsyncGenerator

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessageChunk, AIMessage
from src.api.auth import get_current_session, get_current_user
from src.config.setting import settings
from src.graph.builder import build_graph_with_memory
from loguru import logger
from src.schema.session import Session
from src.schema.chat import (
    ChatRequest,
    ChatResponse,
    Message,
    StreamResponse,
)
from src.schema.user import User

router = APIRouter()

# 全局 graph 实例，只创建一次
graph = build_graph_with_memory()

async def astream_workflow_generator(
    message: str,
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """异步流式工作流生成器
    
    Args:
        message: 用户消息
        thread_id: 线程ID
    
    Yields:
        str: Server-Sent Events 格式的数据
    """
    try:
        logger.info(f"Starting stream workflow for thread {thread_id}")
        
        # 构建输入状态
        input_state = {
            "messages": [HumanMessage(content=message)],
            "locale": "zh-CN",
        }
        
        # 配置参数
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        # 流式调用 graph
        async for chunk in graph.astream(input_state, config, stream_mode="messages"):
            # print(chunk)
            # print("\n")
            message_obj, _ = chunk
            if isinstance(message_obj, AIMessageChunk) and message_obj.content.strip() == "":
                continue

            if isinstance(message_obj, AIMessageChunk) and message_obj.content:
                yield f"data: {message_obj.content}\n\n"
                await asyncio.sleep(0.01)
            
            if isinstance(message_obj, AIMessage):
                continue
        # 发送完成信号
        final_data = {"content": "", "done": True}
        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"Error in stream workflow: {e}", exc_info=True)
        error_data = {"content": f"Error: {str(e)}", "done": True}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    user: User = Depends(get_current_user),
):
    """流式返回接口

    Args:
        request: FastAPI请求对象
        chat_request: 聊天请求
        user: 当前用户
    
    Returns:
        StreamingResponse: 流式响应
    """
    conversation_id = chat_request.conversation_id
    logger.info(f"conversation_id: {conversation_id}")
    return StreamingResponse(
        astream_workflow_generator(
            chat_request.message, 
            conversation_id
            ),
        media_type="text/event-stream")

@router.post("/chat")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    user: User = Depends(get_current_user),
):
    """普通聊天接口，使用 graph 工作流

    Args:
        request: FastAPI请求对象
        chat_request: 聊天请求
        user: 当前用户
    
    Returns:
        ChatResponse: 聊天响应
    """
    try:
        logger.info(f"Chat request received from user {user.id}, conversation_id: {chat_request.conversation_id}")
        
        # 构建输入状态
        input_state = {
            "messages": [HumanMessage(content=chat_request.message)],
            "locale": "zh-CN",  # 可以根据需要动态设置
        }
        
        # 配置参数
        config = {
            "configurable": {
                "thread_id": chat_request.conversation_id,
                "user_id": str(user.id)
            }
        }
        
        # 调用 graph 工作流
        result = await graph.ainvoke(input_state, config)
        
        # 提取响应内容
        response_content = ""
        if "messages" in result and result["messages"]:
            # 获取最后一条消息作为响应
            last_message = result["messages"][-1]
            response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        logger.info(f"Chat response generated: {response_content[:100]}...")
        
        return {"message": response_content}
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/chat/history/{conversation_id}")
async def get_chat_history(
    conversation_id: str,
    user: User = Depends(get_current_user),
):
    """获取聊天历史

    Args:
        conversation_id: 会话ID
        user: 当前用户
    
    Returns:
        ChatResponse: 聊天历史
    """
    try:
        logger.info(f"Getting chat history for conversation {conversation_id}")
        
        # 配置参数
        config = {
            "configurable": {
                "thread_id": conversation_id,
                "user_id": str(user.id)
            }
        }
        
        # 获取当前状态
        current_state = await graph.aget_state(config)
        
        if not current_state or not current_state.values.get("messages"):
            return ChatResponse(messages=[])
        
        # 转换消息格式
        messages = []
        for msg in current_state.values["messages"]:
            if hasattr(msg, 'content') and hasattr(msg, 'type'):
                role = "assistant" if msg.type == "ai" else "user"
                messages.append(Message(role=role, content=msg.content))
        
        return ChatResponse(messages=messages)
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")

@router.delete("/chat/history/{conversation_id}")
async def clear_chat_history(
    conversation_id: str,
    user: User = Depends(get_current_user),
):
    """清除聊天历史

    Args:
        conversation_id: 会话ID
        user: 当前用户
    
    Returns:
        dict: 操作结果
    """
    try:
        logger.info(f"Clearing chat history for conversation {conversation_id}")
        
        # 配置参数
        config = {
            "configurable": {
                "thread_id": conversation_id,
                "user_id": str(user.id)
            }
        }
        
        # 更新状态，清空消息
        await graph.aupdate_state(config, {"messages": []})
        
        return {"message": "Chat history cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
