# Bug Fix Kit MVP 产品需求文档

## 1. 产品定位

**Bug Fix Kit，简称 bfk**，是一个面向 AI Coding Agent 的本地 Bug 复现与修复插件。

MVP 阶段优先服务于本地 Python HTTP 服务调试场景。用户通过一个示例请求初始化可重放请求脚本；之后只需要提供一个新参数或少量参数，bfk 就可以辅助 AI 完成：

1. 构造真实本地请求
2. 执行请求回放
3. 基于日志文件 offset 采集本次新增日志
4. 结合本地代码定位异常
5. 执行最小代码修复
6. 复用同一个请求进行回归验证
7. 独立记录本次异常定位与修复结果

MVP 不做完整调试平台，不做远程日志，不做 Trace 系统，不做 YAML 配置。

---

## 2. 核心设计原则

1. **只保留核心链路**
   MVP 只保留初始化和修复两个主流程。

2. **不让用户理解 YAML / DSL**
   请求构造逻辑以 Python 脚本形式呈现。

3. **可变参数前置**
   每个请求 runner 顶部放置用户最常修改的参数。

4. **请求脚本可独立执行**
   用户可以手工运行 `.bfk/runner/<name>.py`，也可以由 `$bfk-fix` 自动调用。

5. **默认日志采集方式为 External HTTP + file offset**
   请求前记录日志文件 offset，请求后读取新增日志。

6. **每次执行独立记录**
   每次 `$bfk-fix` 都生成一个独立 run 目录，保存本次请求、响应、日志、诊断结论和验证结果。

7. **响应和日志分开保存**
   修复前后的 response 与 log 独立落盘，不合并到 markdown 文件中。

8. **修复后验证必须复用同一个请求**
   验证阶段优先复用本次 run 目录中的 `request.json`，避免重新拼接请求导致前后不一致。

---

## 3. MVP 命令设计

MVP 只保留两个主命令。

### 3.1 `$bfk-init`

用于初始化一个请求 runner。

#### 使用方式

```text
$bfk-init <request_name>
```

示例：

```text
$bfk-init login
```

#### 用户需要提供的信息

1. 示例请求，例如 curl 或真实 HTTP 请求信息
2. 本地服务地址，例如 `http://localhost:8000`
3. 日志文件路径，例如 `logs/app.log`
4. 后续常用可变参数
5. 如果用户只提供一个参数，该参数默认映射到哪个字段

#### 输出产物

```text
.bfk/runner/<request_name>.py
```

示例：

```text
.bfk/runner/login.py
```

#### 职责

`$bfk-init` 负责：

1. 创建 `.bfk/` 根目录
2. 创建 `.bfk/runner/` 目录
3. 基于示例请求生成 Python runner 脚本
4. 将可变参数放到 runner 文件顶部
5. 设置 `DEFAULT_SINGLE_PARAM_NAME`
6. 写入 base_url、log_files、等待日志时间等基础配置
7. 确保 runner 可以独立执行

---

### 3.2 `$bfk-fix`

用于基于新参数完成完整 Bug 修复闭环。

#### 使用方式

```text
$bfk-fix <request_name> <params>
```

示例一：只给一个参数

```text
$bfk-fix login 13900000000
```

示例二：给多个参数

```text
$bfk-fix login account=13900000000 password=123456
```

#### 职责

`$bfk-fix` 负责：

1. 找到 `.bfk/runner/<request_name>.py`
2. 将用户输入参数传给 runner
3. 执行修复前请求回放
4. 保存修复前请求、响应、日志
5. 结合本地代码和日志定位异常
6. 执行最小代码修复
7. 复用同一个 `request.json` 执行修复后验证
8. 保存修复后响应和日志
9. 生成本次异常定位与修复结果记录

---

## 4. MVP 目录结构

MVP 目录结构如下：

```text
.bfk/
├── runner/
│   └── login.py
└── runs/
    └── 20260625_143012_login/
        ├── request.json
        ├── before_response.json
        ├── before.log
        ├── after_response.json
        ├── after.log
        └── result.json
```

### 4.1 `.bfk/runner/`

保存请求 runner 脚本。

每个请求一个 Python 文件。

```text
.bfk/runner/login.py
.bfk/runner/create_order.py
.bfk/runner/query_order.py
```

### 4.2 `.bfk/runs/`

保存每次 `$bfk-fix` 的独立执行记录。

目录命名建议：

```text
<YYYYMMDD_HHMMSS>_<request_name>
```

示例：

```text
.bfk/runs/20260625_143012_login/
```

---

## 5. Runner 脚本设计

Runner 是 MVP 的核心产物。

它既是请求构造脚本，也是本地请求回放脚本。

### 5.1 Runner 文件位置

```text
.bfk/runner/<request_name>.py
```

示例：

```text
.bfk/runner/login.py
```

### 5.2 Runner 顶部结构

