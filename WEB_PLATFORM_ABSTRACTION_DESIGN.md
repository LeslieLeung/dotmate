# Web 多厂商与设备型号抽象功能设计

## 1. 文档状态

- 目标分支：`feature/web-ui`
- 来源分支：`refactor/platform-abstraction`
- 状态：设计稿，尚未实现本文所述 Web 功能
- 目标：让 Web 管理端正确区分厂商、API 凭据与具体设备型号，首批覆盖 MindReset Quote/0 和 Zectrix Note 4

## 2. 术语与边界

### 2.1 Vendor（厂商）

Vendor 表示提供云端接口和 API Key 的厂商，是 API 集成边界。

Vendor 决定：

- API Base URL、认证方式和 API Key 格式。
- 请求/响应协议与错误映射。
- 设备发现、状态、设置、时区、内容列表等厂商接口能力。
- API Key 的保存、验证、限流和客户端复用方式。

首批 Vendor：

| Vendor ID | 厂商名称 | 首批设备 | API Key / 接口 |
|---|---|---|---|
| `mindreset` | MindReset | Quote/0 | MindReset Open API |
| `zectrix` | Zectrix | Note 4 | Zectrix Open API |

### 2.2 Device Model / Profile（设备型号与显示配置）

Device Model 表示具体硬件产品；Device Profile 描述该型号的显示和渲染能力。

设备型号决定：

- 屏幕分辨率和渲染布局。
- 支持文本、图片或其他内容类型。
- 型号专属参数，例如 Note 4 的 `page_id`。
- 设备 ID 的格式、示例和校验提示。
- 是否可以使用依赖设备状态的 Overlay。

首批设备型号：

| Model ID | 设备名称 | Vendor | 分辨率 | 文本 | 图片 |
|---|---|---|---:|---|---|
| `quote0` | Quote/0 | `mindreset` | 296×152 | 支持 | 支持 |
| `note4` | Zectrix Note 4 | `zectrix` | 400×300 | 不支持 | 支持 |

### 2.3 Credential（API 凭据）

- 一个 Credential 只属于一个 Vendor。
- API Key 的唯一性、验证和同步策略都在 Vendor 范围内处理。
- Credential 不直接代表具体设备型号。
- 同一 Vendor 未来可以支持多个 Device Model，并复用相同的凭据体系。

### 2.4 Device（用户设备）

- 一台 Device 关联一个 Credential 和一个 Device Model。
- Device 的 Vendor 由 Credential 确定。
- Device Model 必须属于同一个 Vendor。
- 同一 Vendor 内允许设备更换 Credential。
- 不允许把设备改绑到其他 Vendor 的 Credential。
- 不允许把设备改成其他 Vendor 的 Device Model。

核心关系如下：

```text
Vendor
├── Credentials
├── API Client / Remote Capabilities
└── Device Models
    └── Device Profile / Display Capabilities

Device
├── Credential ──> Vendor
└── Device Model ──> 同一个 Vendor
```

## 3. 背景与当前状态

平台抽象分支已经提供：

- Quote/0 的 296×152 文本与图片推送。
- Zectrix Note 4 的 400×300 图片推送。
- 视图按 Profile 自适应分辨率与布局。
- Note 4 multipart 上传和 1–5 的 `page_id`。
- CLI/YAML 中按注册项创建客户端并校验显示能力。
- Demo 命令按目标 Profile 生成不同尺寸图片。

但当前核心代码中的 `PlatformRegistry` 使用 `quote0` 和 `zectrix` 作为同一级 ID，实际混合了设备型号与厂商概念：

- `quote0` 是 MindReset 的设备型号。
- `zectrix` 是厂商名称，当前对应的具体型号是 Note 4。

Web 端现有 `vendor = mindreset` 的建模方向是正确的，不应迁移成 `quote0`。需要做的是：

- 新增 `zectrix` Vendor。
- 为 Device 增加明确的 Device Model/Profile。
- 将厂商 API 能力和设备显示能力分开。
- 调度时用 Vendor 选择客户端，用 Device Model 选择 Profile。

合并后原有 Web Quote/0 功能仍由兼容客户端维持，但 Web 尚未支持 Zectrix Credential、Note 4 设备和型号化调度。

## 4. 设计目标

1. Web 中明确展示 Vendor、Credential、Device Model 和 Device 的关系。
2. 用户可以分别管理 MindReset 与 Zectrix API Key。
3. 用户可以管理 MindReset Quote/0 和 Zectrix Note 4。
4. 调度器按 Vendor 选择接口客户端，按 Device Model 选择显示 Profile。
5. Web 只允许创建具体设备型号支持的调度类型与参数。
6. MindReset Quote/0 现有远程管理能力不得回归。
7. 数据模型能够支持一个 Vendor 未来增加多个设备型号。

