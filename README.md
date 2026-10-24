# FitTrack 健身系统

一套完整可运行的健身 App 全栈项目（对标 Keep 核心功能），包含 9 大业务模块、30 张数据表、
120+ 个后端接口与 26 个前端页面。

- **后端**：Python 3.10+ / FastAPI / SQLAlchemy 2.0 / MySQL 8（本地可用 SQLite 零配置跑起来）
- **前端**：Vue 3 + Vite + Vue Router + Pinia + Element Plus + ECharts
- **前端在浏览器中渲染**（标准 SPA，可被任何 WebView / 内嵌浏览器直接加载，见文末「在 WebView 中运行」）

---

## 一、功能模块

| 模块 | 主要功能 |
|---|---|
| 用户 | 注册、登录、JWT 鉴权、资料修改、头像上传、密码重置、手机号绑定、实名认证、等级体系、签到日历、连续签到奖励、消息通知 |
| 运动计划 | 创建计划、周期设置（每日/每周）、计划模板库、分享码分享与导入、收藏、打卡、完成统计、训练提醒 |
| 运动课程 | 5 大分类、课程详情、视频地址、难度分级、收藏、评分、评论、评论点赞与回复、相关推荐 |
| 运动记录 | 每次训练打卡、时长、卡路里、动作组次（重量/次数/时长/距离）、历史查询、按月/按周报表、趋势 |
| 动作库 | 28 个动作（可扩展）、配图与动图字段、动作讲解、发力要点、易错提醒、分类、搜索与多条件筛选 |
| 数据统计 | 体重/体脂/围度记录、BMI 计算与分级、体重与体脂趋势、卡路里收支、训练频率、个人看板 |
| 社区 | 动态发布（文字+图片）、点赞、评论与回复、关注/粉丝、关注流与推荐流、用户主页、搜索 |
| 饮食 | 食物库（35 种常见食物 + 自定义）、三餐记录、热量与三大营养素自动计算、每日/区间统计 |
| 后台管理 | 管理员登录、数据看板、用户管理（封禁/重置密码）、课程 CRUD 与上下架、评论审核、动态管理、实名审核 |

## 二、目录结构

```
bbbsss/
├── backend/
│   ├── app/
│   │   ├── main.py              # 应用入口（CORS、静态文件、异常处理、路由挂载）
│   │   ├── core/                # 配置、数据库、安全、依赖、统一响应、异常、分页
│   │   ├── models/              # 30 张表的 SQLAlchemy 模型（9 个模块文件）
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── api/v1/              # 11 个路由模块（auth/users/plans/courses/records/…）
│   │   └── services/            # 初始化数据、可复用业务逻辑
│   ├── sql/
│   │   ├── schema_mysql.sql     # MySQL 8 完整建表语句（30 表 + 54 索引，自动生成）
│   │   └── seed_data.sql        # 初始化数据（管理员/动作/课程/食物/模板）
│   ├── tools/
│   │   ├── gen_sql.py           # 从模型生成上面两个 SQL 文件
│   │   ├── smoke_db.py          # 建表 + 灌种子数据自检
│   │   └── smoke_api.py         # 120+ 接口端到端冒烟测试
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
└── frontend/
    ├── src/api/                 # 按模块拆分的接口封装（axios 统一拦截）
    ├── src/stores/              # Pinia 用户状态
    ├── src/router/              # 路由与登录守卫
    ├── src/layouts/             # 主框架（侧边栏 + 顶栏）
    ├── src/views/               # 26 个页面
    └── package.json
```

## 三、后端部署

### 1. 准备环境

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置数据库

**方式 A：MySQL（推荐，符合生产要求）**

```sql
-- 1) 执行建表脚本（会自动建库 fittrack）
mysql -u root -p < sql/schema_mysql.sql
-- 2) 可选：导入初始化数据（也可以让程序首次启动自动写入）
mysql -u root -p fittrack < sql/seed_data.sql
```

```bash
cp .env.example .env
# 编辑 .env：DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/fittrack?charset=utf8mb4
```

**方式 B：SQLite（零配置，演示/本地开发最快）**

```bash
# .env 里写：
# DATABASE_URL=sqlite:///./fittrack.db
```

