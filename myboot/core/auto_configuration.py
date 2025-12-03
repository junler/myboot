"""
自动配置模块

实现约定优于配置的设计理念，提供自动发现和配置功能
"""

import os
import re
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type, Any, Optional, Callable
from functools import wraps

from loguru import logger as loguru_logger

logger = loguru_logger.bind(name=__name__)


def _camel_to_snake(name: str) -> str:
    """
    将驼峰命名转换为下划线分隔的小写形式
    
    Args:
        name: 类名（驼峰命名）
    
    Returns:
        下划线分隔的小写字符串
    """
    # 在大写字母前插入下划线（除了第一个字符）
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    # 处理连续大写字母的情况（如 HTTPClient）
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    # 转换为小写
    return s2.lower()


def _find_project_root() -> str:
    """查找项目根目录"""
    # 从当前文件所在目录开始向上查找
    current_dir = Path(__file__).parent.absolute()
    
    # 向上查找，直到找到包含 pyproject.toml 或 requirements.txt 的目录
    while current_dir.parent != current_dir:
        if (current_dir / 'pyproject.toml').exists() or (current_dir / 'requirements.txt').exists():
            return str(current_dir)
        current_dir = current_dir.parent
    
    # 如果没找到，返回当前工作目录
    return os.getcwd()


