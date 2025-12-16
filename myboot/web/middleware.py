"""
Web 中间件模块

提供类似 Spring Boot 的中间件功能
"""

import asyncio
import json
import time
from typing import Callable, List, Optional, Union, Pattern
import re

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import StreamingResponse


class Middleware:
    """中间件基类"""
    
    def __init__(self, middleware_class: type, **kwargs):
        """
        初始化中间件
        
        Args:
            middleware_class: 中间件类
            **kwargs: 中间件参数
        """
        self.middleware_class = middleware_class
        self.kwargs = kwargs


class FunctionMiddleware(BaseHTTPMiddleware):
    """函数中间件包装器
    
    将函数式中间件转换为 FastAPI 的 BaseHTTPMiddleware 类
    """
    
    def __init__(
        self,
        app,
        middleware_func: Callable,
        path_filter: Optional[Union[str, Pattern, List[str]]] = None,
        methods: Optional[List[str]] = None,
        condition: Optional[Callable] = None,
        order: int = 0,
        **kwargs
    ):
        """
        初始化函数中间件
        
        Args:
            app: FastAPI 应用实例
            middleware_func: 中间件函数，接收 (request, next_handler) 参数
            path_filter: 路径过滤，支持字符串、正则表达式或字符串列表
            methods: HTTP 方法过滤，如 ['GET', 'POST']
            condition: 条件函数，接收 request，返回 bool 决定是否执行中间件
            order: 执行顺序，数字越小越先执行
            **kwargs: 其他参数
        """
        super().__init__(app)
        self.middleware_func = middleware_func
        self.path_filter = path_filter
        self.methods = [m.upper() for m in methods] if methods else None
        self.condition = condition
        self.order = order
        self.kwargs = kwargs
        
        # 编译路径过滤正则表达式
        if path_filter:
            if isinstance(path_filter, str):
                # 将通配符转换为正则表达式
                pattern = path_filter.replace('*', '.*').replace('?', '.')
                self.path_pattern = re.compile(f'^{pattern}$')
            elif isinstance(path_filter, list):
                patterns = [p.replace('*', '.*').replace('?', '.') for p in path_filter]
                self.path_pattern = re.compile(f"^({'|'.join(patterns)})$")
            elif isinstance(path_filter, Pattern):
                self.path_pattern = path_filter
            else:
                self.path_pattern = None
        else:
            self.path_pattern = None
    
    def _should_process(self, request: Request) -> bool:
        """判断是否应该处理该请求"""
        # 检查路径过滤
        if self.path_pattern:
            if not self.path_pattern.match(request.url.path):
                return False
        
        # 检查 HTTP 方法过滤
        if self.methods:
            if request.method not in self.methods:
                return False
        
        # 检查条件函数
        if self.condition:
            try:
                if not self.condition(request):
                    return False
            except Exception:
                # 条件函数执行失败时跳过该中间件
                return False
        
        return True
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """执行中间件逻辑"""
        # 如果不符合过滤条件，直接跳过
        if not self._should_process(request):
            return await call_next(request)
        
        # 创建异步 next_handler 包装器
        async def async_next_handler(req: Request) -> Response:
            return await call_next(req)
        
        # 检查中间件函数是否是异步函数
        if asyncio.iscoroutinefunction(self.middleware_func):
            # 异步中间件（推荐方式）
            response = await self.middleware_func(request, async_next_handler)
        else:
            # 同步中间件支持（为了向后兼容）
            # 注意：同步中间件接收的 next_handler 会返回协程，需要手动处理
            # 建议使用异步中间件以获得更好的性能
            def sync_wrapper(req: Request):
                """同步包装器：返回协程对象，需要调用者手动 await"""
                return call_next(req)
            
            # 调用同步中间件函数
            result = self.middleware_func(request, sync_wrapper)
            
            # 处理返回值
            if asyncio.iscoroutine(result):
                # 如果返回协程，等待它
                response = await result
            elif isinstance(result, (Response, StreamingResponse)):
                # 如果已经是 Response，直接使用
                response = result
            else:
                # 其他情况，尝试转换
                from fastapi.responses import JSONResponse
                response = JSONResponse(content=result)
        
        # 确保返回 Response 对象
        if not isinstance(response, (Response, StreamingResponse)):
            # 如果返回的不是 Response，尝试转换为 Response
            from fastapi.responses import JSONResponse
            response = JSONResponse(content=response)
        
        return response


