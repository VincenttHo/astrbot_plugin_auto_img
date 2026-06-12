# astrbot_plugin_auto_img
定时发图插件

## 功能特性

- 支持定时自动发送图片到群聊或私聊
- 支持两种图库API，**每个用户可以单独配置使用不同的API**：
  - **lolicon API**：功能丰富，支持标签筛选、R18控制、详细信息展示等。图库涩图偏多，甚至可以获取R18图片。
  - **alcy API**：简洁快速，支持多种分类，参数简单。图库比较小清新，没有涩图。
- 支持自定义标签设置
- 支持排除特定时间段
- 支持转发消息格式
- 支持AI生成评论（仅lolicon API）

## 配置说明

### 基础配置

- `bot_qq`: 机器人的QQ号
- `image_size`: 图片质量控制（仅lolicon API有效），可选：original, regular, small, thumb, mini
- `schedule`: 定时任务配置（JSON格式），每个任务可以单独设置API类型
- `exclude_time`: 排除的时间段设置
- `send_img_messages`: 发图时的附加消息
- `proxy`: pixiv反代服务地址，默认 `i.pixiv.re`

### 定时任务配置（schedule）

**重要**：每个定时任务可以通过 `api_type` 字段单独指定使用哪个API，不同用户可以使用不同的API。

#### 使用 lolicon API 的配置

```json
[
  {
    "id": "群号或QQ号",
    "type": "GROUP",
    "api_type": "lolicon",
    "interval_sec": 3600,
    "send_forward": false,
    "detail_mode": "full",
    "call_ai": false,
    "r18": 0,
    "exclude_tags": ["标签1", "标签2"]
  }
]
```

参数说明：
- `id`: 目标群号或QQ号
- `type`: 消息类型，GROUP（群聊）或 FRIEND（私聊）
- `api_type`: API类型，设置为 `lolicon`（不设置时默认为lolicon）
- `interval_sec`: 发送间隔（秒）
- `send_forward`: 是否使用转发消息格式
- `detail_mode`: 图片信息显示模式，`full` 完整显示（标题、作者、PID、标签），`brief` 简略显示（标题、作者、PID），`none` 不显示详情；旧配置 `show_detail` 仍然兼容
- `call_ai`: 是否调用AI生成评论
- `r18`: R18等级（0=非R18, 1=R18, 2=混合）
- `exclude_tags`: 排除的标签列表

#### 使用 alcy API 的配置

```json
[
  {
    "id": "群号或QQ号",
    "type": "GROUP",
    "api_type": "alcy",
    "interval_sec": 3600,
    "send_forward": false,
    "category": "pc",
    "count": 1
  }
]
```

参数说明：
- `id`: 目标群号或QQ号
- `type`: 消息类型，GROUP（群聊）或 FRIEND（私聊）
- `api_type`: API类型，设置为 `alcy`
- `interval_sec`: 发送间隔（秒）
- `send_forward`: 是否使用转发消息格式
- `category`: 图片分类，可选值：pc, ai, aimp, bd, fj, fjmp, lai, moe, moemp, mp, tx, xhl, ys, ysmp
- `count`: 每次获取的图片数量（默认1）

#### 混合使用示例

可以在同一个配置中为不同用户设置不同的API：

```json
[
  {
    "id": "123456789",
    "type": "GROUP",
    "api_type": "lolicon",
    "interval_sec": 3600,
    "r18": 0,
    "detail_mode": "brief"
  },
  {
    "id": "987654321",
    "type": "GROUP",
    "api_type": "alcy",
    "interval_sec": 7200,
    "category": "pc",
    "count": 2
  }
]
```

## 命令使用

- `/auto_img set_my_tags [标签设置]` - 设置自定义标签（仅lolicon API）
  - 标签设置支持多个，`&`表示and，`|`表示or
  - 示例：`JK|黑丝&雷姆|拉姆`（请不要带空格）
- `/auto_img my_tags` - 查看当前的标签设置
- `/auto_img get` - 根据当前设置立即获取一张图片
- `/auto_img help` - 显示帮助信息

## API对比

| 特性 | lolicon API | alcy API |
|------|-------------|----------|
| 标签筛选 | ✅ | ❌ |
| R18控制 | ✅ | ❌ |
| 详细信息 | ✅ | ❌ |
| AI评论 | ✅ | ❌ |
| 分类选择 | ❌ | ✅ |
| 响应速度 | 中等 | 快速 |
| 参数复杂度 | 较高 | 简单 |

## 注意事项

- 两种API可以在不同的定时任务中混合使用，每个任务通过 `api_type` 字段单独指定
- 如果不设置 `api_type` 字段，默认使用 lolicon API
- lolicon API的参数（如r18、detail_mode、call_ai、exclude_tags）在使用alcy API时不生效
- alcy API的参数（如category、count）在使用lolicon API时不生效
- 建议根据实际需求为每个用户选择合适的API
- `detail_mode` 设置为 `brief` 时只会显示标题、作者、PID，即使 `call_ai` 为 `true` 也不会追加AI评论

## 配置示例文件

项目中提供了三个配置示例文件供参考：
- `config_example.json` - 使用 lolicon API 的配置示例
- `config_example_alcy.json` - 使用 alcy API 的配置示例
- `config_example_mixed.json` - 混合使用两种API的配置示例
