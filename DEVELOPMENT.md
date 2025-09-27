# 开发指南

## 项目结构

```
dotmate/
├── main.py                 # 主程序入口
├── config.example.yaml     # 配置文件模板
├── pyproject.toml          # 项目依赖配置
└── dotmate/
    ├── api/
    │   └── api.py          # API 客户端
    ├── config/
    │   └── models.py       # 配置模型
    └── view/
        ├── base.py         # 基础视图类
        ├── factory.py      # 视图工厂
        ├── work.py         # 工作倒计时视图
        ├── text.py         # 文本消息视图
        └── code_status.py  # 代码状态视图
```

## 开发环境搭建

### 环境要求
- Python >= 3.12
- uv 包管理器（推荐）

### 安装开发依赖
```bash
# 克隆项目
git clone https://github.com/leslieleung/dotmate
cd dotmate

# 安装依赖
uv install
```

## 扩展开发

### 添加新的消息类型

1. 在 `dotmate/view/` 目录下创建新的视图文件
2. 继承 `BaseView` 类并实现必要方法
3. 在 `factory.py` 中注册新的视图类型

示例：
```python
# dotmate/view/my_custom.py
from typing import Type
from pydantic import BaseModel
from dotmate.view.base import BaseView

class MyCustomParams(BaseModel):
    custom_param: str

class MyCustomView(BaseView):
    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return MyCustomParams

    def execute(self, params: BaseModel) -> None:
        # 实现你的逻辑
        pass
```

然后在 `factory.py` 中注册：
```python
from dotmate.view.my_custom import MyCustomView

class ViewFactory:
    _view_registry: Dict[str, Type[BaseView]] = {
        "work": WorkView,
        "text": TextView,
        "code_status": CodeStatusView,
        "my_custom": MyCustomView,  # 添加新类型
    }
```

### 配置模型

配置文件的数据模型定义在 `dotmate/config/models.py` 中：

- `Config`: 主配置类，包含 API 密钥和设备列表
- `Device`: 设备配置，包含名称、设备ID和调度任务
- `Schedule`: 调度任务配置，包含 Cron 表达式、消息类型和参数

### API 客户端

API 客户端位于 `dotmate/api/api.py`，提供与设备通信的接口。

### 视图系统

- `BaseView`: 所有视图的基类，定义了通用接口
- `ViewFactory`: 视图工厂，负责创建和管理不同类型的视图
- 各个具体视图类：实现特定的消息类型逻辑

## 测试

目前项目尚未包含测试套件。建议在开发新功能时：

1. 使用 `python main.py push` 命令手动测试新的消息类型
2. 验证配置文件解析是否正确
3. 确保定时任务调度正常工作

## 代码规范

- 使用 Python 3.12+ 的类型提示
- 遵循 PEP 8 代码风格
- 使用 Pydantic 进行数据验证
- 保持代码简洁和可读性

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

欢迎提交 Pull Request 和 Issue！