class ResponseFormatterMiddleware(BaseHTTPMiddleware):
    """响应格式化中间件
    
    自动将路由返回的数据包装为统一的 REST API 格式：
    {
        "success": true,
        "code": 200,
        "message": "操作成功",
        "data": {...}
    }
    """
    
    def __init__(
        self,
        app,
        exclude_paths: Optional[List[str]] = None,
        auto_wrap: bool = True
    ):
        """
        初始化响应格式化中间件
        
        Args:
            app: FastAPI 应用实例
            exclude_paths: 排除的路径列表（这些路径不进行格式化）
            auto_wrap: 是否自动包装响应
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or []
        self.auto_wrap = auto_wrap
        
        # 默认排除的路径（系统路径和文档路径）
        default_excludes = [
            "/docs",
            "/openapi.json",
            "/redoc",
            "/health",
            "/health/ready",
            "/health/live"
        ]
        
        # 合并排除路径
        self.exclude_paths = list(set(self.exclude_paths + default_excludes))
    
    def _should_format(self, request: Request) -> bool:
        """判断是否应该格式化响应"""
        if not self.auto_wrap:
            return False
        
        path = request.url.path
        
        # 检查是否在排除列表中
        for exclude_path in self.exclude_paths:
            if path == exclude_path or path.startswith(exclude_path + "/"):
                return False
        
        return True
    
    def _is_formatted(self, content: dict) -> bool:
        """检查响应是否已经是统一格式"""
        if not isinstance(content, dict):
            return False
        
        # 检查是否包含统一格式的必须字段（message 和 data 可选）
        required_fields = {"success", "code"}
        return all(field in content for field in required_fields)
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """处理请求并格式化响应"""
        response = await call_next(request)
        
        # 如果不需要格式化，直接返回
        if not self._should_format(request):
            return response
        
        # 检查响应类型
        # FastAPI 可能返回 JSONResponse、StreamingResponse 或 _StreamingResponse
        # 我们需要处理所有可能包含 JSON 内容的响应
        
        # 检查是否是 JSONResponse
        is_json_response = isinstance(response, JSONResponse)
        
        # 如果不是 JSONResponse，检查是否可能是 JSON 响应
        if not is_json_response:
            # 检查 media_type 是否为 JSON
            if hasattr(response, 'media_type') and response.media_type:
                media_type_lower = response.media_type.lower()
                if 'json' in media_type_lower:
                    is_json_response = True
                else:
                    return response
            elif isinstance(response, (StreamingResponse, Response)):
                # StreamingResponse 或 Response 如果没有设置 media_type，尝试读取并判断
                # 对于未知类型的响应，我们尝试读取内容并判断是否为 JSON
                # 允许继续处理，尝试读取响应体
                pass
            else:
                # 如果既不是 JSONResponse 也没有 media_type，跳过
                return response
        
        # 检查响应是否有 body_iterator（所有响应都应该有）
        if not hasattr(response, 'body_iterator'):
            return response
        
        # 获取响应内容
        try:
            # 读取响应体 - 使用正确的方式处理流式响应
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # 如果没有响应体，直接返回空响应
            if not body:
                return response
            
            # 解析 JSON
            try:
                content = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                # 如果不是有效的 JSON，返回原始响应
                return response
            
            # 如果已经是统一格式，重新构建响应并返回
            if self._is_formatted(content):
                # 移除 Content-Length，让服务器重新计算
                headers = dict(response.headers)
                headers.pop('content-length', None)
                return JSONResponse(
                    content=content,
                    status_code=response.status_code,
                    headers=headers
                )
            
            # 根据状态码判断成功或失败
            status_code = response.status_code
            is_success = 200 <= status_code < 400
            
            # 自动包装响应
            from myboot.web.response import ResponseWrapper
            
            if is_success:
                # 成功响应
                formatted_content = ResponseWrapper.success(
                    data=content,
                    message="操作成功",
                    code=status_code
                )
            else:
                # 错误响应（通常由异常处理器处理，但以防万一）
                message = content.get("message", "操作失败") if isinstance(content, dict) else "操作失败"
                formatted_content = ResponseWrapper.error(
                    message=message,
                    code=status_code,
                    data=content if isinstance(content, dict) else {"error": str(content)}
                )
            
            # 移除 Content-Length，让服务器重新计算新的响应长度
            headers = dict(response.headers)
            headers.pop('content-length', None)
            
            return JSONResponse(
                content=formatted_content,
                status_code=status_code,
                headers=headers
            )
            
        except (AttributeError, UnicodeDecodeError, StopAsyncIteration) as e:
            # 如果无法解析，返回原始响应
            # 这里可以记录日志，但为了不影响正常响应，静默处理
            return response
        except Exception as e:
            # 捕获所有其他异常，避免中间件崩溃
            # 在生产环境中可以记录日志
            return response
