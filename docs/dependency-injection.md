# 依赖注入使用指南

MyBoot 框架提供了基于 `dependency_injector` 的自动依赖注入功能，让您可以轻松管理服务之间的依赖关系，无需手动获取和传递依赖。

## 目录

- [快速开始](#快速开始)
- [基本用法](#基本用法)
  - [声明依赖](#1-声明依赖)
  - [服务命名规则](#2-服务命名规则)
  - [多级依赖](#3-多级依赖)
  - [可选依赖](#4-可选依赖)
  - [Client 依赖注入](#5-client-依赖注入)
  - [Component 组件](#6-component-组件)
- [高级特性](#高级特性)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

## 快速开始

### 安装依赖

确保已安装 `dependency_injector`：

```bash
pip install dependency-injector
```

### 基本示例

```python
from myboot.core.decorators import service

@service()
class UserService:
    """用户服务"""
    def __init__(self):
        self.users = {}

    def get_user(self, user_id: int):
        return self.users.get(user_id)

@service()
class EmailService:
    """邮件服务"""
    def send_email(self, to: str, subject: str):
        print(f"发送邮件到 {to}: {subject}")

@service()
class OrderService:
    """订单服务 - 自动注入 UserService 和 EmailService"""
    def __init__(self, user_service: UserService, email_service: EmailService):
        self.user_service = user_service
        self.email_service = email_service

    def create_order(self, user_id: int, product: str):
        user = self.user_service.get_user(user_id)
        self.email_service.send_email(user['email'], "订单创建", f"您的订单 {product} 已创建")
```

框架会自动：

1. 检测 `OrderService` 的依赖（`UserService` 和 `EmailService`）
2. 按正确的顺序初始化服务
3. 自动注入依赖到 `OrderService` 的构造函数

## 基本用法

### 1. 声明依赖

通过类型注解声明依赖是最简单的方式：

```python
@service()
class ProductService:
    def __init__(self, user_service: UserService, cache_service: CacheService):
        self.user_service = user_service
        self.cache_service = cache_service
```

框架会自动：

- 从类型注解中识别依赖的服务类
- 将类名转换为服务名（如 `UserService` → `user_service`）
- 自动注入对应的服务实例

### 2. 服务命名规则

服务名称遵循以下规则：

- **默认命名**：类名自动转换为下划线分隔的小写形式

  - `UserService` → `user_service`
  - `EmailService` → `email_service`
  - `DatabaseClient` → `database_client`

- **自定义命名**：通过装饰器参数指定
  ```python
  @service('custom_user_service')
  class UserService:
      pass
  ```

### 3. 多级依赖

支持多级依赖，框架会自动处理依赖顺序：

```python
@service()
class DatabaseClient:
    def __init__(self):
        self.connection = None

@service()
class UserRepository:
    def __init__(self, db: DatabaseClient):
        self.db = db

@service()
class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
```

依赖顺序：`DatabaseClient` → `UserRepository` → `UserService`

### 4. 可选依赖

使用 `Optional` 类型注解声明可选依赖：

```python
from typing import Optional

@service()
class CacheService:
    pass

@service()
class ProductService:
    # cache_service 是可选的，如果不存在则为 None
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service
        if self.cache_service:
            # 使用缓存服务
            pass
```

### 5. Client 依赖注入

除了 Service 之间的依赖注入，框架还支持将 Client 注入到 Controller 或 Service 中：

```python
from myboot.core.decorators import client, service, rest_controller, get

@client()
class HttpClient:
    """HTTP 客户端"""
    def request(self, url: str):
        return {"url": url}

@client(name="redis_client")  # 自定义名称
class RedisClient:
    """Redis 客户端"""
    def get(self, key: str):
        return None

@service()
class UserService:
    """注入 Client 到 Service"""
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

@rest_controller("/api")
class UserController:
    """注入 Client 和 Service 到 Controller"""
    def __init__(self, user_service: UserService, redis_client: RedisClient):
        self.user_service = user_service
        self.redis_client = redis_client

    @get("/users")
    def list_users(self):
        return []
```

#### Client 命名规则

- **默认命名**：类名自动转换为下划线形式

  - `HttpClient` → `http_client`
  - `RedisClient` → `redis_client`

- **自定义命名**：通过装饰器参数指定
  ```python
  @client(name="my_redis")
  class RedisClient:
      pass
  ```

#### Client 查找方式

框架支持多种方式查找 Client 依赖：

```python
@client(name="my_http")  # 自定义名称
class HttpClient:
    pass

@rest_controller("/api")
class MyController:
    # 以下方式都可以成功注入：

    # 方式1：按自定义名称（参数名匹配）
    def __init__(self, my_http: HttpClient):
        pass

    # 方式2：按自动转换名称
    def __init__(self, http_client: HttpClient):
        pass

    # 方式3：按类型匹配（参数名任意）
    def __init__(self, client: HttpClient):
        pass

    # 方式4：显式指定名称
    def __init__(self, x: Provide['my_http']):
        pass
```

### 6. Component 组件

`@component` 装饰器用于注册通用组件，支持依赖注入。它可用于任意需要托管的类（工具类、配置类、包含定时任务的类等）。

#### 基本用法

```python
from myboot.core.decorators import component

@component()
class EmailHelper:
    """邮件工具类"""
    def send(self, to: str, content: str):
        print(f"发送邮件到 {to}: {content}")
```

#### 带依赖注入

```python
from myboot.core.decorators import component, client

@client()
class SmtpClient:
    def send_mail(self, to: str, subject: str, body: str):
        pass

@component(name='email_helper')
class EmailHelper:
    """带依赖注入的组件"""
    def __init__(self, smtp_client: SmtpClient):
        self.smtp = smtp_client
    
    def send(self, to: str, subject: str, body: str):
        self.smtp.send_mail(to, subject, body)
```

#### 包含定时任务的组件

**重要**：定时任务（`@cron`、`@interval`、`@once`）**必须**在 `@component` 装饰的类中定义。这是定义定时任务的唯一方式，不再支持模块级函数或 `@service` 类中的定时任务。

```python
from myboot.core.decorators import component, service, cron, interval

@service()
class DataService:
    def sync(self):
        print("同步数据...")
    
    def health_check(self):
        print("健康检查...")

@component()
class DataSyncJobs:
    """数据同步任务集合 - 自动注入 DataService"""
    
    def __init__(self, data_service: DataService):
        self.data_service = data_service
    
    @cron("0 2 * * *")  # 每天凌晨 2 点
    def sync_daily_data(self):
        """每日数据同步"""
        self.data_service.sync()
    
    @interval(hours=1)  # 每小时
    def check_data_health(self):
        """数据健康检查"""
        self.data_service.health_check()
```

**注意**：
- 定时任务方法会在组件注册时自动扫描并注册到调度器
- 组件支持依赖注入，可以在构造函数中注入所需的服务

#### Component 配置选项

```python
@component(
    name='my_component',    # 组件名称，默认使用类名的 snake_case
    scope='singleton',      # 生命周期：'singleton'（默认）或 'prototype'
    lazy=False,             # 是否懒加载
    primary=False           # 当按类型获取有多个匹配时，是否为首选
)
class MyComponent:
    pass
```

#### 从容器获取组件

```python
from myboot.core.application import app

# 方式1：通过 container 获取
email_helper = app().container.get('email_helper')

# 方式2：通过 Application 直接获取
email_helper = app().get_component('email_helper')

# 方式3：依赖注入（推荐）
@component()
class NotificationService:
    def __init__(self, email_helper: EmailHelper):
        self.email_helper = email_helper
```

## 高级特性

### 1. 显式指定服务名

如果服务名与类名转换规则不匹配，可以使用 `Provide` 类型提示：

```python
from myboot.core.di import Provide

@service('custom_user_service')
class UserService:
    pass

@service()
class OrderService:
    def __init__(self, user_service: Provide['custom_user_service']):
        self.user_service = user_service
```

### 2. 服务生命周期

通过 `scope` 参数控制服务的生命周期：

```python
# 单例模式（默认）
@service(scope='singleton')
class UserService:
    pass

# 工厂模式（每次创建新实例）
@service(scope='factory')
class TaskService:
    pass
```

### 3. 循环依赖检测

框架会自动检测循环依赖并抛出清晰的错误：

```python
@service()
class ServiceA:
    def __init__(self, service_b: ServiceB):
        pass

@service()
class ServiceB:
    def __init__(self, service_a: ServiceA):
        pass
```

错误信息：

```
ValueError: 检测到循环依赖: service_a -> service_b -> service_a。
请重构代码以消除循环依赖。
```

### 4. 获取服务实例

在路由或其他地方获取服务实例：

```python
from myboot.core.application import get_service

@get('/users/{user_id}')
def get_user(user_id: int):
    user_service = get_service('user_service')
    return user_service.get_user(user_id)
```

## 最佳实践

### 1. 使用类型注解

推荐使用类型注解声明依赖，代码更清晰：

```python
# ✅ 推荐
@service()
class OrderService:
    def __init__(self, user_service: UserService, email_service: EmailService):
        self.user_service = user_service
        self.email_service = email_service

# ❌ 不推荐（需要手动获取）
@service()
class OrderService:
    def __init__(self):
        from myboot.core.application import get_service
        self.user_service = get_service('user_service')
        self.email_service = get_service('email_service')
```

### 2. 避免循环依赖

设计服务时避免循环依赖：

```python
# ✅ 好的设计
@service()
class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

@service()
class OrderService:
    def __init__(self, user_service: UserService, order_repo: OrderRepository):
        self.user_service = user_service
        self.order_repo = order_repo

# ❌ 避免循环依赖
@service()
class ServiceA:
    def __init__(self, service_b: ServiceB):
        pass

@service()
class ServiceB:
    def __init__(self, service_a: ServiceA):
        pass
```

### 3. 使用接口而非具体实现

虽然 Python 没有接口，但可以通过抽象基类或协议定义接口：

```python
from abc import ABC, abstractmethod

class IUserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: int):
        pass

@service()
class UserRepository(IUserRepository):
    def get_user(self, user_id: int):
        return {"id": user_id}

@service()
class UserService:
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo
```

### 4. 合理使用可选依赖

对于非必需的依赖，使用 `Optional`：

```python
from typing import Optional

@service()
class ProductService:
    def __init__(
        self,
        db: DatabaseClient,  # 必需依赖
        cache: Optional[CacheService] = None  # 可选依赖
    ):
        self.db = db
        self.cache = cache
```

## 常见问题

### Q1: 依赖注入失败怎么办？

如果依赖注入失败，框架会自动回退到传统方式（直接实例化）。检查日志中的错误信息：

1. **依赖的服务未注册**：确保依赖的服务已使用 `@service()` 装饰器
2. **服务名不匹配**：检查服务名是否正确（类名转下划线命名）
3. **循环依赖**：重构代码消除循环依赖

### Q2: 如何调试依赖关系？

框架会在日志中输出依赖关系信息：

```
已注册服务提供者: user_service (依赖: set())
已注册服务提供者: order_service (依赖: {'user_service', 'email_service'})
```

### Q3: 可以在运行时动态获取服务吗？

可以，使用 `get_service()` 函数：

```python
from myboot.core.application import get_service

def some_function():
    user_service = get_service('user_service')
    if user_service:
        # 使用服务
        pass
```

### Q4: 支持异步服务吗？

目前依赖注入主要支持同步服务。对于异步服务，建议在服务内部处理异步逻辑。

### Q5: 如何测试带依赖的服务？

在测试中，可以手动创建服务实例并注入 mock 对象：

```python
def test_order_service():
    # 创建 mock 依赖
    mock_user_service = MockUserService()
    mock_email_service = MockEmailService()

    # 创建服务实例
    order_service = OrderService(mock_user_service, mock_email_service)

    # 测试
    assert order_service is not None
```

## 完整示例

```python
from myboot.core.decorators import service, get
from myboot.core.application import get_service
from typing import Optional

# 基础服务
@service()
class DatabaseClient:
    def __init__(self):
        self.connection = "connected"
        print("✅ DatabaseClient 已初始化")

@service()
class CacheService:
    def __init__(self):
        self.cache = {}
        print("✅ CacheService 已初始化")

# 仓储层
@service()
class UserRepository:
    def __init__(self, db: DatabaseClient):
        self.db = db
        print("✅ UserRepository 已初始化（依赖: DatabaseClient）")

    def find_by_id(self, user_id: int):
        return {"id": user_id, "name": f"用户{user_id}"}

# 服务层
@service()
class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        cache: Optional[CacheService] = None
    ):
        self.user_repo = user_repo
        self.cache = cache
        print("✅ UserService 已初始化（依赖: UserRepository, CacheService）")

    def get_user(self, user_id: int):
        # 尝试从缓存获取
        if self.cache and user_id in self.cache.cache:
            return self.cache.cache[user_id]

        # 从数据库获取
        user = self.user_repo.find_by_id(user_id)

        # 存入缓存
        if self.cache:
            self.cache.cache[user_id] = user

        return user

# 路由层
@get('/users/{user_id}')
def get_user(user_id: int):
    user_service = get_service('user_service')
    return user_service.get_user(user_id)
```

## 总结

依赖注入功能让您能够：

- ✅ 自动管理服务依赖关系
- ✅ 无需手动获取和传递依赖
- ✅ 支持多级依赖和可选依赖
- ✅ 自动检测循环依赖
- ✅ 支持 Client 注入到 Service 和 Controller
- ✅ 支持 Component 组件，可包含定时任务
- ✅ 支持多种依赖查找方式（名称、类型）
- ✅ 保持向后兼容，现有代码无需修改

开始使用依赖注入，让代码更加清晰和可维护！