## 5. 非目标

- 本轮不新增消息视图类型。
- 不为 Zectrix 模拟不存在的设备发现、状态或设置接口。
- 不提供跨 Vendor 迁移设备。
- 不在本轮实现 Web Demo/图片预览。
- 不把 Device Model 当作 Vendor，也不把 API Key 直接绑定到某个型号。
- 不在本文阶段编写功能实现代码。

## 6. 注册模型

### 6.1 Vendor Registry

Vendor Registry 负责 API 集成信息：

- `id`
- `label`
- `description`
- `client_factory`
- `credential_hint`
- `supports_credential_validation`
- `supports_device_discovery`
- `supports_status`
- `supports_settings`
- `supports_timezones`
- `supports_next_content`
- `supports_content_list`

首批注册：

- `mindreset`
- `zectrix`

### 6.2 Device Model Registry

Device Model Registry 负责设备和显示信息：

- `id`
- `vendor_id`
- `label`
- `description`
- `width`
- `height`
- `supports_text`
- `supports_image`
- `supports_battery_overlay`
- `supports_page_id`
- `device_id_label`
- `device_id_example`
- 型号专属参数约束

首批注册：

- `quote0`，属于 `mindreset`
- `note4`，属于 `zectrix`

### 6.3 核心代码的抽象调整方向

现有 `PlatformRegistry` 后续应拆分为 Vendor 与 Device Model 两个维度，或至少让一个注册项同时明确携带 `vendor_id` 与 `model_id`，不能继续使用含义不一致的单一字符串。

推荐运行链路：

1. 从 Credential 的 `vendor` 获取 Vendor Client。
2. 从 Device 的 `model` 获取 Device Profile。
3. 校验 Model 所属 Vendor 与 Credential Vendor 一致。
4. 使用 Client 发送由 Profile 尺寸生成的内容。

## 7. 页面与交互设计

### 7.1 Settings / API Keys

新增 Credential 时：

1. 先选择 Vendor。
2. 填写凭据名称和 API Key。
3. 根据 Vendor 展示接口和密钥说明。
4. 保存后按 Vendor 能力决定是否验证、是否同步设备。

MindReset：

- 保存后可通过只读接口验证凭据。
- 支持自动发现并同步 Quote/0 设备。
- 显示 “Sync devices” 操作。

Zectrix：

- 保存 Zectrix API Key。
- 当前没有设备列表能力时，不自动创建设备。
- 不通过发送测试图片来验证密钥，避免改变设备内容。
- 提示用户到设备页手动添加 Note 4。

Credential 列表展示：

- Vendor 名称。
- 凭据名称。
- 掩码密钥。
- 关联设备数。
- 验证状态。
- 仅对支持发现的 Vendor 显示同步操作。

批量导入时每行必须带 `vendor`，错误按行返回。

### 7.2 Devices 列表

页面调整：

- 页面说明改为 “Manage your e-ink devices”。
- Vendor 筛选保留，用于区分 MindReset 和 Zectrix。
- 增加 Device Model 筛选，为未来同厂商多型号预留。
- 表格分别展示 Vendor、Device Model、分辨率和 Credential。
- 不把 `mindreset` 或 `zectrix` 当作设备型号展示。
- 全局状态刷新只处理 Vendor 支持状态接口且型号允许状态 Overlay 的设备。
- Note 4 不显示空的电池/Wi-Fi 数据，改为 “Status unavailable”。

### 7.3 新增设备

推荐流程：

1. 选择 Vendor。
2. 选择该 Vendor 下的 Credential。
3. 选择该 Vendor 下的 Device Model。
4. 填写或选择设备 ID。
5. 配置该型号支持的 Overlay。

MindReset Quote/0：

- 可从 Credential 同步得到的设备列表中选择。
- Model 自动识别为 `quote0`；首期也可显示为只读字段。
- 保留手工填写设备 ID 的兼容能力。

Zectrix Note 4：

- Model 为 `note4`。
- 手工填写 Note 4 设备 ID/MAC 地址。
- 显示 400×300、仅图片能力摘要。

表单必须校验：

- Credential Vendor 与所选 Vendor 一致。
- Device Model 属于所选 Vendor。
- 编辑时只能更换同 Vendor 的 Credential。
- 编辑时不允许更改 Vendor 或 Device Model；如需更换，应创建新设备。

