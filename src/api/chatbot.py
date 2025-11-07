"""Chatbot API endpoints for handling chat interactions."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage, HumanMessage, AIMessageChunk, AIMessage
from src.api.auth import get_current_user
from src.graph.builder import build_agentic_rag_graph
from src.utils.conversation_manager import conversation_manager
from src.schema.redis import MessageRole
from loguru import logger
from src.schema.chat import (
    ChatRequest,
    ChatResponse,
    Message,
)
from src.schema.user import User

router = APIRouter()

graph = build_agentic_rag_graph()

async def astream_workflow_generator(
    message: str,
    thread_id: str,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """异步流式工作流生成器
    
    Args:
        message: 用户消息
        thread_id: 线程ID
        user_id: 用户ID
    
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
                "user_id": str(user_id)
            }
        }
        
        # 流式调用 graph
        answer = []
        async for chunk in graph.astream(input_state, config, stream_mode="messages"):
            message_obj, metadata = chunk
            langgraph_node = metadata.get("langgraph_node")
            if langgraph_node == "deal_with_results" and message_obj.content:
                content = message_obj.content
                answer.append(content)
                yield f"data: {content}\n\n"

        # 发送完成信号
        final_data = {"content": "", "done": True}
        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
        
        # 保存到数据库中
        full_answer = "".join(answer)
        logger.info(f"Stream completed. Saving full answer to DB for thread {thread_id}")
        conversation_manager.add_message(
            session_id=thread_id,
            user_id=user_id,
            message_role=MessageRole.ASSISTANT,
            message=full_answer
        )
        
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

    # 1. 预热会话数据（如果 Redis 中没有数据）
    conversation_manager.warmup_session_from_postgres(
        session_id=conversation_id,
        user_id=user.id,
        limit=50
    )

    # 2. 立即存储用户消息到多轮对话管理器
    conversation_manager.add_message(
        session_id=conversation_id,
        user_id=user.id,
        message_role=MessageRole.USER,
        message=chat_request.message
    )

    return StreamingResponse(
        astream_workflow_generator(
            chat_request.message, 
            conversation_id,
            user.id
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
        
        # 1. 预热会话数据（如果 Redis 中没有数据）
        conversation_manager.warmup_session_from_postgres(
            session_id=chat_request.conversation_id,
            user_id=user.id,
            limit=50
        )
        
        # 2. 立即存储用户消息到多轮对话管理器
        conversation_manager.add_message(
            session_id=chat_request.conversation_id,
            user_id=user.id,
            message_role=MessageRole.USER,
            message=chat_request.message
        )
        
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
        
        # 3. 存储AI回复到多轮对话管理器
        if response_content.strip():
            conversation_manager.add_message(
                session_id=chat_request.conversation_id,
                user_id=user.id,
                message_role=MessageRole.ASSISTANT,
                message=response_content
            )
        
        logger.info(f"Chat response generated: {response_content[:100]}...")
        
        return {"response": response_content}
        
    except Exception as e:
        logger.error(f"Error in chat endpoint:{e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/get_history/{conversation_id}")
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
        
        # 直接从 Redis 获取消息（因为发送消息时已经预热了）
        messages = conversation_manager.get_messages(
            session_id=conversation_id,
            user_id=user.id,
            limit=50
        )
        
        # 如果 Redis 中仍然没有数据，尝试从 PostgreSQL 获取（备用方案）
        if not messages:
            logger.info("No messages found in Redis, trying PostgreSQL")
            history_messages = conversation_manager.get_messages_from_postgres(
                session_id=conversation_id,
                limit=50
            )
            
            # 转换PostgreSQL消息格式
            messages = []
            for history in history_messages:
                messages.append({
                    "session_id": history.session_id,
                    "user_id": history.user_id,
                    "message_role": history.message_role,
                    "message": history.message,
                    "created_at": history.created_at.isoformat()
                })
        
        # 转换为前端需要的格式
        chat_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                # 从PostgreSQL获取的数据
                role = msg["message_role"]
                content = msg["message"]
            else:
                # 从Redis获取的数据
                role = msg.message_role
                content = msg.message
            
            chat_messages.append(Message(role=role, content=content))
        
        return ChatResponse(messages=chat_messages)
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")

@router.delete("/clear_history/{conversation_id}")
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
        
        # 使用多轮对话管理器清空会话
        success = conversation_manager.clear_session(
            session_id=conversation_id,
            user_id=user.id
        )
        
        if success:
            return {"message": "Chat history cleared successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear chat history")
        
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