class AutoConfigurationManager:
    """自动配置管理器"""
    
    def __init__(self, app_root: str = None):
        self.app_root = app_root or _find_project_root()
        self.discovered_components = {
            'routes': [],
            'jobs': [],
            'middleware': [],
            'services': [],
            'models': [],
            'clients': [],
            'rest_controllers': []
        }
        self.auto_configured = False
    
    def auto_discover(self, package_name: str = "app") -> None:
        """自动发现应用组件"""
        logger.info(f"开始自动发现 {package_name} 包中的组件...")
        logger.debug(f"扫描根目录: {self.app_root}")
        
        try:
            # 获取包路径
            package_path = Path(self.app_root) / package_name
            logger.debug(f"尝试扫描路径: {package_path}")
            if not package_path.exists():
                logger.warning(f"包路径不存在: {package_path}")
                return
            
            # 递归扫描包
            self._scan_package(package_path, package_name)
            
            logger.debug(f"自动发现完成，发现组件: {self.discovered_components}")
            self.auto_configured = True
            
        except Exception as e:
            logger.error(f"自动发现失败: {e}")
    
    def _scan_package(self, package_path: Path, package_name: str) -> None:
        """递归扫描包"""
        for item in package_path.iterdir():
            if item.is_file() and item.name.endswith('.py') and not item.name.startswith('__'):
                # 扫描 Python 文件
                module_name = f"{package_name}.{item.stem}"
                self._scan_module(module_name)
            elif item.is_dir() and not item.name.startswith('__'):
                # 递归扫描子包
                sub_package_name = f"{package_name}.{item.name}"
                self._scan_package(item, sub_package_name)
    
    def _scan_module(self, module_name: str) -> None:
        """扫描模块中的组件"""
        try:
            module = importlib.import_module(module_name)
            
            # 扫描模块中的所有对象
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj):
                    self._check_function(obj, module_name)
                elif inspect.isclass(obj):
                    self._check_class(obj, module_name)
                    
        except Exception as e:
            logger.debug(f"扫描模块 {module_name} 失败: {e}")
    
    def _check_function(self, func: Callable, module_name: str) -> None:
        """检查函数是否是装饰的组件"""
        if hasattr(func, '__myboot_route__'):
            self.discovered_components['routes'].append({
                'function': func,
                'module': module_name,
                'type': 'function_route'
            })
        elif hasattr(func, '__myboot_job__'):
            self.discovered_components['jobs'].append({
                'function': func,
                'module': module_name,
                'type': 'function_job'
            })
        elif hasattr(func, '__myboot_middleware__'):
            self.discovered_components['middleware'].append({
                'function': func,
                'module': module_name,
                'type': 'function_middleware'
            })
    
    def _check_class(self, cls: Type, module_name: str) -> None:
        """检查类是否是装饰的组件"""
        # 检查类中的方法是否有任务装饰器
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(method, '__myboot_job__'):
                # 发现类方法中的任务
                self.discovered_components['jobs'].append({
                    'class': cls,
                    'method': method,
                    'method_name': name,
                    'module': module_name,
                    'type': 'class_method_job'
                })
        
        # 检查类本身的装饰器
        if hasattr(cls, '__myboot_rest_controller__'):
            self.discovered_components['rest_controllers'].append({
                'class': cls,
                'module': module_name,
                'type': 'rest_controller'
            })
        elif hasattr(cls, '__myboot_service__'):
            self.discovered_components['services'].append({
                'class': cls,
                'module': module_name,
                'type': 'service'
            })
        elif hasattr(cls, '__myboot_model__'):
            self.discovered_components['models'].append({
                'class': cls,
                'module': module_name,
                'type': 'model'
            })
        elif hasattr(cls, '__myboot_client__'):
            self.discovered_components['clients'].append({
                'class': cls,
                'module': module_name,
                'type': 'client'
            })
        elif hasattr(cls, '__myboot_route__'):
            self.discovered_components['routes'].append({
                'class': cls,
                'module': module_name,
                'type': 'class_route'
            })
    
    def apply_auto_configuration(self, app) -> None:
        """应用自动配置"""
        if not self.auto_configured:
            logger.warning("自动发现未完成，跳过自动配置")
            return
        
        logger.debug("开始应用自动配置...")
        
        # 自动注册各种组件
        # 注意：服务注册需要在任务注册之前，以便任务可以使用依赖注入的服务
        self._auto_register_rest_controllers(app)
        self._auto_register_routes(app)
        self._auto_register_services(app)  # 先注册服务，支持依赖注入
        self._auto_register_models(app)
        self._auto_register_clients(app)
        self._auto_register_jobs(app)  # 再注册任务，可以使用已注册的服务
        self._auto_register_middleware(app)
        
        logger.debug("自动配置应用完成")
    
    def _auto_register_rest_controllers(self, app) -> None:
        """自动注册 REST 控制器
        
        只注册显式使用 @get、@post 等装饰器的方法，不自动根据方法名生成路由
        """
        import inspect as inspect_module
        
        for controller_info in self.discovered_components['rest_controllers']:
            try:
                cls = controller_info['class']
                controller_config = getattr(cls, '__myboot_rest_controller__')
                base_path = controller_config['base_path']
                base_kwargs = controller_config.get('kwargs', {})
                
                # 创建控制器实例
                instance = cls()
                
                # 检查类中的所有方法，只处理显式使用路由装饰器的方法
                for method_name, method in inspect_module.getmembers(
                    instance, 
                    predicate=lambda x: inspect_module.ismethod(x) and not x.__name__.startswith('_')
                ):
                    # 只处理有 __myboot_route__ 属性的方法（即显式使用 @get、@post 等装饰器的方法）
                    if hasattr(method, '__myboot_route__'):
                        route_config = getattr(method, '__myboot_route__')
                        method_path = route_config['path']
                        methods = route_config.get('methods', ['GET'])
                        route_kwargs = {**base_kwargs, **route_config.get('kwargs', {})}
                        
                        # 合并基础路径和方法路径
                        # 如果方法路径是绝对路径（以 // 开头），则直接使用（去掉一个 /）
                        # 否则，将方法路径追加到基础路径
                        if method_path.startswith('//'):
                            # 绝对路径，去掉一个 / 后使用
                            full_path = method_path[1:]
                        elif method_path.startswith('/'):
                            # 以 / 开头但非绝对路径，去掉开头的 / 后追加到基础路径
                            full_path = f"{base_path}{method_path}".replace('//', '/')
                        else:
                            # 相对路径，追加到基础路径
                            full_path = f"{base_path}/{method_path}".replace('//', '/')
                        
                        # 注册路由
                        app.add_route(
                            path=full_path,
                            handler=method,
                            methods=methods,
                            **route_kwargs
                        )
                        
                        logger.debug(f"自动注册 REST 路由: {methods} {full_path} -> {controller_info['module']}.{cls.__name__}.{method_name}")
                
                logger.info(f"自动注册 REST 控制器: {controller_info['module']}.{cls.__name__}")
            except Exception as e:
                logger.error(f"自动注册 REST 控制器失败 {controller_info['module']}: {e}")
    
    def _auto_register_routes(self, app) -> None:
        """自动注册路由"""
        for route_info in self.discovered_components['routes']:
            try:
                if route_info['type'] == 'function_route':
                    # 函数路由
                    func = route_info['function']
                    route_config = getattr(func, '__myboot_route__')
                    app.add_route(
                        path=route_config['path'],
                        handler=func,
                        methods=route_config.get('methods', ['GET']),
                        **route_config.get('kwargs', {})
                    )
                elif route_info['type'] == 'class_route':
                    # 类路由
                    cls = route_info['class']
                    route_config = getattr(cls, '__myboot_route__')
                    instance = cls()
                    for method_name, method in inspect.getmembers(instance, predicate=inspect.ismethod):
                        if hasattr(method, '__myboot_route__'):
                            method_config = getattr(method, '__myboot_route__')
                            app.add_route(
                                path=method_config['path'],
                                handler=method,
                                methods=method_config.get('methods', ['GET']),
                                **method_config.get('kwargs', {})
                            )
                            logger.debug(f"自动注册路由: {route_info['module']}.{cls.__name__}.{method_name}")
                
                logger.debug(f"自动注册路由: {route_info['module']}.{route_info['function'].__name__}")
            except Exception as e:
                logger.error(f"自动注册路由失败 {route_info['module']}: {e}")
    
    def _is_job_enabled(self, _func, job_config: dict) -> bool:
        """
        检查任务是否启用
        
        Args:
            _func: 任务函数（保留用于未来扩展，如从函数名读取配置）
            job_config: 任务配置
            
        Returns:
            bool: 任务是否启用
        """
        # 检查装饰器中直接指定的 enabled
        enabled = job_config.get('enabled')
        if enabled is not None:
            # 支持布尔值和字符串
            if isinstance(enabled, bool):
                return enabled
            if isinstance(enabled, str):
                return enabled.lower() in ('true', '1', 'yes', 'on', 'enabled')
            return bool(enabled)
        
        # 默认启用
        return True

    def _get_class_instance(self, cls: Type, app) -> Any:
        """
        获取类实例，支持依赖注入
        
        如果类有 @service 装饰器，尝试从 DI 容器或 app.services 获取实例
        否则直接实例化
        
        Args:
            cls: 类
            app: 应用实例
            
        Returns:
            类实例
        """
        # 检查类是否有 @service 装饰器
        if hasattr(cls, '__myboot_service__'):
            service_config = getattr(cls, '__myboot_service__')
            service_name = service_config.get('name', _camel_to_snake(cls.__name__))
            
            # 方法1: 尝试从 DI 容器获取（如果容器已构建）
            if hasattr(app, 'di_container'):
                di_container = app.di_container
                try:
                    if di_container.has_service(service_name):
                        instance = di_container.get_service(service_name)
                        logger.debug(f"从 DI 容器获取服务实例: {service_name}")
                        return instance
                except Exception as e:
                    logger.debug(f"从 DI 容器获取服务失败 {service_name}: {e}")
            
            # 方法2: 尝试从 app.services 获取（服务注册后会在那里）
            if hasattr(app, 'services') and service_name in app.services:
                instance = app.services[service_name]
                logger.debug(f"从 app.services 获取服务实例: {service_name}")
                return instance
            
            # 方法3: 如果都失败，尝试直接实例化（可能会有依赖注入问题）
            logger.warning(f"服务 '{service_name}' 未在容器中注册，尝试直接实例化（可能缺少依赖注入）")
        
        # 没有 @service 装饰器或获取失败，直接实例化
        return cls()
    
    def _auto_register_jobs(self, app) -> None:
        """自动注册任务"""
        for job_info in self.discovered_components['jobs']:
            try:
                # 处理类方法任务
                if job_info['type'] == 'class_method_job':
                    cls = job_info['class']
                    method = job_info['method']
                    method_name = job_info['method_name']
                    job_config = getattr(method, '__myboot_job__')
                    
                    # 检查任务是否启用
                    if not self._is_job_enabled(method, job_config):
                        logger.info(f"任务已禁用，跳过注册: {cls.__name__}.{method_name} ({job_info['module']})")
                        continue
                    
                    # 创建类实例并绑定方法（支持依赖注入）
                    try:
                        instance = self._get_class_instance(cls, app)
                        bound_method = getattr(instance, method_name)
                    except Exception as e:
                        logger.error(f"创建类实例失败 {cls.__name__}: {e}", exc_info=True)
                        continue
                    
                    # 注册绑定的方法
                    if job_config['type'] == 'cron':
                        app.scheduler.add_cron_job(
                            func=bound_method,
                            cron=job_config['cron'],
                            **job_config.get('kwargs', {})
                        )
                    elif job_config['type'] == 'interval':
                        app.scheduler.add_interval_job(
                            func=bound_method,
                            interval=job_config['interval'],
                            **job_config.get('kwargs', {})
                        )
                    elif job_config['type'] == 'once':
                        app.scheduler.add_date_job(
                            func=bound_method,
                            run_date=job_config['run_date'],
                            **job_config.get('kwargs', {})
                        )
                    
                    logger.info(f"自动注册任务（类方法）: {cls.__name__}.{method_name} ({job_info['module']})")
                
                # 处理函数任务
                elif job_info['type'] == 'function_job':
                    func = job_info['function']
                    job_config = getattr(func, '__myboot_job__')
                    
                    # 检查任务是否启用
                    if not self._is_job_enabled(func, job_config):
                        logger.info(f"任务已禁用，跳过注册: {func.__name__} ({job_info['module']})")
                        continue
                    
                    if job_config['type'] == 'cron':
                        app.scheduler.add_cron_job(
                            func=func,
                            cron=job_config['cron'],
                            **job_config.get('kwargs', {})
                        )
                    elif job_config['type'] == 'interval':
                        app.scheduler.add_interval_job(
                            func=func,
                            interval=job_config['interval'],
                            **job_config.get('kwargs', {})
                        )
                    elif job_config['type'] == 'once':
                        # 一次性任务的处理
                        app.scheduler.add_date_job(
                            func=func,
                            run_date=job_config['run_date'],
                            **job_config.get('kwargs', {})
                        )
                    
                    logger.info(f"自动注册任务: {func.__name__} ({job_info['module']})")
            except Exception as e:
                logger.error(f"自动注册任务失败 {job_info.get('module', 'unknown')}: {e}", exc_info=True)
    
    def _auto_register_middleware(self, app) -> None:
        """自动注册中间件"""
        from myboot.web.middleware import FunctionMiddleware
        
        if not self.discovered_components['middleware']:
            return
        
        # 按照 order 排序中间件
        middleware_list = []
        for middleware_info in self.discovered_components['middleware']:
            try:
                func = middleware_info['function']
                middleware_config = getattr(func, '__myboot_middleware__')
                order = middleware_config.get('order', 0)
                middleware_list.append({
                    'func': func,
                    'config': middleware_config,
                    'order': order,
                    'module': middleware_info['module']
                })
            except Exception as e:
                logger.error(f"解析中间件配置失败 {middleware_info['module']}: {e}")
        
        # 按 order 排序
        middleware_list.sort(key=lambda x: x['order'])
        
        # 注册中间件（FastAPI 的中间件是后进先出的，所以需要反向注册）
        for middleware_item in reversed(middleware_list):
            try:
                func = middleware_item['func']
                config = middleware_item['config']
                module = middleware_item['module']
                
                # 创建动态中间件类，包装 FunctionMiddleware
                middleware_name = config.get('name', func.__name__)
                
                # 使用闭包捕获变量
                def make_init(middleware_func, middleware_config):
                    def __init__(self, app):
                        FunctionMiddleware.__init__(
                            self,
                            app=app,
                            middleware_func=middleware_func,
                            path_filter=middleware_config.get('path_filter'),
                            methods=middleware_config.get('methods'),
                            condition=middleware_config.get('condition'),
                            order=middleware_config.get('order', 0),
                            **middleware_config.get('kwargs', {})
                        )
                    return __init__
                
                # 动态创建中间件类
                middleware_class = type(
                    f"Middleware_{middleware_name}",
                    (FunctionMiddleware,),
                    {'__init__': make_init(func, config)}
                )
                
                # 添加到 FastAPI 应用
                app._fastapi_app.add_middleware(middleware_class)
                
                logger.info(
                    f"自动注册中间件: '{middleware_name}' "
                    f"(order={config.get('order', 0)}, "
                    f"module={module})"
                )
            except Exception as e:
                logger.error(f"自动注册中间件失败 {middleware_item['module']}: {e}", exc_info=True)
        
        logger.info(f"成功注册 {len(middleware_list)} 个中间件")
    
    def _auto_register_services(self, app) -> None:
        """自动注册服务（支持依赖注入）"""
        try:
            from myboot.core.di import DependencyContainer
            
            # 检查应用是否有依赖注入容器
            if not hasattr(app, 'di_container'):
                app.di_container = DependencyContainer()
            
            di_container = app.di_container
            
            # 第一步：注册所有服务到容器（不创建实例）
            for service_info in self.discovered_components['services']:
                try:
                    cls = service_info['class']
                    service_config = getattr(cls, '__myboot_service__')
                    service_name = service_config.get('name', cls.__name__.lower())
                    
                    # 获取服务作用域（默认单例）
                    scope = service_config.get('scope', 'singleton')
                    
                    # 注册到依赖注入容器
                    di_container.register_service(
                        service_class=cls,
                        service_name=service_name,
                        scope=scope,
                        config=service_config
                    )
                    
                    logger.debug(f"已注册服务到容器: '{service_name}' ({service_info['module']}.{cls.__name__})")
                except Exception as e:
                    logger.error(f"注册服务到容器失败 {service_info['module']}: {e}", exc_info=True)
            
            # 第二步：构建依赖注入容器
            try:
                di_container.build_container()
                logger.info("依赖注入容器构建成功")
            except Exception as e:
                logger.error(f"构建依赖注入容器失败: {e}", exc_info=True)
                # 如果依赖注入失败，回退到原来的方式
                logger.warning("回退到传统服务注册方式（无依赖注入）")
                self._auto_register_services_fallback(app)
                return
            
            # 第三步：获取所有服务实例并注册到应用上下文
            for service_info in self.discovered_components['services']:
                try:
                    cls = service_info['class']
                    service_config = getattr(cls, '__myboot_service__')
                    service_name = service_config.get('name', cls.__name__.lower())
                    
                    # 从容器获取服务实例（自动注入依赖）
                    instance = di_container.get_service(service_name)
                    app.services[service_name] = instance
                    
                    # 确保当前应用实例已注册
                    from myboot.core.application import _current_app
                    if _current_app != app:
                        # 更新当前应用实例
                        import myboot.core.application
                        myboot.core.application._current_app = app
                    
                    logger.info(f"自动注册服务（依赖注入）: '{service_name}' ({service_info['module']}.{cls.__name__})")
                except Exception as e:
                    logger.error(f"获取服务实例失败 {service_info['module']}: {e}", exc_info=True)
                    # 如果获取失败，尝试直接实例化（无依赖注入）
                    try:
                        cls = service_info['class']
                        service_config = getattr(cls, '__myboot_service__')
                        service_name = service_config.get('name', cls.__name__.lower())
                        instance = cls()
                        app.services[service_name] = instance
                        logger.warning(f"服务 '{service_name}' 使用传统方式实例化（无依赖注入）")
                    except Exception as fallback_error:
                        logger.error(f"服务 '{service_name}' 实例化失败: {fallback_error}", exc_info=True)
        
        except ImportError:
            # 如果 dependency_injector 未安装，使用传统方式
            logger.warning("dependency_injector 未安装，使用传统服务注册方式")
            self._auto_register_services_fallback(app)
        except Exception as e:
            logger.error(f"依赖注入服务注册失败: {e}", exc_info=True)
            # 回退到传统方式
            self._auto_register_services_fallback(app)
    
    def _auto_register_services_fallback(self, app) -> None:
        """传统服务注册方式（无依赖注入）"""
        for service_info in self.discovered_components['services']:
            try:
                cls = service_info['class']
                service_config = getattr(cls, '__myboot_service__')
                
                # 创建服务实例并注册到应用上下文
                instance = cls()
                service_name = service_config.get('name', cls.__name__.lower())
                app.services[service_name] = instance
                
                # 确保当前应用实例已注册
                from myboot.core.application import _current_app
                if _current_app != app:
                    # 更新当前应用实例
                    import myboot.core.application
                    myboot.core.application._current_app = app
                
                logger.info(f"自动注册服务: '{service_name}' ({service_info['module']}.{cls.__name__})")
            except Exception as e:
                logger.error(f"自动注册服务失败 {service_info['module']}: {e}", exc_info=True)
    
    def _auto_register_models(self, app) -> None:
        """自动注册模型"""
        for model_info in self.discovered_components['models']:
            try:
                cls = model_info['class']
                model_config = getattr(cls, '__myboot_model__')
                
                # 注册模型到应用上下文
                model_name = model_config.get('name', cls.__name__.lower())
                app.models[model_name] = cls
                
                logger.info(f"自动注册模型: {model_info['module']}")
            except Exception as e:
                logger.error(f"自动注册模型失败 {model_info['module']}: {e}")
    
    def _auto_register_clients(self, app) -> None:
        """自动注册客户端"""
        for client_info in self.discovered_components['clients']:
            try:
                cls = client_info['class']
                client_config = getattr(cls, '__myboot_client__')
                
                # 创建客户端实例并注册到应用上下文
                instance = cls()
                client_name = client_config.get('name', cls.__name__.lower())
                app.clients[client_name] = instance
                
                logger.info(f"自动注册客户端: '{client_name}' ({client_info['module']}.{cls.__name__})")
            except Exception as e:
                logger.error(f"自动注册客户端失败 {client_info['module']}: {e}")


# 全局自动配置管理器实例
_auto_configuration_manager = AutoConfigurationManager()


def auto_discover(package_name: str = "app") -> None:
    """自动发现应用组件"""
    _auto_configuration_manager.auto_discover(package_name)


def apply_auto_configuration(app) -> None:
    """应用自动配置"""
    _auto_configuration_manager.apply_auto_configuration(app)