### 7.4 Overlay 配置

Overlay 能力来自 Device Model 和 Vendor API 能力的交集：

- Quote/0：支持刷新时间、电池图标和电量百分比。
- Note 4：支持刷新时间；当前 Vendor API 不提供状态时，不显示电池图标和电量百分比。

如果历史数据在不支持的型号上开启了电池 Overlay，编辑页显示提示并在保存时清除。

### 7.5 Device Detail / 远程控制

远程管理区块由 Vendor API 能力控制：

- MindReset Quote/0：保留状态刷新、设备设置、时区、切换下一内容和内容列表。
- Zectrix Note 4：隐藏当前不支持的远程管理区块，仅展示 Vendor、型号、设备 ID、分辨率、调度和最近推送错误。

后端仍需做能力校验，不能只依赖前端隐藏。

### 7.6 Schedule Form

调度 Schema 应基于具体 Device 返回，因为可用能力由 Device Model 与 Vendor 协议共同决定。

| 能力/字段 | MindReset Quote/0 | Zectrix Note 4 |
|---|---|---|
| `text` 调度 | 显示 | 隐藏并由后端拒绝 |
| 图片类调度 | 显示 | 显示 |
| 输出尺寸 | 296×152 | 400×300 |
| `page_id` | 隐藏 | 显示，选项 1–5 |
| `border` | 显示 | 隐藏 |
| `link` | 显示 | 隐藏 |
| `task_key` / `task_alias` | 显示 | 隐藏 |
| `dither_type` | 完整枚举 | 简化为 Enabled/Disabled |
| `dither_kernel` | 显示 | 隐藏 |

补充约束：

- `page_id` 是 Note 4 型号参数，不是 Zectrix Vendor 的全局参数。
- `page_id` 放在 Display 区域，使用 1–5 的 Select。
- 后端执行同样的消息类型、字段白名单和取值范围校验。
- 对当前设备无效的历史参数需要明确提示并在保存时清除。
- Note 4 调度摘要增加 “Page 1–5”。
- 原始图片调度继续维持当前不可在 Web 编辑的限制。

### 7.7 自适应渲染

Web 调度执行链：

1. 从 Device 获取 Credential 和 Device Model。
2. 根据 Credential Vendor 创建或复用 Vendor Client。
3. 根据 Device Model 获取 Device Profile。
4. 校验 Model 与 Vendor 的归属关系。
5. 调用 `ViewFactory.execute_view` 时传入 Profile。
6. 图片视图按 296×152 或 400×300 渲染后交给 Vendor Client。

前端只展示型号的固定分辨率，不提供任意宽高配置。

## 8. 后端接口设计

### 8.1 Vendor 列表

保留并扩展：

`GET /api/vendors`

返回 Vendor API 信息与远程能力。`mindreset` 继续作为合法且正确的 Vendor ID，新增 `zectrix`。

### 8.2 Device Model 列表

新增：

`GET /api/device-models?vendor={vendor_id}`

返回指定 Vendor 下可选的设备型号及显示能力。

也可在 Vendor 响应中嵌套 `device_models`，但 Vendor 与 Model 在数据语义上仍保持独立。

### 8.3 调度 Schema

建议改为：

`GET /api/devices/{device_id}/schedule-types`

后端根据设备的 Vendor Client 能力和 Device Profile 返回过滤后的类型与字段，避免全局 Schema 将 Note 4 的 `page_id` 暴露给 Quote/0。

创建或更新调度时执行：

- 型号显示能力校验。
- Vendor 协议字段校验。
- 型号专属参数校验。
- 不支持字段的明确错误提示。

### 8.4 Device 响应

设备读模型增加：

- `vendor`
- `vendor_label`
- `vendor_capabilities`
- `device_model`
- `device_model_label`
- `display_width`
- `display_height`
- `display_capabilities`

现有 `vendor` 字段继续保留，不迁移为 `platform`。

### 8.5 Credential 保存结果

按 Vendor 返回：

- `validated`：通过安全的只读接口验证。
- `unverified`：Vendor 没有安全的只读验证接口。
- `invalid`：Vendor 明确拒绝凭据。

“Credential 保存成功”和“远端设备同步成功”是两个独立状态。

## 9. 数据库迁移

现有 `api_credential.vendor = 'mindreset'` 是正确数据，不应迁移为 `quote0`。

迁移步骤：

