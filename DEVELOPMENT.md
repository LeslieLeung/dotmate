# 开发指南

## 项目结构

```
dotmate/
├── main.py                      # 主程序入口
├── config.example.yaml          # 配置文件模板
├── Dockerfile                   # 多阶段构建（前端 dist + Python 运行时）
├── docker-compose.yml           # daemon 默认；`--profile web` 启动 Web UI
├── docker-entrypoint.sh         # 容器启动时校正 data/logs 目录权限
├── .env.example                 # Docker Web 模式的 ADMIN_TOKEN 模板
├── pyproject.toml               # 项目依赖配置
├── dotmate/
│   ├── api/
│   │   └── api.py               # Web 管理端使用的 Quote/0 兼容客户端
│   ├── config/
│   │   └── models.py            # 配置模型 (Config/Device/Schedule/PlatformConfig)
│   ├── platforms/               # ★ 厂商平台抽象层
│   │   ├── base.py              # PlatformClient 抽象基类 + 中性 ImagePayload/TextPayload
│   │   ├── registry.py          # PlatformRegistry 工厂 (platform -> client+profile)
│   │   ├── demo.py              # DemoClient 本地预览
│   │   ├── quote0/              # Quote/0 厂商包 (296x152, 文本+图片)
│   │   │   ├── client.py        # DotClient (JSON base64)
│   │   │   ├── models.py        # Quote/0 wire-format 模型
│   │   │   └── profile.py       # Quote0Profile
│   │   └── zectrix/             # Zectrix 厂商包 (400x300, 仅图片)
│   │       ├── client.py        # ZectrixClient (multipart)
│   │       ├── models.py        # Zectrix wire-format 模型
│   │       └── profile.py       # Note4Profile
│   ├── font/
│   │   ├── manager.py           # 字体管理器
│   │   └── resource/            # 字体文件目录
│   │       ├── Hack-Bold.ttf
│   │       ├── Hack-Regular.ttf
│   │       └── SourceHanSansSC-VF.otf
│   └── view/
│       ├── base.py              # 基础视图类 (声明 requires_text 能力)
│       ├── factory.py           # 视图工厂 (接收 PlatformProfile)
│       ├── image.py             # 图像视图基类 (display_scale/_sz/_py 自适应布局)
│       ├── title_image.py       # 标题图像视图
│       ├── work.py              # 工作倒计时视图
│       ├── text.py              # 文本消息视图
│       ├── code_status.py       # 代码状态视图
│       ├── umami_stats.py       # Umami 统计视图
│       ├── github_contributions.py  # GitHub 贡献图视图
│       └── code_plan_usage.py   # 代码计划用量视图
└── web/
    ├── backend/                 # FastAPI 后端
    │   ├── app.py               # FastAPI 应用入口
    │   ├── db.py                # SQLite 数据库配置
    │   ├── device_models.py     # 硬件型号与显示能力注册表
    │   ├── models.py            # SQLModel 数据模型
    │   ├── schemas.py           # Pydantic 请求/响应模型
    │   ├── schedule_types.py    # 动态任务表单元数据与校验
    │   ├── scheduler.py         # SQLite 驱动的后台调度器
    │   ├── status_worker.py     # 设备状态轮询与缓存
    │   ├── vendors.py           # Web 远程管理 Vendor 注册表
    │   └── routes/              # 管理端 API 路由
    └── frontend/                # React + shadcn/ui 前端
        ├── src/                 # 页面、组件、i18n 和 API 客户端
        └── test/                # Vitest + Testing Library 测试
```

## 开发环境搭建

### 环境要求
- Python >= 3.12
- Node.js >= 20.19（用于前端构建）
- uv 包管理器（推荐）

### 安装开发依赖
```bash
# 克隆项目
git clone https://github.com/leslieleung/dotmate
cd dotmate

# 安装 Python 环境
uv venv
uv sync

# 安装前端依赖
cd web/frontend
npm ci
cd ../..
```

### 运行模式

#### 1. 传统模式 (config.yaml)

使用 YAML 配置文件运行守护进程：

```bash
# 复制配置模板
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入你的配置

# 启动守护进程
python main.py daemon
```

#### 2. Web 管理面板模式

使用 SQLite 数据库和 Web 界面管理设备和调度任务：

