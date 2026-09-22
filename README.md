# 校园失物招领语义匹配

移动优先的单页 H5。丢失者和拾获者分别用自然语言描述物品，后端用 embedding 计算语义相似度并自动匹配。

> 项目内置的 3 个演示账号、20 条发布和联系方式全部是模拟数据，不是真实校园数据。

## 当前功能

- 公开主界面：左侧展示全部“想找的信息”，右侧展示全部“找到的信息”。
- 注册登录：用户名 + 密码；密码使用 PBKDF2-HMAC-SHA256 加盐哈希；登录使用服务端 Session Cookie。
- 登录后发布：提交后留在主界面，自己的发布置顶并高亮。
- 中间匹配：只显示当前用户自己发布的物品所关联的、相似度大于等于 70% 的匹配。
- “匹配”按钮：在匹配卡片内展开双方用户名和联系方式。
- “确认找到”：每个自己的发布只有一个按钮；确认后删除该发布、所有与它匹配的对方发布，以及关联匹配记录。
- 未登录用户可以查看左右两侧公开信息，但不能发布、查看自己的匹配或联系方式。
- embedding 存进 SQLite；向量先归一化；cosine 使用 numpy 全量点乘；不使用向量数据库。

## 环境要求

- Python 3.11 或更高版本。
- 通义 Embedding API key（默认 provider）。
- 可选：切换智谱或本地 BGE 时需要对应配置或额外依赖。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

把通义 key 填入项目根目录的 `.env`：

```dotenv
DASHSCOPE_API_KEY=你的通义APIKey
```

`.env` 已被 `.gitignore` 忽略，不应提交。不要把真实 key 写进 `.env.example`。

## 灌入模拟数据

```powershell
python seed.py
```

脚本会清空旧演示数据，创建以下模拟账号并重新写入 20 条模拟发布：

| 用户名 | 密码 |
| --- | --- |
| `demo_lost` | `LostDemo123!` |
| `demo_found` | `FoundDemo123!` |
| `demo_other` | `OtherDemo123!` |

这些账号、帖子和联系方式只用于演示，不代表真实用户。`seed.py` 需要成功调用当前 embedding provider；key 无效时会显示中文错误，不会写入半套数据。

## 启动

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

电脑浏览器打开 `http://127.0.0.1:8000`。手机与电脑在同一局域网时，用电脑局域网 IP 访问 `http://电脑IP:8000`。

## 主界面说明

### 未登录

- 左侧：全部丢失信息。
- 右侧：全部拾获信息。
- 中间：提示登录后查看自己的匹配。
- 公开卡片不包含联系方式。

### 登录后

- 左右两侧仍为公开列表，自己的发布置顶并高亮。
- 中间按相似度从高到低显示自己的全部匹配，不限制 Top 3 或 Top 5。
- 点击某条匹配的“匹配”按钮，才展开该匹配双方的账号和联系方式。
- 每个自己的发布对应一个“确认找到”按钮。

“确认找到”删除范围较大：会删除当前发布、所有与它达到 70% 的对方发布，以及相关匹配记录。点击后前端会再次确认。

## 五条语义匹配验收

先确认 `.env` 中 `EMBEDDING_PROVIDER=qwen` 且 key 可用，然后执行：

```powershell
python evaluate.py
```

五条验收用例：

| 丢失描述 | 捡到描述 | 期望 |
| --- | --- | --- |
| 蓝色保温杯，400ml，图书馆三楼 | 水杯一个，深色的，三楼阅览室捡的 | 匹配 |
| 黑色长柄雨伞，教学楼 | 雨伞，直杆那种，教室门口捡的 | 匹配 |
| 白色 AirPods 充电盒 | 捡到一个白色耳机盒 | 匹配 |
| 蓝色保温杯 | 黑色双肩包，食堂 | 不匹配 |
| 学生证，姓李 | 一个黑色钱包 | 不匹配 |

当前实测结果在 `MATCH_THRESHOLD=0.70` 下全部通过。该值已写入 `.env` 和 `.env.example`。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/auth/register` | 注册并自动登录 |
| `POST` | `/api/auth/login` | 登录 |
| `POST` | `/api/auth/logout` | 退出 |
| `GET` | `/api/home` | 返回公开左右列表；登录时额外返回当前用户匹配和联系方式 |
| `POST` | `/api/report` | 登录后发布并计算、保存 70% 以上匹配 |
| `POST` | `/api/reports/{report_id}/complete` | 登录后确认找到并执行级联删除 |

“匹配”按钮只控制前端联系方式展开，不增加额外接口。

## 数据与安全

- `users`：用户名、PBKDF2 密码哈希、创建时间。
- `sessions`：Session token 哈希、用户、过期时间；Cookie 有效期 7 天。
- `reports`：发布记录，包含所有者、描述、地点、时间、必填联系方式、embedding。
- `matches`：发布对和相似度；删除发布时级联删除关联匹配。
- Session Cookie：`HttpOnly`、`SameSite=Lax`；本地 HTTP 开发环境未启用 `Secure`。
- 用户名重复、密码错误、未登录、越权确认和 embedding key 错误均返回中文提示。
- 前端保持原生 HTML/CSS/JS，无前端框架、无构建步骤。

## 配置项

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `EMBEDDING_PROVIDER` | `qwen` | `qwen`、`zhipu` 或 `local` |
| `MATCH_THRESHOLD` | `0.70` | 匹配最低 cosine 相似度 |
| `DATABASE_PATH` | `data/lost_found.db` | SQLite 文件路径 |
| `REQUEST_TIMEOUT` | `30` | 远端 Embedding 请求超时秒数 |
| `DASHSCOPE_API_KEY` | 空 | 通义 key，只能从 `.env` 读取 |
| `QWEN_EMBEDDING_MODEL` | `text-embedding-v3` | 通义模型名 |
| `ZHIPU_API_KEY` | 空 | 智谱 key，只能从 `.env` 读取 |
| `ZHIPU_EMBEDDING_MODEL` | `embedding-3` | 智谱模型名 |
| `LOCAL_EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 本地 BGE 模型名 |

本地 BGE 还需要：

```powershell
python -m pip install -r requirements-local.txt
```

## 项目边界

项目只做文字语义匹配、注册登录、公开收发信息列表、联系方式展开和一键确认找到。不包含邮件或短信验证、第三方登录、密码找回、管理员后台、站内通知、图片上传、视觉识别、关键词搜索、向量数据库、部署、域名、备案、小程序或桌面软件。