1. 保留 `ApiCredential.vendor` 及其现有 `mindreset` 值。
2. 注册新的 `zectrix` Vendor，使 Zectrix API Key 使用独立凭据记录。
3. 为 Device 增加 `device_model` 字段或 `device_model_id` 外键。
4. 将现有 MindReset 设备回填为 `quote0`。
5. 新建 Zectrix 设备时写入 `note4`。
6. 添加约束，确保 Device Model 所属 Vendor 与 Credential Vendor 一致。
7. 保留设备、调度、状态缓存和 Credential 关联关系。
8. 清理不支持型号上的电池 Overlay 历史值。

迁移必须在事务中执行。发现未知 Vendor、无法识别的 Model 或归属冲突时停止迁移并报告，不自动删除数据。

## 10. 调度与错误处理

- Vendor Client 按 `(vendor, credential_id)` 复用。
- Device Profile 按 `device_model` 获取。
- 同一 Vendor 的多个型号可以复用 Client，但使用不同 Profile。
- Model 与 Vendor 不匹配时跳过该设备任务并记录配置错误。
- 单个设备失败不影响其他 Vendor 或设备。
- 日志包含设备名、Vendor、Model 和调度 ID，但不记录 API Key。
- 不支持状态接口的 Vendor 不启动状态轮询。
- 旧 Quote/0 Web 调度兼容层最终应迁移到 MindReset Vendor Client；删除兼容层前必须保留完整远程管理能力。

## 11. 实施优先级

### P0：领域模型与运行链路

- 拆分 Vendor Registry 与 Device Model/Profile Registry。
- 为 Device 增加 Model，回填现有 MindReset 设备为 Quote/0。
- Web 调度器按 Vendor 创建 Client、按 Model 传入 Profile。
- 后端校验 Vendor、Credential、Model 的归属关系。
- 保证 MindReset Quote/0 现有管理功能不回归。

### P1：核心管理界面

- Settings 支持 MindReset 与 Zectrix Credential。
- Devices 支持 Vendor、Credential 和 Device Model 分层选择。
- 支持手工添加 Zectrix Note 4。
- Schedule Form 按具体设备过滤能力和 `page_id`。
- RemoteDevicePanel 与 Overlay 按能力显示。

### P2：体验增强

- Credential 验证状态与首次推送错误展示。
- Vendor 与 Device Model 双维度筛选。
- 型号化帮助文案和空状态。
- Web Demo/预览按 Device Profile 生成。

## 12. 验收标准

### 领域模型

- `mindreset` 和 `zectrix` 表示 Vendor。
- `quote0` 和 `note4` 表示 Device Model。
- Credential 归属 Vendor，不直接归属 Device Model。
- Device 同时关联 Credential 与 Device Model，并校验二者 Vendor 一致。

### MindReset Quote/0 回归

- 现有 `mindreset` Credential 无需改名即可继续使用。
- 现有设备迁移后 Model 为 `quote0`。
- 设备同步、状态、设置、时区、内容切换和内容列表正常。
- 图片输出为 296×152，文本和图片调度均可创建与执行。

### Zectrix Note 4

- 可以创建 `zectrix` Credential。
- 可以手工添加 Model 为 `note4` 的设备。
- 设备显示 Vendor Zectrix、Model Note 4、400×300、仅图片能力。
- 不能创建 `text` 调度。
- 图片类调度可选择 1–5 的页面并按 400×300 渲染。
- 不展示或请求当前不支持的状态、设置、时区和内容操作。
- 不展示电池 Overlay，刷新时间 Overlay 仍可使用。

### 安全与兼容

- API 响应和日志不泄露完整 API Key。
- 非本机绑定仍要求 `ADMIN_TOKEN`。
- 数据迁移失败时不产生部分迁移。
- 前后端都校验 Vendor 与 Model 能力。
- Web 后端测试、前端测试和两种设备型号的调度集成测试全部通过。

## 13. 建议测试清单

- Vendor Registry 与 Device Model Registry 测试。
- Vendor、Credential、Model 归属关系校验测试。
- 现有 MindReset Device 回填 Quote/0 Model 的迁移与回滚测试。
- MindReset 与 Zectrix Credential 创建流程测试。
- Quote/0 自动发现与 Note 4 手工创建设备测试。
- 跨 Vendor 改绑 Credential 拒绝测试。
- 不属于 Vendor 的 Device Model 拒绝测试。
- 设备级 Schedule Schema 快照测试。
- Note 4 文本调度拒绝、`page_id` 边界和无效字段测试。
- 调度器选择正确 Vendor Client 与 Device Profile 的测试。
- 296×152 与 400×300 输出尺寸断言。
- 不支持状态的 Vendor 不进入状态轮询测试。
- MindReset Quote/0 远程控制完整回归测试。