```bash
# 设置管理员 Token（仅本机访问时可选；对外监听时必填）
export ADMIN_TOKEN="your-secret-token"

# 生产模式：构建前端并启动服务
make web
# 访问 http://localhost:8000

# 或指定端口
make build-frontend
python main.py web --port 9000

# 允许其他主机访问（必须先设置 ADMIN_TOKEN）
python main.py web --host 0.0.0.0

# 开发模式：同时启动后端 API 和前端开发服务器（支持热更新）
python main.py dev
# 后端 API: http://localhost:8000
# 前端: http://localhost:5173
```

也可以使用 Makefile：

```bash
make dev   # 开发模式
make web   # 生产模式（自动构建前端）
```

##### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ADMIN_TOKEN` | 管理面板认证 Token；非本机监听时必填 | 空（仅允许本机免认证） |
| `DOTMATE_DB_PATH` | SQLite 数据库路径 | `data/dotmate.db` |
| `DOTMATE_WEB_PORT` | Docker Compose 映射到宿主机的 Web 端口 | `8000` |
| `TZ` | 容器时区 | `UTC` |

##### Docker 部署

发布镜像通过多阶段构建打包 `web/frontend/dist`，同一镜像可运行 YAML daemon 或 Web 管理面板。Web 模式把设备和任务写在 SQLite 里，**必须把数据库目录挂载到容器外**，否则重建或更新容器后配置会丢失。

```bash
# Web UI：SQLite 持久化到 ./data/dotmate.db
cp .env.example .env   # 填写 ADMIN_TOKEN
docker compose --profile web up -d web

# YAML daemon：继续使用 config.yaml，不启动 Web
docker compose up -d
```

Compose 中 Web 服务会：

- 将 `./data` 挂载到 `/app/data`，并设置 `DOTMATE_DB_PATH=/app/data/dotmate.db`
- 映射 `8000` 端口，并以 `--host 0.0.0.0` 启动（因此 `ADMIN_TOKEN` 必填）
- 不挂载 `config.yaml`；Web 与 daemon 配置互不导入

`docker-entrypoint.sh` 会在启动时创建 `data/`、`logs/` 并把所有权交给容器内的 `app` 用户，避免 Linux 宿主机 bind mount 导致 SQLite 无法写入。直接 `docker run` 时同样需要挂载数据目录、设置 `ADMIN_TOKEN`，并显式传入 `.venv/bin/python main.py web --host 0.0.0.0`。

停止 Web 请用 `docker compose --profile web stop web`。`docker compose down` 会拆除同一 Compose 项目里的全部容器，包括正在运行的 YAML daemon。

本地改完前端或后端后需要 `docker compose --profile web build web` 才会进入镜像；只重启容器不会更新已打包的 `dist`。

##### Web 运行时架构

Web 模式与 YAML 模式是两套独立的配置和调度运行时：

| 模式 | 配置源 | 调度器 | 界面 |
|------|--------|----------|------|
| `daemon` / `push` | `config.yaml` | `BlockingScheduler` | 无 |
| `web` | SQLite（默认 `data/dotmate.db`） | `BackgroundScheduler` + 设备状态 worker | FastAPI 托管 `web/frontend/dist` |
| `dev` | SQLite | 同 Web 模式 | FastAPI API + Vite HMR |

`python main.py web` 会依次初始化数据库、加载调度任务、启动状态 worker，然后运行 Uvicorn。`python main.py dev` 会额外启动 Vite，并在退出时统一停止子进程和后台任务。直接运行 `uvicorn web.backend.app:app` 只会提供 API/静态页，不会启动调度器或状态 worker。

Web 数据模型由 SQLModel 定义：

- `Settings`：全局 API 请求间隔
- `ApiCredential`：按 vendor 分组的 API Key，同 vendor 下名称和 Key 唯一
- `Device`：关联凭据和硬件型号，保存 Overlay 选项
- `Schedule`：保存 Cron、View 类型和 JSON 参数
- `DeviceStatusRecord`：设备状态缓存、刷新策略和失败退避状态

数据库启动时会执行只增量的 Schema 迁移；对未知 vendor 或型号/vendor 不匹配的旧数据会中止迁移，不会静默删除数据。

Web 层把「云 API 厂商」和「硬件显示能力」分开建模：`vendors.py` 描述设备发现、状态、设置等远程能力，`device_models.py` 描述分辨率、文本/图片、Overlay 和 Note 4 页号等显示能力。当前映射为 `mindreset -> quote0` 和 `zectrix -> note4`。

