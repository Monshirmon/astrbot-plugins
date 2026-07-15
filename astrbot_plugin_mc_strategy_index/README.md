# MC公会萌新攻略索引

AstrBot 插件。面向 MC 服务器公会社群，萌新自助查攻略、管理员自动化运维攻略库。**零内置资源，全部由人工上传构建。**

## 核心闭环

```
管理员上传图文 → 自动建库 → 玩家发触发词自动回复 → 管理员巡检 → AI生成索引图
```

## 命令列表

### 公开命令

| 命令 | 示例 | 说明 |
|------|------|------|
| 直接发送触发词 | `龙神打法` | 严格匹配触发词，自动返回图文攻略 |
| `/查攻略 <关键词>` | `/查攻略 钻石` | 模糊搜索攻略名/分类/内容 |
| `/攻略列表 [分类]` | `/攻略列表 副本类` | 按分类查看 / 列出全部分类 |
| `/索引` | `/索引` | 查看全部触发词 + 索引引导图 |

### 管理员命令

| 命令 | 示例 | 说明 |
|------|------|------|
| `/上传攻略` | `/上传攻略 龙神打法 副本类` + 图片 + 文字 | 上传攻略（名+分类+多图+文字） |
| `/上传攻略 批量` | `/上传攻略 批量` + ZIP | 批量导入攻略包 |
| `/巡检攻略` | `/巡检攻略` | 全库巡检异常 + 自动更新索引图 |
| `/整改攻略 <id>` | `/整改攻略 1` | AI 整改指定攻略图片 |
| `/编辑攻略 <id> <字段> <值>` | `/编辑攻略 1 trigger_words 龙神,副本` | 修改攻略元数据 |
| `/删除攻略 <id>` | `/删除攻略 1` | 删除攻略及全部图片 |
| `/替换攻略图 <id>` | `/替换攻略图 1` + 多张图片 | 替换全部图片 |
| `/攻略分类管理` | `/攻略分类管理 add 副本类` | 分类增删 |
| `/攻略日志 [条数]` | `/攻略日志` | 查看操作日志 |

## 上传格式

```
/上传攻略 <攻略名> <分类名> [图片1] [图片2] ... [额外文字...]
```

- 攻略名自动成为触发词，新分类自动创建
- 图片可发多张，全部收录，触发时一起发送
- 指令后的文字自动作为攻略内容，不会被指令前缀污染

## 内置特殊触发词

| 触发词 | 效果 |
|--------|------|
| `开光线` | 返回随机 1-14 的数字 + "线"，例如 `7线` |

## 触发词冲突处理

上传时自动检测同名触发词，如发现冲突，从旧攻略中移除冲突词并绑定到新攻略，同时告知管理员冲突已自动解决。

## 配置项

| 配置 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `admin_whitelist` | list | `[]` | 管理员白名单 QQ 号 |
| `notify_permission_denied` | bool | `true` | 无权限时发送提示 |
| `enable_image_edit` | bool | `false` | 启用 AI 图片整改 |
| `image_api_provider` | string | `openai` | API 提供商 |
| `image_api_key` | string | `""` | API 密钥 |
| `image_api_base_url` | string | `https://api.openai.com` | API 地址 |
| `image_api_model` | string | `gpt-4o` | 模型名称 |
| `max_image_size_kb` | int | `5120` | 图片大小上限 (KB) |

## 项目结构

```
astrbot_plugin_mc_strategy_index/
├── main.py                          # 插件入口：命令注册 + 消息监听
├── metadata.yaml                    # 元信息
├── _conf_schema.json                # 配置面板
├── .gitignore                       # 排除 data/ 目录（保护用户数据）
├── modules/
│   ├── utils.py                     # 核心工具：数据读写、触发词匹配、消息构建、索引图
│   ├── resource_upload.py           # 资源上传（单文件 + ZIP 批量）
│   ├── player_search.py             # 玩家模糊检索
│   ├── admin_inspect.py             # 管理员巡检、整改、日志
│   ├── resource_management.py       # 增删改查、分类、替换图片
│   ├── image_api.py                 # 图片编辑 API 对接
│   └── trigger_match.py             # 严格触发词匹配（无前缀自动回复）
├── webui/
│   ├── api.py                       # WebUI 后端（含图库导出接口）
│   └── payloads.py                  # 数据序列化
└── pages/strategy-console/
    ├── index.html                   # 管理控制台
    ├── style.css                    # 样式
    └── app.js                       # 前端 SPA
```

## 数据存储

数据文件 `strategy_index.json`，图片存储在 `images/`，均在 AstrBot 的 `data/` 目录下，受 `.gitignore` 保护，更新插件不会覆盖。

```json
{
  "strategies": [{
    "id": "abc123def456",
    "name": "龙神打法",
    "category": "副本类",
    "trigger_words": ["龙神打法"],
    "status": "normal",
    "text_content": "注意站位和技能循环...",
    "image_paths": ["img_xxx.png"]
  }],
  "categories": ["副本类"],
  "index_image_path": "index_xxx.png",
  "logs": []
}
```

## 部署

1. 将插件目录放入 AstrBot 的 `data/plugins/`
2. 在 AstrBot 后台 → 插件管理 → 启用插件
3. 在插件配置中设置 `admin_whitelist`（你的 QQ 号）
4. （可选）配置 `image_api_key` 启用 AI 整改
5. 重启或热加载

## WebUI 控制台

AstrBot 后台 → 插件 → MC公会萌新攻略索引 → 打开控制台：

- 左侧攻略列表（全部/已规范/待整改筛选 + 搜索）
- 右侧编辑面板（名称、分类、触发词标签、文字内容、多图预览上传）
- 顶部 📦 按钮：导出全部图片为 ZIP（含确认弹窗）
- 统计面板：总攻略数、已规范数、待整改数、图库图片数

## 许可

MIT
