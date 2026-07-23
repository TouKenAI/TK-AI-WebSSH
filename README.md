# TKAI SSH

**Web SSH终端 + AI Agent助手** — 面向纯内网环境的智能运维平台。

让不懂命令行的人也能通过自然语言运维Linux服务器和网络设备。

## 核心功能

- **Web SSH终端** — 浏览器直接操作，无需安装客户端
- **AI Copilot** — 自然语言生成命令，人工确认后执行
- **危险命令拦截** — 30+危险模式自动拦截，防止误操作
- **AI结果分析** — 命令执行后自动分析结果，给出中文建议
- **多设备支持** — Linux服务器、华为VRP、思科IOS
- **完整审计日志** — 所有操作可追溯
- **SFTP文件传输** — 上传/下载/在线编辑
- **跳板机支持** — 多跳SSH连接
- **密钥管理** — SSH密钥上传/加密存储
- **用户管理** — 多用户+管理员面板

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.13 + Flask 3.x + Flask-SocketIO |
| 前端 | HTML + JS + xterm.js + WebSocket |
| SSH | paramiko |
| AI | 阶跃星辰 StepFun API (step-3.5-flash-2603) |
| 数据库 | SQLite + Flask-SQLAlchemy |
| 部署 | Docker / 直接运行 |

## 快速开始

```bash
# 1. 安装依赖
cd webssh
python -m venv venv
source venv/bin/activate  # Linux
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的阶跃星辰 API Key

# 3. 启动
python start.py

# 4. 访问
# http://127.0.0.1:5000
```

## AI交互模式

```
用户：帮我查看服务器磁盘使用情况
AI：建议执行命令 df -h（安全级别：safe）
用户：[点击执行]
AI：根分区使用率85%，建议清理日志文件。
```

## 项目结构

```
tkai-ssh/
├── docs/                    # 架构文档（6个）
├── webssh/                  # 主应用
│   ├── app/
│   │   ├── ai/              # AI模块（新增）
│   │   │   ├── stepfun_provider.py   # 阶跃星辰API调用
│   │   │   ├── command_generator.py  # 危险命令拦截
│   │   │   └── routes.py             # AI API路由
│   │   ├── auth.py          # 认证系统
│   │   ├── audit_logger.py  # 审计日志
│   │   ├── ssh_manager.py   # SSH连接管理
│   │   └── ...
│   ├── static/
│   │   ├── css/ai-assistant.css  # AI侧边栏样式
│   │   └── js/ai-assistant.js    # AI交互逻辑
│   ├── templates/
│   └── config.py            # 配置
└── .env.example             # 环境变量示例
```

## 安全特性

- API Key通过环境变量传入，不硬编码
- 危险命令自动拦截（rm -rf /、mkfs、dd等）
- CSRF保护 + 速率限制
- SSH密钥加密存储
- 完整操作审计日志

## 开发计划

| 阶段 | 目标 | 状态 |
|------|------|------|
| Phase 1 | AI Copilot（生成命令+人工确认） | ✅ 完成 |
| Phase 2 | Web界面增强 + 网络设备支持 | 规划中 |
| Phase 3 | Semi-Agent（自主执行安全命令） | 规划中 |
| Phase 4 | Windows支持 + 本地LLM | 规划中 |

## 致谢

基于 [bifrost0x/webssh](https://github.com/bifrost0x/webssh) (MIT) 二次开发。

## License

MIT