`schedule_types.py` 从 View 的 Pydantic 参数模型生成表单 Schema，再按设备型号过滤不支持的任务和字段。新建/修改任务时，后端会重新做 Pydantic 校验、设备能力校验和 Cron 冲突检查；持久化成功后会原子替换调度快照，失败时回滚数据库变更。

##### 认证与开发边界

- `ADMIN_TOKEN` 为空时 API 不要求认证，因此入口点禁止在这种状态下绑定非回环地址。
- 设置 `ADMIN_TOKEN` 后，除 `/api/auth/status` 外的管理 API 均使用 `Authorization: Bearer <token>`。
- 生产模式必须先生成 `web/frontend/dist/index.html`；`python main.py web` 缺少构建产物时会拒绝启动。
- Vite 只允许 `localhost:5173` 和 `127.0.0.1:5173` 跨域访问 API；非默认部署需要同步调整 CORS 策略。

##### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/status` | 查询是否需要认证以及当前 Token 是否有效 |
| GET | `/api/settings` | 获取全局设置 |
| PUT | `/api/settings` | 更新全局设置 |
| GET | `/api/vendors` | 获取支持的 Vendor 与能力 |
| GET | `/api/device-models` | 获取硬件型号与显示能力，可用 `vendor` 过滤 |
| GET | `/api/api-keys` | 获取已绑定 API Key（仅返回掩码） |
| POST | `/api/api-keys/batch` | 批量绑定 API Key 并导入设备 |
| POST | `/api/api-keys/sync-all` | 同步全部 API Key 的设备 |
| POST | `/api/api-keys/{id}/sync` | 同步单个 API Key 的设备 |
| PUT | `/api/api-keys/{id}` | 重命名 API Key |
| DELETE | `/api/api-keys/{id}` | 删除未被设备使用的 API Key |
| GET | `/api/devices` | 获取所有设备 |
| POST | `/api/devices` | 创建设备 |
| GET | `/api/devices/{id}` | 获取单个设备 |
| PUT | `/api/devices/{id}` | 更新设备 |
| DELETE | `/api/devices/{id}` | 删除设备 |
| POST | `/api/devices/remote/statuses/refresh` | 异步刷新全部设备状态 |
| POST | `/api/devices/{id}/remote/status/refresh` | 异步刷新单台设备状态 |
| PATCH | `/api/devices/{id}/remote/status/policy` | 设置单台设备状态轮询间隔 |
| GET | `/api/devices/{id}/remote/settings` | 读取远端设备设置 |
| PATCH | `/api/devices/{id}/remote/settings` | 修改远端设备设置 |
| GET | `/api/devices/{id}/remote/timezones` | 获取 Vendor 支持的时区 |
| POST | `/api/devices/{id}/remote/next` | 切换到下一条设备内容 |
| GET | `/api/devices/{id}/remote/content` | 获取设备内容列表 |
| GET | `/api/devices/{id}/schedule-types` | 获取按设备型号过滤的调度表单 Schema |
| GET | `/api/devices/{id}/schedules` | 获取设备的调度任务 |
| POST | `/api/devices/{id}/schedules` | 创建调度任务 |
| PUT | `/api/devices/schedules/{id}` | 更新调度任务 |
| DELETE | `/api/devices/schedules/{id}` | 删除调度任务 |
| POST | `/api/devices/schedules/{id}/run` | 立即执行调度任务 |
| GET | `/api/schema/schedule-types` | 获取不绑定设备的通用调度类型 Schema |

前端默认在 API 请求中添加 `X-Dotmate-Structured-Errors: 1`，以获得本地化所需的错误代码、参数和字段错误；未添加该请求头的 API 调用方仍会收到普通 FastAPI 错误结构。

##### 前端开发

```bash
cd web/frontend

# 启动开发服务器（带热更新）
npm run dev

# 构建生产版本
npm run build

# 运行前端测试与 lint
npm test
npm run lint
```

提交前可在项目根目录运行完整检查：

```bash
make check  # 后端测试、前端测试、lint 和生产构建
```

前端开发服务器运行在 `http://localhost:5173`，会自动代理 API 请求到后端 `http://localhost:8000`。可用 `DOTMATE_BACKEND_URL` 修改 Vite 代理目标；通常应优先从项目根目录运行 `python main.py dev`，以确保后台调度器和状态 worker 一起启动。

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
    border: Optional[Literal[0, 1]] = None
    task_key: Optional[str] = None
    task_alias: Optional[Union[str, int]] = None
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
from dotmate.platforms.base import TextPayload

