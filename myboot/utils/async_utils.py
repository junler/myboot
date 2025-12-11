#!/usr/bin/env python3
# -*- coding: utf-8
"""
异步执行工具模块
提供可复用的异步执行方法
"""

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Callable

from loguru import logger as loguru_logger

logger = loguru_logger.bind(name='async_utils')


class AsyncExecutor:
    """异步执行器，提供可复用的异步执行方法"""

    def __init__(self, max_workers: int = 4, executor_type: str = 'thread'):
        """
        初始化异步执行器
        
        Args:
            max_workers: 最大工作线程/进程数
            executor_type: 执行器类型，'thread' 或 'process'
        """
        self.max_workers = max_workers
        self.executor_type = executor_type
        self._executor = None
        self._loop = None

    @property
    def executor(self):
        """获取执行器实例"""
        if self._executor is None:
            if self.executor_type == 'thread':
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
            elif self.executor_type == 'process':
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            else:
                raise ValueError(f"不支持的执行器类型: {self.executor_type}")
        return self._executor

    @property
    def loop(self):
        """获取事件循环"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    async def run_in_background(self, func: Callable, *args, **kwargs) -> asyncio.Task:
        """
        在后台异步执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            asyncio.Task: 异步任务对象
        """
        task = asyncio.create_task(self._execute_func(func, *args, **kwargs))
        return task

    async def _execute_func(self, func: Callable, *args, task_name: str = None, **kwargs):
        """执行函数的内部方法"""
        try:
            # 使用提供的任务名称或函数名
            display_name = task_name if task_name else func.__name__
            # logger.info(f"开始执行后台任务: {display_name}")
            result = await self.loop.run_in_executor(
                self.executor,
                functools.partial(func, *args, **kwargs)
            )
            # logger.info(f"后台任务执行完成: {display_name}")
            return result
        except Exception as e:
            display_name = task_name if task_name else func.__name__
            # logger.error(f"后台任务执行失败: {display_name}, 错误: {e}", exc_info=True)
            raise

    def close(self):
        """关闭执行器，释放资源"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
            # logger.info("异步执行器已关闭")


# 全局异步执行器实例
_global_executor = None


def get_async_executor(max_workers: int = 4, executor_type: str = 'thread') -> AsyncExecutor:
    """
    获取全局异步执行器实例
    
    Args:
        max_workers: 最大工作线程/进程数
        executor_type: 执行器类型
        
    Returns:
        AsyncExecutor: 异步执行器实例
    """
    global _global_executor
    if _global_executor is None:
        _global_executor = AsyncExecutor(max_workers, executor_type)
    return _global_executor


def async_run(func: Callable, *args, **kwargs) -> asyncio.Task:
    """
    快速启动后台任务的便捷函数
    
    Args:
        func: 要执行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数，支持 task_name 用于日志显示
        
    Returns:
        asyncio.Task: 异步任务对象
    """
    executor = get_async_executor()
    # 从kwargs中提取task_name，如果没有则使用函数名
    task_name = kwargs.pop('task_name', None)
    display_name = task_name if task_name else func.__name__
    
    # 创建异步任务，确保在后台运行
    task = asyncio.create_task(executor._execute_func(func, *args, task_name=display_name, **kwargs))
    return task


# 装饰器：将同步函数转换为异步函数
def async_task(func: Callable) -> Callable:
    """
    装饰器：将同步函数包装为异步函数
    
    Usage:
        @async_task
        def my_sync_function():
            # 同步代码
            pass
            
        # 现在可以异步调用
        await my_sync_function()
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        executor = get_async_executor()
        return await executor._execute_func(func, *args, **kwargs)

    return wrapper


# 上下文管理器：自动管理执行器生命周期
class AsyncExecutorContext:
    """异步执行器上下文管理器"""

    def __init__(self, max_workers: int = 4, executor_type: str = 'thread'):
        self.max_workers = max_workers
        self.executor_type = executor_type
        self.executor = None

    async def __aenter__(self):
        self.executor = AsyncExecutor(self.max_workers, self.executor_type)
        return self.executor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.close()


# 清理函数
def cleanup_async_executor():
    """清理全局异步执行器"""
    global _global_executor
    if _global_executor:
        _global_executor.close()
        _global_executor = None
