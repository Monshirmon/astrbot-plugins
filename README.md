# AstrBot 插件集合（存档）

> ⚠️ 插件已迁移至独立仓库进行维护：
> - [astrbot_plugin_mc_strategy_index](https://github.com/Monshirmon/astrbot_plugin_mc_strategy_index)
> - [astrbot_plugin_silence_ban](https://github.com/Monshirmon/astrbot_plugin_silence_ban)
>
> 本分支仅保留历史代码，不再更新。

欢迎来到慕雪梦的插件仓库。

## 插件列表

| 插件目录 | 说明 |
|---------|------|
| `astrbot_plugin_mc_strategy_index/` | MC策略索引插件 |
| `说不理你就不理你！/` | 沉默/不理人玩法插件 |

---

## 版本更新日志

### astrbot_plugin_mc_strategy_index

#### v2.0.0 (2026-07-15)

- 正式纳入 Git 管理，规范化代码结构
- 新增 `.gitignore` 文件
- 完善 `modules/` 模块目录（admin_inspect、image_api、player_search、resource_management、resource_upload、trigger_match、utils）
- 新增 `pages/strategy-console/` 前端策略控制台（app.js、index.html、style.css）
- 完善 `webui/` 后端接口（api.py、payloads.py）
- 全面更新 main.py 核心逻辑
- 更新配置描述文件 `_conf_schema.json`
- 优化 README.md 文档

#### v1.0.0 (2026-07-11)

- 初始版本，手动上传
- 基础 MC 策略索引功能
- 包含 main.py、metadata.yaml、基础配置
