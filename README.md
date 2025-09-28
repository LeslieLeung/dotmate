# Dotmate

Dotmate 是一个用于管理[Quote/0](https://dot.mindreset.tech/product/quote)消息推送的调度器，支持通过定时任务向设备发送各种类型的消息。

## 功能特性

- 🕐 **定时任务调度**：基于 Cron 表达式的定时任务系统
- 💬 **多种消息类型**：支持文本消息、工作倒计时、代码状态、图片消息和标题图片生成等多种消息类型
- 🎯 **多设备管理**：支持管理多个设备，每个设备可配置独立的任务调度
- 🔧 **灵活配置**：使用 YAML 配置文件管理设备和任务
- 🚀 **即时推送**：支持手动触发消息推送

## 快速开始

### 方式一：Docker Compose（推荐）

1. 克隆项目：
```bash
git clone https://github.com/leslieleung/dotmate
cd dotmate
```

2. 复制配置文件模板：
```bash
cp config.example.yaml config.yaml
```

3. 编辑配置文件 `config.yaml`，填入你的 API 密钥和设备信息。

4. 启动服务：
```bash
# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 方式二：直接使用 Docker

如果你只想快速运行，可以直接使用 Docker 命令：

```bash
# 拉取镜像
docker pull ghcr.io/leslieleung/dotmate:latest

# 运行容器（需要提前准备好 config.yaml）
docker run -d \
  --name dotmate \
  --restart unless-stopped \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/leslieleung/dotmate:latest

# 查看日志
docker logs -f dotmate

# 停止容器
docker stop dotmate

# 删除容器
docker rm dotmate
```

### 方式三：本地开发

#### 环境要求
- Python >= 3.12
- uv 包管理器（推荐）
- Pillow 库（用于图片处理）

#### 安装

```bash
# 克隆项目
git clone https://github.com/leslieleung/dotmate
cd dotmate

# 安装依赖
uv install
```

#### 配置

1. 复制配置文件模板：
```bash
cp config.example.yaml config.yaml
```

2. 编辑配置文件 `config.yaml`，填入你的 API 密钥和设备信息。

#### 运行

##### 启动守护进程
```bash
# 启动定时任务调度器
python main.py daemon

# 或者直接运行（默认为守护进程模式）
python main.py
```

##### 手动发送消息
```bash
# 发送文本消息
python main.py push mydevice text --message "Hello World" --title "通知"

# 发送工作倒计时（生成图片）
python main.py push mydevice work --clock-in "09:00" --clock-out "18:00"

# 发送自定义图片
python main.py push mydevice image --image-path "path/to/image.png"

# 发送标题图片（动态生成）
python main.py push mydevice title_image --main-title "主标题" --sub-title "副标题"
```

## 消息类型

### 文本消息 (text)
发送自定义文本消息，支持标题和内容。

### 工作倒计时 (work)
显示距离下班还有多长时间，支持自定义上班和下班时间。现在以图片形式显示，支持中文字体渲染。

### 图片消息 (image)
发送 PNG 格式的图片文件到设备。支持以下参数：
- `image_path`: 图片文件路径
- `link`: 可选的跳转链接
- `border`: 可选的边框颜色
- `dither_type`: 抖动类型（DIFFUSION, ORDERED, NONE）
- `dither_kernel`: 抖动算法（多种选项）

### 标题图片 (title_image)
动态生成包含标题的图片消息。支持以下参数：
- `main_title`: 主标题（必填）
- `sub_title`: 副标题（可选）
- 支持中文字体渲染和自动字体大小调整
- 支持文本自动换行
- 其他图片相关参数同 image 类型

### 代码状态 (code_status)
显示代码状态信息（开发中）。

## 配置说明

配置文件使用 YAML 格式，主要包含：

- `api_key`: API 密钥
- `devices`: 设备列表
  - `name`: 设备名称
  - `device_id`: 设备唯一标识符
  - `schedules`: 定时任务列表
    - `cron`: Cron 表达式
    - `type`: 消息类型
    - `params`: 消息参数（可选）

### Cron 表达式示例

```bash
"*/5 * * * *"      # 每5分钟
"0 9-18 * * 1-5"   # 工作日每小时
"0 12 * * *"       # 每天中午12点
"*/30 9-17 * * 1-5" # 工作日工作时间内每30分钟
```

## 开发

如需扩展功能或贡献代码，请参考 [开发指南](DEVELOPMENT.md)。

## 贡献

欢迎提交 Pull Request 和 Issue！