class MyTextView(BaseView):
    requires_text = True  # 声明需要文本能力（会在配置加载时校验平台支持）

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return MyCustomParams

    def execute(self, params: BaseModel) -> None:
        custom_params = MyCustomParams(**params.model_dump())

        payload = TextPayload(
            title="My Title",
            message=custom_params.required_param,
            signature=datetime.now().strftime("%H:%M"),
        )

        try:
            response = self.client.display_text(self.device_id, payload)
            print(f"Message sent to {self.device_id}")
        except Exception as e:
            print(f"Error: {e}")
```

**图像类型示例：**
```python
from dotmate.view.image import ImageView, ImageParams

class MyImageView(ImageView):
    def __init__(self, client, device_id: str, profile=None):
        super().__init__(client, device_id, profile=profile)
        # 可在此设置自定义字体：
        # self.custom_font_name = "Hack-Bold"

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return MyCustomParams

    def _generate_image(self, params: MyCustomParams) -> bytes:
        """生成图像的核心逻辑"""
        # 实现图像生成逻辑，布局请使用 self._sz(...) / self._py(...) 自适应分辨率
        # 返回 PNG 格式的字节数据
        pass

    def execute(self, params: BaseModel) -> None:
        custom_params = MyCustomParams(**params.model_dump())

        try:
            # 生成图像
            image_data = self._generate_image(custom_params)

            # 创建 ImageParams 并调用父类方法（父类会转成中性 ImagePayload 再发送）
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

#### 步骤 6: 生成效果图片

使用 `demo` 命令生成 View 的效果展示图片，保存到 `demos/` 目录下。这些图片用于 README 的效果展示。

```bash
# 生成效果图片（以 title_image 为例）
python main.py demo title_image --main-title "测试标题" --sub-title "副标题"

# 指定输出目录（默认为 demos/）
python main.py demo my_custom --my-param "test value" --output "./demos"
```

生成后确认图片效果符合预期，图片文件命名规则由 DemoClient 自动处理，通常为 `demos/<view_type>.png`。

#### 步骤 7: 更新配置文件和文档

需要更新以下文件，确保新 View 类型的配置示例、命令行用法和效果图片都被正确记录。

1. **适配 Web 调度表单**：
   - 在 `web/backend/schedule_types.py` 的 `SCHEDULE_TYPE_METADATA` 中添加类型标签、说明、摘要字段和表单字段覆盖
   - 如果该类型无法在 Web 中安全编辑，显式设置 `web_editable=False`
   - 确认 Quote/0 和 Note 4 的字段过滤符合 `DeviceModelDefinition.allowed_image_fields`
   - 在 `web/frontend/src/i18n/metadata.ts` 和 `resources.ts` 中添加中英文名称、字段和错误文案

2. **更新 `config.example.yaml`**：
   - 在对应设备的 `schedules` 下添加新 View 类型的完整配置示例
   - 包含所有必填参数和常用可选参数
   - 添加参数注释说明

3. **更新 `README.md`**：
   - 在「效果展示」部分添加效果图片引用：`<img src="demos/my_custom.png" width="400" alt="描述">`
   - 在「手动发送消息」部分添加 `push` 命令使用示例
   - 在「生成 Demo 图片」部分添加 `demo` 命令使用示例
   - 在「消息类型」部分添加新类型的详细说明，包含参数列表和效果图片

4. **更新 `CLAUDE.md`**：
   - 在 View System 描述中更新支持的 View 类型列表
   - 在 `push` 命令示例中添加新类型的命令行用法
   - 在 `demo` 命令示例中添加新类型的命令行用法
   - 在配置结构示例中添加新类型的 YAML 配置

5. **更新 `DEVELOPMENT.md`**：
   - 在项目结构树中添加新的视图文件
   - 如有新增字体分配，更新「当前字体分配」部分

#### 步骤 8: 测试

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

- 图像尺寸按设备平台决定：Quote/0 为 296x152，Zectrix Note 4 为 400x300
- 平台分辨率通过构造函数 `profile=` 传入，ViewFactory 会自动传递
- 使用 `_sz(base)` 让字体/间距按 296x152 基准缩放（自动适应分辨率）
- 使用 `_py(ratio)` 用比例表示行 Y 坐标（如 `_py(0.21)`），避免硬编码像素
- 使用 1-bit 模式 (黑白) 以适配 e-ink 显示器
- 支持中文字体渲染时使用 FontManager
- 实现适当的文本换行和字体大小调整
- 包含时间戳等有用信息