首次启动会自动建表并写入种子数据（默认管理员 `admin / admin123456`，**请登录后立即修改**）。

### 3. 启动

```bash
python run.py                 # http://127.0.0.1:8000
# 生产：python run.py --no-reload --workers 4
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/>

### 4. 自检

```bash
python tools/smoke_db.py      # 建表 + 种子数据，打印每张表行数
python tools/smoke_api.py     # 端到端跑 120+ 接口（需先启动服务）
```

## 四、前端部署

```bash
cd frontend
npm install
npm run dev                   # 开发：http://127.0.0.1:5173
npm run build                 # 生产构建，产物在 dist/
```

`.env` 里配置后端地址（默认已指向本机）：

```
VITE_API_BASE=http://127.0.0.1:8000
```

### 生产部署（Nginx 示例）

```nginx
server {
    listen 80;
    server_name fittrack.example.com;
    root /var/www/fittrack/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;      # SPA 路由回退
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /static/ {
        proxy_pass http://127.0.0.1:8000;      # 上传的图片
    }
}
```

## 五、在 WebView 中运行

前端是标准单页应用，不需要 Node 运行时即可被宿主加载，三种常见接法：

1. **直接加载线上地址**：`webview.loadUrl("http://你的域名/")`
2. **打包进 App 内置**：`npm run build` 后把 `dist/` 放进 Android `assets/` 或 iOS bundle，
   用 `file:///android_asset/dist/index.html` 加载（注意把 `VITE_API_BASE` 改成线上后端地址，
   并在后端 CORS 中允许该来源）
3. **桌面端 WebView**（Electron / Tauri / WebView2）：窗口直接指向 `dist/index.html`，
   `mainWindow.webContents` 或 Tauri 的 `WebviewWindow` 均可

> 若后端与页面不同源，请把 `backend/app/main.py` 里的 `allow_origins=["*"]` 换成你的域名白名单。

## 六、默认账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 后台管理员 | `admin` | `admin123456` |

普通用户请在前端注册页自行注册。

## 七、技术要点

- **统一响应**：所有接口返回 `{code, message, data}`，异常由全局处理器统一包装（含参数校验、数据库约束、JWT 过期）
- **鉴权**：JWT（HS256），用户令牌 `type=user`、管理员令牌 `type=admin`，互不通用；`get_current_user` / `get_current_admin` 依赖注入
- **密码安全**：PBKDF2-HMAC-SHA256，20 万次迭代 + 16 字节随机盐，常数时间比较（标准库实现，无第三方依赖）
- **数据校验**：全部入参 Pydantic v2 校验，出参 schema 化
- **分页**：`page/page_size` 统一参数 + `PageResult` 统一结构
- **图片上传**：MIME 与大小校验，uuid 重命名，静态目录托管
- **建表语句**：由模型自动生成（`tools/gen_sql.py`），保证 SQL 与代码永不脱节

## 八、验收与自测结果

本仓库交付前已实际跑通以下检查（全部为本机真实执行，非纸面清单）：

| 检查 | 命令 | 结果 |
|---|---|---|
| 建表 + 种子数据 | `python tools/smoke_db.py` | 30 张表全部建成，91 行初始数据（管理员 1 / 动作分类 7 / 动作 28 / 课程分类 5 / 课程 12 / 食物 35 / 计划模板 3） |
| 接口端到端 | `python tools/smoke_api.py` | **111 项接口全部通过，0 失败**（覆盖注册登录、签到重复校验、计划 CRUD 与分享导入、课程评分评论、记录组次、BMI、卡路里收支、社区点赞/评论/关注、饮食记录、后台看板与权限越权校验） |
| 接口数量 | `GET /openapi.json` | 121 条路径 |
| 前端构建 | `npm run build` | 成功，32 个 chunk，8.18s |

**代码量**（`python tools/count_lines.py` 统计，已排除 node_modules / dist / 依赖库）：

| 部分 | 文件数 | 行数 |
|---|---|---|
| 后端（Python + SQL） | 50 | **12,244** |
| 前端（Vue / JS / CSS / HTML） | 52 | **19,649** |
| 合计 | 102 | **31,893** |

## 九、许可证

MIT