Runner 顶部必须放置用户最常修改的参数。

示例：

```python
# ============================================================
# 1. 可变参数区：用户通常只需要修改这里
# ============================================================

PARAMS = {
    "account": "13800000000",
    "password": "123456",
}

DEFAULT_SINGLE_PARAM_NAME = "account"

BASE_URL = "http://localhost:8000"

LOG_FILES = [
    "logs/app.log",
]

AFTER_REQUEST_WAIT_SECONDS = 2
```

### 5.3 Runner 请求构造函数

Runner 中必须包含 `build_request` 函数。

示例：

```python
def build_request(params: dict) -> dict:
    return {
        "method": "POST",
        "url": f"{BASE_URL}/api/login",
        "headers": {
            "Content-Type": "application/json",
            "X-BugFix-Run-Id": params["run_id"],
        },
        "json": {
            "account": params["account"],
            "password": params["password"],
        },
    }
```

### 5.4 Runner 必须支持的执行能力

Runner 至少需要支持：

1. 从命令行接收单参数
2. 从命令行接收 key=value 参数
3. 根据 `DEFAULT_SINGLE_PARAM_NAME` 解析单参数
4. 构造完整 HTTP 请求
5. 保存完整请求到 `request.json`
6. 请求前记录日志文件 offset
7. 执行 HTTP 请求
8. 请求后读取新增日志
9. 保存 response 和 log 到指定 run 目录

### 5.5 Runner 推荐命令行形式

Runner 可以被 `$bfk-fix` 自动调用，也可以被用户手工调用。

示例：

```text
python .bfk/runner/login.py --single 13900000000 --out .bfk/runs/20260625_143012_login --phase before
```

或者：

```text
python .bfk/runner/login.py --account 13900000000 --password 123456 --out .bfk/runs/20260625_143012_login --phase before
```

### 5.6 Runner phase 设计

Runner 支持两个 phase：

```text
before
after
```

#### before

修复前执行，生成：

```text
request.json
before_response.json
before.log
```

#### after

修复后验证，复用已有 `request.json`，生成：

```text
after_response.json
after.log
```

---

## 6. Run 目录产物设计

每次 `$bfk-fix` 生成一个独立 run 目录。

示例：

```text
.bfk/runs/20260625_143012_login/
```

### 6.1 `request.json`

保存本次真实发出的完整请求。

示例：

```json
{
  "method": "POST",
  "url": "http://localhost:8000/api/login",
  "headers": {
    "Content-Type": "application/json",
    "X-BugFix-Run-Id": "bfk-20260625-143012-login"
  },
  "json": {
    "account": "13900000000",
    "password": "123456"
  }
}
```

说明：

1. `request.json` 是本次执行的事实来源。
2. 修复后验证必须复用该文件。
3. 不允许验证阶段重新根据参数拼接请求。

---

### 6.2 `before_response.json`

保存修复前 HTTP 响应。

建议结构：

```json
{
  "status_code": 500,
  "headers": {},
  "body": {
    "error": "Internal Server Error"
  },
  "elapsed_ms": 238
}
```

如果响应 body 不是 JSON，则保存为：

```json
{
  "status_code": 500,
  "headers": {},
  "body_text": "Internal Server Error",
  "elapsed_ms": 238
}
```

---

### 6.3 `before.log`

保存修复前本次请求新增日志。

内容来自：

```text
请求前 log file offset
请求后 log file offset
```

只保存 offset 之后新增的日志内容。

---

### 6.4 `after_response.json`

保存修复后 HTTP 响应。

结构同 `before_response.json`。

---

### 6.5 `after.log`

保存修复后本次请求新增日志。

结构同 `before.log`。

---

### 6.6 `result.json`

保存本次异常定位、修复和验证结果。

示例结构：

```json
{
  "request_name": "login",
  "run_id": "20260625_143012_login",
  "input": "13900000000",
  "status": "pass",
  "issue": {
    "symptom": "登录接口返回 500",
    "type": "code_bug",
    "root_cause": "账号不存在时 login_service 未处理 None 分支，后续访问 user.status 导致异常",
    "evidence": [
      "before_response.json status_code=500",
      "before.log 中出现 AttributeError: 'NoneType' object has no attribute 'status'"
    ],
    "related_files": [
      "app/services/login_service.py"
    ]
  },
  "fix": {
    "summary": "增加账号不存在时的显式处理，返回业务错误",
    "changed_files": [
      "app/services/login_service.py"
    ],
    "risk": "影响范围较小，仅影响账号不存在分支"
  },
  "verification": {
    "status": "pass",
    "before_status_code": 500,
    "after_status_code": 200,
    "error_log_after_fix": false
  }
}
```

说明：

1. `result.json` 是本次异常定位问题的独立记录。
2. 它不保存完整日志和完整响应，只保存结论和引用。
3. 完整响应与日志分别保存在对应文件中。