### 平台系统（厂商抽象）

厂商实现完全分离，每个厂商一个独立包，互不依赖：

- `platforms/base.py`: 定义中性 `ImagePayload`/`TextPayload` 和 `PlatformClient` 抽象契约
- `platforms/quote0/`: Quote/0 厂商（DotClient + JSON base64 模型 + Quote0Profile）
- `platforms/zectrix/`: Zectrix 厂商（ZectrixClient + multipart 模型 + Note4Profile）
- `platforms/registry.py`: `PlatformRegistry` 工厂，按 `platform` 名称解析出 client 类和 profile

**关键解耦**：View 层只构建厂商无关的中性 `ImagePayload`/`TextPayload`，各厂商 client 负责转换成自己的 wire 格式。新增厂商时无需改动任何 view。

### 添加新的平台/厂商

1. 在 `dotmate/platforms/<name>/` 下创建子包，包含：
   - `client.py`: 继承 `PlatformClient`，实现 `display_image`（把中性 payload 转为厂商 wire 格式）
   - `models.py`: 厂商专用的请求/响应模型（不要跨厂商 import）
   - `profile.py`: 一个 `PlatformProfile`（分辨率 + `supports_text`/`supports_image` 能力）
2. 在 `PlatformRegistry._platforms` 中注册（名称 -> client 类, profile）
3. 在 YAML 配置的 `platforms:` 下添加该厂商的配置段

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

#### 当前字体分配

- **CodeStatusView**: 使用 Hack-Bold 用于代码/技术内容展示
- **WorkView**: 使用 SourceHanSansSC-VF (SemiBold weight 600) 用于中文文本
- **UmamiStatsView**: 使用 Hack-Bold 用于分析数据展示

#### 字体回退机制

如果指定的字体不存在，系统会：
1. 尝试在 `font/resource/` 目录中查找
2. 尝试部分匹配字体文件名
3. 直接回退到 PIL 默认字体

### 添加新的消息类型

按照上述 SOP 步骤进行开发即可。

### 配置模型

配置文件的数据模型定义在 `dotmate/config/models.py` 中：

- `Config`: 主配置类，包含 `platforms`（按厂商分组的凭证）和设备列表
- `Device`: 设备配置，包含名称、设备ID、`platform`（厂商）和调度任务
- `Schedule`: 调度任务配置，包含 Cron 表达式、消息类型和参数
- `PlatformConfig`: 单个平台的配置（如 api_key）

加载时会做能力校验：在仅图片平台（如 zectrix）上配置 text 任务会在加载时直接报错。

### 平台客户端

平台客户端位于 `dotmate/platforms/`，是厂商抽象层。各厂商实现互不依赖，统一通过 `PlatformRegistry` 工厂创建。

### 视图系统

- `BaseView`: 所有视图的基类，定义了通用接口
- `ViewFactory`: 视图工厂，负责创建和管理不同类型的视图
- 各个具体视图类：实现特定的消息类型逻辑

## 测试

项目同时包含 Pytest 后端/CLI 测试和 Vitest 前端测试。常用命令：

```bash
# 完整检查：后端测试 + 前端测试 + 前端 lint + 生产构建
make check

# 单独运行
make test-backend
make test-frontend
make lint-frontend
make build-frontend
```

后端测试覆盖 CLI 参数与离线执行、平台客户端、Overlay、Web CRUD、认证、调度热加载、设备状态 worker 和 Zectrix 客户端。前端测试覆盖登录、设备/凭据管理、调度表单、设备详情、多语言和基础组件行为。

修改 Web 后端时优先使用测试中的临时 SQLite 数据库和 mock vendor client，避免读写真实 `data/dotmate.db` 或调用设备云 API。修改 View 或 CLI 后，除自动化测试外，可再用 `python main.py demo` 做图像视觉检查。

## 代码规范

- 使用 Python 3.12+ 的类型提示
- 遵循 PEP 8 代码风格
- 使用 Pydantic 进行数据验证
- 前端使用 TypeScript，提交前通过 Oxlint、Vitest 和生产构建
- 用户可见文案同步维护 `zh-CN` 和 `en-US` 翻译，不在组件中写死文本
- 保持代码简洁和可读性

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

欢迎提交 Pull Request 和 Issue！
