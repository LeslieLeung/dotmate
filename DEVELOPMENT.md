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
    ├── font/
    │   ├── manager.py      # 字体管理器
    │   └── resource/       # 字体文件目录
    │       ├── Hack-Bold.ttf
    │       ├── Hack-Regular.ttf
    │       └── SourceHanSansSC-VF.otf
    └── view/
        ├── base.py         # 基础视图类
        ├── factory.py      # 视图工厂
        ├── image.py        # 图像视图基类
        ├── title_image.py  # 标题图像视图
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

## 安装环境
uv venv

# 安装依赖
uv sync
```

## 扩展开发

### 新 View 开发 SOP (标准操作程序)

#### 步骤 1: 确定 View 类型

首先确定你要开发的 View 类型：

1. **文本类型 (BaseView)**: 发送简单的文本消息
2. **图像类型 (ImageView)**: 发送图像数据
3. **生成图像类型 (TitleImageView)**: 动态生成图像内容

#### 步骤 2: 创建参数模型

在 `dotmate/view/` 目录下创建新的视图文件，首先定义参数模型：

```python
from pydantic import BaseModel
from typing import Optional, Literal

class MyCustomParams(BaseModel):
    # 必填参数
    required_param: str

    # 可选参数
    optional_param: Optional[str] = None

    # 如果是图像类型，添加图像相关参数
    link: Optional[str] = None
    border: Optional[int] = None
    dither_type: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = "NONE"
    dither_kernel: Optional[Literal[
        "THRESHOLD", "ATKINSON", "BURKES", "FLOYD_STEINBERG",
        "SIERRA2", "STUCKI", "JARVIS_JUDICE_NINKE",
        "DIFFUSION_ROW", "DIFFUSION_COLUMN", "DIFFUSION2_D"
    ]] = None
```

#### 步骤 3: 选择基类并实现 View

根据 View 类型选择适当的基类：

**文本类型示例：**
```python
from dotmate.view.base import BaseView
from dotmate.api.api import DisplayTextRequest

class MyTextView(BaseView):
    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return MyCustomParams

    def execute(self, params: BaseModel) -> None:
        custom_params = MyCustomParams(**params.model_dump())

        request = DisplayTextRequest(
            refreshNow=True,
            deviceId=self.device_id,
            title="My Title",
            message=custom_params.required_param,
            signature=datetime.now().strftime("%H:%M"),
            icon=None,
            link=None,
        )

        try:
            response = self.client.display_text(request)
            print(f"Message sent to {self.device_id}")
        except Exception as e:
            print(f"Error: {e}")
```

**图像类型示例：**
```python
from dotmate.view.image import ImageView, ImageParams

class MyImageView(ImageView):
    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        # 如果需要字体管理，添加：
        # self.font_manager = FontManager()

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return MyCustomParams

    def _generate_image(self, params: MyCustomParams) -> bytes:
        """生成图像的核心逻辑"""
        # 实现图像生成逻辑
        # 返回 PNG 格式的字节数据
        pass

    def execute(self, params: BaseModel) -> None:
        custom_params = MyCustomParams(**params.model_dump())

        try:
            # 生成图像
            image_data = self._generate_image(custom_params)

            # 创建 ImageParams 并调用父类方法
            image_params = ImageParams(
                image_data=image_data,
                link=custom_params.link,
                border=custom_params.border,
                dither_type=custom_params.dither_type,
                dither_kernel=custom_params.dither_kernel,
            )

            super().execute(image_params)

        except Exception as e:
            print(f"Error in MyImageView: {e}")
```

#### 步骤 4: 注册到工厂

在 `dotmate/view/factory.py` 中注册新的视图类型：

```python
from dotmate.view.my_custom import MyCustomView

class ViewFactory:
    _view_registry: Dict[str, Type[BaseView]] = {
        "work": WorkView,
        "text": TextView,
        "code_status": CodeStatusView,
        "image": ImageView,
        "title_image": TitleImageView,
        "my_custom": MyCustomView,  # 添加新类型
    }