---

## 7. 核心执行流程

### 7.1 初始化流程

```text
$bfk-init login
  ↓
用户提供示例请求
  ↓
AI 分析请求结构
  ↓
AI 提取可变参数
  ↓
AI 生成 .bfk/runner/login.py
  ↓
用户确认顶部 PARAMS 是否合理
  ↓
初始化完成
```

初始化完成后，用户应该能直接执行：

```text
python .bfk/runner/login.py --single 13900000000 --out .bfk/runs/manual_login --phase before
```

---

### 7.2 修复流程

```text
$bfk-fix login 13900000000
  ↓
创建 .bfk/runs/<timestamp>_login/
  ↓
调用 .bfk/runner/login.py --phase before
  ↓
生成 request.json
  ↓
生成 before_response.json
  ↓
生成 before.log
  ↓
AI 读取 request.json、before_response.json、before.log 和本地代码
  ↓
定位异常根因
  ↓
执行最小代码修复
  ↓
调用 .bfk/runner/login.py --phase after
  ↓
复用 request.json 重新请求
  ↓
生成 after_response.json
  ↓
生成 after.log
  ↓
生成 result.json
```

---

## 8. 日志采集方案

MVP 默认使用：

```text
External HTTP + file offset
```

### 8.1 采集逻辑

1. 请求前读取每个日志文件的当前 size
2. 执行 HTTP 请求
3. 等待 `AFTER_REQUEST_WAIT_SECONDS`
4. 从请求前 size 开始读取新增内容
5. 写入 `before.log` 或 `after.log`

### 8.2 默认不做的事情

MVP 不做：

1. 清空日志文件
2. 强依赖 run_id 过滤
3. 自动修改服务端 logging
4. OpenTelemetry trace
5. 远程日志拉取

### 8.3 预留增强能力

后续可以增加：

1. `X-BugFix-Run-Id` + 服务端 logging middleware
2. run_id 日志过滤
3. in-process FastAPI / Flask test client
4. OpenTelemetry trace id 关联

---

## 9. 异常定位与修复原则

`$bfk-fix` 在定位和修复时遵循以下原则：

1. 优先基于 `before_response.json` 和 `before.log` 判断问题。
2. 必须结合本地代码定位根因，不只依赖日志文本。
3. 修复前应形成明确根因判断。
4. 采用最小代码修改。
5. 不做顺手重构。
6. 不随意修改接口协议。
7. 修复后必须执行回归验证。
8. 如果验证失败，应在 `result.json` 中记录失败原因。

---

## 10. MVP 不包含的能力

MVP 暂不包含：

1. `$bfk-status`
2. `$bfk-verify`
3. `$bfk-run`
4. `$bfk-diagnose`
5. YAML 配置
6. `.bfk/config.py`
7. `.bfk/context.md`
8. `.bfk/runtime/`
9. Markdown 格式的响应与日志保存
10. 单独的 `patch.diff`
11. 单独的 `code_review.md`
12. 远程日志
13. 分布式链路追踪
14. 多服务编排
15. 自动 Mock 外部依赖
16. 数据库快照
17. Web UI

这些能力如果后续需求明确，再逐步补充。

---

## 11. MVP 验收标准

### 11.1 初始化验收

执行：

```text
$bfk-init login
```

应生成：

```text
.bfk/runner/login.py
```

并满足：

1. 文件顶部包含 `PARAMS`
2. 文件顶部包含 `DEFAULT_SINGLE_PARAM_NAME`
3. 文件顶部包含 `BASE_URL`
4. 文件顶部包含 `LOG_FILES`
5. 文件中包含 `build_request(params)`
6. 文件可以通过 Python 命令独立执行

---

### 11.2 修复前回放验收

执行：

```text
$bfk-fix login 13900000000
```

在修复前阶段应生成：

```text
request.json
before_response.json
before.log
```

并满足：

1. `request.json` 是完整本地请求
2. `before_response.json` 包含 status_code、headers、body/body_text、elapsed_ms
3. `before.log` 包含本次请求期间新增日志

---

### 11.3 修复后验证验收

修复后应生成：

```text
after_response.json
after.log
result.json
```

并满足：

1. 验证阶段复用同一个 `request.json`
2. `after_response.json` 记录修复后的响应
3. `after.log` 记录修复后的新增日志
4. `result.json` 记录根因、修复内容、影响范围和验证结果

---

## 12. MVP 最终形态

MVP 最终只保留：

```text
命令：
$bfk-init <request_name>
$bfk-fix <request_name> <params>

目录：
.bfk/
├── runner/
│   └── <request_name>.py
└── runs/
    └── <timestamp>_<request_name>/
        ├── request.json
        ├── before_response.json
        ├── before.log
        ├── after_response.json
        ├── after.log
        └── result.json
```

这就是 Bug Fix Kit 第一版的完整闭环。
