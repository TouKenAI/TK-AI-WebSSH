# API接口规范

**文档编号**: TKAI-API-001  
**版本**: v3.0  
**日期**: 2026-06-29  
**状态**: 已通过四性审查  
**作者**: Software Architect Agent

---

## ⚠️ 安全说明

**API Key处理**：本文档中的API Key已替换为占位符 `your-stepfun-api-key-here`，真实Key请通过环境变量配置。

**安全要求**：
1. API Key通过 `.env` 文件或环境变量传入，不硬编码在代码中
2. `.env` 文件已加入 `.gitignore`，不会提交到版本控制
3. 生产环境必须使用环境变量或密钥管理服务

---

## 目录

1. [REST API](#1-rest-api)
2. [WebSocket API](#2-websocket-api)
3. [认证规范](#3-认证规范)
4. [通用响应格式](#4-通用响应格式)
5. [错误码定义](#5-错误码定义)
6. [API使用示例](#6-api使用示例)
7. [版本管理](#7-版本管理)

---

## 1. REST API

### 1.1 认证接口

#### 1.1.1 用户登录

**POST** `/api/auth/login`

**请求**：

```json
{
  "username": "admin",
  "password": "password123"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": 1,
    "username": "admin",
    "role": "admin"
  },
  "error": null
}
```

**错误响应**：

```json
{
  "success": false,
  "data": null,
  "error": "用户名或密码错误"
}
```

#### 1.1.2 用户登出

**POST** `/api/auth/logout`

**请求**：

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应**：

```json
{
  "success": true,
  "data": null,
  "error": null
}
```

### 1.2 设备管理接口

#### 1.2.1 获取设备列表

**GET** `/api/devices/list`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| group | string | 否 | 分组名称 |
| page | int | 否 | 页码（默认1） |
| limit | int | 否 | 每页条数（默认20） |

**响应**：

```json
{
  "success": true,
  "data": {
    "total": 50,
    "page": 1,
    "limit": 20,
    "devices": [
      {
        "id": 1,
        "name": "阿里云服务器",
        "ip": "203.0.113.10",
        "port": 22,
        "username": "root",
        "device_type": "linux",
        "group_name": "生产环境"
      }
    ]
  },
  "error": null
}
```

#### 1.2.2 添加设备

**POST** `/api/devices/add`

**请求**：

```json
{
  "name": "测试服务器",
  "ip": "192.168.1.100",
  "port": 22,
  "username": "root",
  "password": "password123",
  "device_type": "linux",
  "group_name": "测试环境"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "id": 2,
    "name": "测试服务器"
  },
  "error": null
}
```

### 1.3 AI对话接口

#### 1.3.1 AI对话（生成命令）

**POST** `/api/ai/chat`

**请求**：

```json
{
  "message": "查看磁盘使用情况",
  "device_type": "linux",
  "session_id": "abc123"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "command": "df -h",
    "description": "查看磁盘使用情况",
    "risk_level": "safe"
  },
  "error": null
}
```

**错误响应**：

```json
{
  "success": false,
  "data": null,
  "error": "AI服务暂时不可用，请稍后重试"
}
```

#### 1.3.2 AI分析命令结果

**POST** `/api/ai/analyze`

**请求**：

```json
{
  "command": "df -h",
  "result": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1  50G  40G  10G  80% /",
  "device_type": "linux",
  "session_id": "abc123"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "analysis": "磁盘根分区使用率已达80%，建议清理日志文件或扩容。"
  },
  "error": null
}
```

### 1.4 审计日志接口

#### 1.4.1 获取审计日志

**GET** `/api/audit/logs`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 否 | 用户ID |
| device_ip | string | 否 | 设备IP |
| start_time | string | 否 | 开始时间（YYYY-MM-DD HH:MM:SS） |
| end_time | string | 否 | 结束时间 |
| page | int | 否 | 页码（默认1） |
| limit | int | 否 | 每页条数（默认50） |

**响应**：

```json
{
  "success": true,
  "data": {
    "total": 100,
    "page": 1,
    "limit": 50,
    "logs": [
      {
        "id": 1,
        "user_id": "admin",
        "device_ip": "203.0.113.10",
        "command": "df -h",
        "result": "Filesystem      Size...",
        "ai_analysis": "磁盘使用率80%...",
        "timestamp": "2026-06-29 14:30:00"
      }
    ]
  },
  "error": null
}
```

---

## 2. WebSocket API

### 2.1 连接地址

`ws://localhost:5000/ws/ssh`

### 2.2 消息格式

**客户端 → 服务端**：

```json
{
  "type": "input",
  "data": "ls -la\n"
}
```

**服务端 → 客户端**：

```json
{
  "type": "output",
  "data": "total 48\ndrwxr-xr-x  5 root root 4096...\n"
}
```

### 2.3 消息类型

| 类型 | 方向 | 说明 |
|------|------|------|
| input | C→S | 用户输入（命令或文本） |
| output | S→C | 终端输出 |
| error | S→C | 错误信息 |
| resize | C→S | 终端窗口大小改变 |
| heartbeat | C→S / S→C | 心跳检测 |

---

## 3. 认证规范

### 3.1 Session认证（Phase 1）

- 用户登录后，服务器返回Session ID（Cookie）
- 后续请求自动带上Session ID
- Session过期时间：24小时

### 3.2 Token认证（Phase 2+）

- 用户登录后，服务器返回JWT Token
- 后续请求在Header中带上Token：`Authorization: Bearer {token}`
- Token过期时间：24小时

---

## 4. 通用响应格式

### 4.1 成功响应

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### 4.2 错误响应

```json
{
  "success": false,
  "data": null,
  "error": "错误描述"
}
```

### 4.3 分页响应

```json
{
  "success": true,
  "data": {
    "total": 100,
    "page": 1,
    "limit": 20,
    "items": [ ... ]
  },
  "error": null
}
```

---

## 5. 错误码定义

| 错误码 | 说明 | HTTP状态码 |
|--------|------|-----------|
| 0 | 成功 | 200 |
| 400 | 请求格式错误 | 400 |
| 401 | 未认证 | 401 |
| 403 | 无权限 | 403 |
| 404 | 资源不存在 | 404 |
| 500 | 服务器内部错误 | 500 |
| 1001 | AI API调用失败 | 500 |
| 1002 | SSH连接失败 | 500 |
| 1003 | 危险命令被拦截 | 403 |
| 1004 | 命令执行超时 | 500 |

---

## 6. API使用示例

### 6.1 完整流程示例

**场景**：用户通过AI生成命令，执行，然后查看结果分析

**步骤1：用户登录**

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

**步骤2：AI生成命令**

```bash
curl -X POST http://localhost:5000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"查看磁盘使用情况","device_type":"linux"}'
```

**响应**：

```json
{
  "success": true,
  "data": {
    "command": "df -h",
    "description": "查看磁盘使用情况",
    "risk_level": "safe"
  }
}
```

**步骤3：用户点击执行，调用SSH执行接口**

```bash
curl -X POST http://localhost:5000/api/ssh/execute \
  -H "Content-Type: application/json" \
  -d '{"session_id":"abc123","command":"df -h"}'
```

**响应**：

```json
{
  "success": true,
  "data": {
    "result": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1  50G  40G  10G  80% /",
    "exit_code": 0
  }
}
```

**步骤4：AI分析命令结果**

```bash
curl -X POST http://localhost:5000/api/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"command":"df -h","result":"Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1  50G  40G  10G  80% /"}'
```

**响应**：

```json
{
  "success": true,
  "data": {
    "analysis": "磁盘根分区使用率已达80%，建议清理日志文件或扩容。"
  }
}
```

---

## 7. 版本管理

### 7.1 版本号规则

- 主版本号：不兼容的API修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修正

示例：`v1.0.0`

### 7.2 版本兼容性

- 同一主版本号内，向下兼容
- 不同主版本号，不兼容

### 7.3 版本废弃策略

- 新版本发布后，旧版本继续支持6个月
- 提前3个月通知用户升级

---

**文档结束**