```

#### 步骤 5: 添加命令行支持

在 `main.py` 中添加命令行参数支持：

1. **添加参数解析**：
```python
# 在 push_parser.add_argument 部分添加
push_parser.add_argument("--my-param", help="My custom parameter")
```

2. **添加参数处理**：
```python
# 在参数处理部分添加
if args.my_param:
    push_params["my_param"] = args.my_param
```

#### 步骤 6: 更新配置文件和文档

1. **更新 `config.example.yaml`**：
   - 添加新 View 类型的配置示例
   - 更新参数说明文档

2. **更新 `README.md`**：
   - 在消息类型部分添加说明
   - 添加命令行使用示例

3. **更新 `CLAUDE.md`**：
   - 更新支持的 View 类型列表
   - 添加配置示例

#### 步骤 7: 测试

1. **参数验证测试**：
```bash
python -c "
from dotmate.view.my_custom import MyCustomView, MyCustomParams
params = MyCustomParams(required_param='test')
print('✓ Parameter validation passed')
"
```

2. **工厂注册测试**：
```bash
python -c "
from dotmate.view.factory import ViewFactory
print('Available types:', ViewFactory.get_available_types())
"
```

3. **命令行测试**：
```bash
python main.py push mydevice my_custom --my-param "test value"
```

#### 最佳实践

1. **错误处理**: 总是包含适当的错误处理和用户友好的错误消息
2. **参数验证**: 使用 Pydantic 模型进行参数验证
3. **代码复用**: 对于图像类型，尽量复用现有的字体管理和图像生成工具
4. **文档**: 确保添加清晰的文档字符串和类型提示
5. **测试**: 在不同场景下测试你的 View（成功、失败、边界情况）

#### 图像 View 开发注意事项

- 图像尺寸固定为 296x152 像素
- 使用 1-bit 模式 (黑白) 以适配 e-ink 显示器
- 支持中文字体渲染时使用 FontManager
- 实现适当的文本换行和字体大小调整
- 包含时间戳等有用信息

### 字体系统

#### 字体管理器 (FontManager)

FontManager 负责字体文件的查找和加载，支持：

- **字体文件目录**: `dotmate/font/resource/`
- **支持格式**: TTF、OTF、TTC
- **系统字体回退**: 在本地字体不可用时自动回退到系统字体

#### 在 View 中使用自定义字体

图像类型的 View 可以通过以下方式自定义字体：

```python
from dotmate.view.image import ImageView
from dotmate.font import FontManager

class MyImageView(ImageView):
    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.font_manager = FontManager()
        self.custom_font_name = "Hack-Bold"  # 指定字体名称

    def _get_font(self, size: int):
        """获取指定大小的字体"""
        if self.custom_font_name:
            return self.font_manager.get_specific_font(self.custom_font_name, size)
        return self.font_manager.get_font(size)
```

#### 对于 TitleImageView 的字体配置

TitleImageView 支持更高级的字体配置，包括字重设置：

```python
from dotmate.view.title_image import TitleImageView

class MyTitleView(TitleImageView):
    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "SourceHanSansSC-VF"  # 可变字体
        self.font_weight = 600  # 字重 (100-900)
```

#### 内置字体配置

项目包含以下字体：

- **Hack-Bold.ttf**: 编程字体，适合代码展示
- **Hack-Regular.ttf**: 编程字体常规版本
- **SourceHanSansSC-VF.otf**: 思源黑体可变字体，支持中文

#### 字体选择建议

- **英文/代码内容**: 使用 Hack 字体系列
- **中文内容**: 使用 SourceHanSansSC 字体
- **可变字体**: 可通过 `font_weight` 调整字重 (100-900)

#### 字体回退机制

如果指定的字体不存在，系统会：
1. 尝试在 `font/resource/` 目录中查找
2. 尝试部分匹配字体文件名
3. 直接回退到 PIL 默认字体

### 添加新的消息类型

按照上述 SOP 步骤进行开发即可。

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