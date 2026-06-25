# Bug Fix Kit MVP 产品需求文档

## 1. 产品定位

**Bug Fix Kit**，简称 **bfk**，是一个面向 AI Coding Agent 的本地异常复现、日志诊断与代码修复插件。

MVP 阶段优先支持本地 Python HTTP 服务场景。用户先通过 `$bfk-init` 初始化项目调试知识，再通过 `$bfk-new` 创建一个具体异常问题。之后通过 `$bfk-run` 执行当前问题的请求脚本并采集日志，通过 `$bfk-diagnose` 定位异常原因，通过 `$bfk-fix` 执行代码修复，再继续 `$bfk-run` 进入下一轮验证。

核心目标是：

> 将一次线上反馈问题沉淀为一个可持续迭代的本地异常处理会话。

---

## 2. 核心设计原则

### 2.1 项目知识与具体问题分离

`$bfk-init` 只初始化项目级知识，例如服务地址、日志路径、请求基础信息和修复原则。

`$bfk-new` 才创建具体异常问题，并生成该问题专属的 Python 请求脚本。

---

### 2.2 Issue 级 Runner

MVP 不维护项目级通用 runner 库。

每个异常问题都有自己的：

```text
.bfk/issues/<issue_id>/runner.py
```

原因：

1. 每个异常问题的参数在创建时已经确定。
2. 后续迭代不应重复传参。
3. 每个 issue 需要稳定复现同一个问题。
4. 如果参数变化，应该创建新的 issue。
5. issue 级 runner 更方便用户手工调整。
6. `$bfk-run` 永远无需请求参数，语义稳定。

---

### 2.3 run 只执行，不诊断

`$bfk-run` 只负责执行请求和采集日志，不做问题分析，不修改代码。

---

### 2.4 diagnose 只分析，不修复

`$bfk-diagnose` 基于当前 iteration 的响应、日志和本地代码定位问题，输出 Markdown 格式诊断报告，不修改代码。

---

### 2.5 fix 只修复，不执行

`$bfk-fix` 基于最新诊断报告进行代码修复，并输出修复报告。修复后用户继续执行 `$bfk-run` 验证。

---

### 2.6 Iteration 表达持续迭代

MVP 不使用 before / after，也不使用 baseline / attempt。

每一轮都是一个 iteration：

```text
执行请求 → 采集日志 → 诊断问题 → 必要时修复 → 下一轮执行验证
```

---

## 3. MVP 命令设计

MVP 保留 5 个命令：

```text
$bfk-init
$bfk-new
$bfk-run
$bfk-diagnose
$bfk-fix
```

| 命令              | 是否需要请求参数 | 是否执行请求 | 是否诊断 | 是否修复 | 核心产物                                        |
| --------------- | -------: | -----: | ---: | ---: | ------------------------------------------- |
| `$bfk-init`     |        否 |      否 |    否 |    否 | `.bfk/PROJECT.md`                           |
| `$bfk-new`      |        是 |      否 |    否 |    否 | `issue.md`、`runner.py`                      |
| `$bfk-run`      |        否 |      是 |    否 |    否 | `request.json`、`response.json`、`output.log` |
| `$bfk-diagnose` |        否 |      否 |    是 |    否 | `diagnosis.md`                              |
| `$bfk-fix`      |        否 |      否 |    否 |    是 | `fix.md`                                    |

---

## 4. 目录结构

最终 MVP 目录结构如下：

```text
.bfk/
├── PROJECT.md
└── issues/
    └── <issue_id>/
        ├── issue.md
        ├── runner.py
        └── iterations/
            └── <iteration_no>/
                ├── request.json
                ├── response.json
                ├── output.log
                ├── diagnosis.md
                └── fix.md
```

说明：

1. `.bfk/PROJECT.md` 保存项目级调试知识。
2. `.bfk/issues/<issue_id>/` 表示一次具体异常问题处理会话。
3. `runner.py` 是当前 issue 专属的请求脚本。
4. `iterations/<iteration_no>/` 表示第 N 轮执行、诊断、修复过程。
5. `fix.md` 是可选文件，只有该轮执行了修复才会生成。
6. 如果某一轮诊断已经通过，则该轮不需要 `fix.md`。

---

## 5. 命令一：$bfk-init

### 5.1 命令作用

初始化当前项目的 bfk 调试知识。

### 5.2 使用方式

```text
$bfk-init
```

### 5.3 用户输入

用户需要提供项目级信息，例如：

```text
本地服务地址：http://localhost:8000
日志文件路径：logs/app.log
日志采集方式：file offset
默认请求头：Content-Type: application/json
鉴权方式：从环境变量 LOCAL_AUTH_TOKEN 读取
```

### 5.4 输出产物

```text
.bfk/PROJECT.md
```

### 5.5 PROJECT.md 示例

```markdown
# Bug Fix Kit Project Knowledge

## Local Service

- Base URL: http://localhost:8000
- Service should be started manually before running bfk.

## Logs

- Log files:
  - logs/app.log

## Log Capture

Default strategy:

1. Record file offset before request.
2. Execute HTTP request.
3. Wait 2 seconds.
4. Read new logs from previous offset.

## Request Defaults

Default headers:

- Content-Type: application/json

Auth:

- Authorization token is read from LOCAL_AUTH_TOKEN.

## Fix Principles

- Diagnose before fixing.
- Prefer minimal code changes.
- Do not refactor unrelated code.
- Do not change public API contract unless necessary.
- After fixing, run `$bfk-run` again to verify.
```

### 5.6 职责边界

`$bfk-init` 只创建或更新项目级知识，不创建具体异常问题，不执行请求，不诊断，不修复。

---

## 6. 命令二：$bfk-new

### 6.1 命令作用

创建一个新的异常问题，并生成该问题专属的 Python 请求脚本。

### 6.2 使用方式

```text
$bfk-new <issue_name> <params>
```

示例：

```text
$bfk-new login_failed 13900000000
```

或者：

```text
$bfk-new create_order_failed user_id=10086 sku_id=sku_abc coupon=SUMMER2026
```

参数解析规则：

1. `key=value` 形式直接按键名写入 `runner.py` 的 `PARAMS`。
2. 位置参数结合 `.bfk/PROJECT.md` 与目标接口语义推断字段名（如登录场景将手机号推断为 `account`）。
3. 接口必需但无法从输入推断的参数（如 `password`），在 `runner.py` 中以空占位值生成，由用户在首次 `$bfk-run` 前手工补全。

### 6.3 命令职责

`$bfk-new` 负责：

1. 读取 `.bfk/PROJECT.md`
2. 理解用户输入的异常参数
3. 创建新的 issue 目录
4. 生成该 issue 专属的 `runner.py`
5. 生成 `issue.md`
6. 初始化空的 `iterations/` 目录

### 6.4 输出目录

```text
.bfk/issues/<issue_id>/
```

目录命名建议：

```text
<YYYYMMDD_HHMMSS>_<issue_name>
```

示例：

```text
.bfk/issues/20260625_143012_login_failed/
```

### 6.5 输出产物

```text
.bfk/issues/20260625_143012_login_failed/
├── issue.md
├── runner.py
└── iterations/
```

### 6.6 issue.md

`issue.md` 保存该异常问题的自然语言描述、原始输入和解析后的参数。

示例：

````markdown
# Issue: login_failed

## User Input

账号 13900000000 登录失败。

## Parsed Parameters

- account: 13900000000
- password: (required, 无法从输入推断，请在 runner.py 中手工补全)

## Expected Goal

复现登录异常，基于日志定位原因，并修复本地代码。

## Runner

Runner script: `.bfk/issues/20260625_143012_login_failed/runner.py`
````

### 6.7 runner.py

`runner.py` 是当前异常问题专属的请求脚本。

它保存当前问题的固定参数，并负责构造请求；请求的执行与日志采集由 `$bfk-run` 完成。

示例结构：

```python
# ============================================================
# Bug Fix Kit Issue Runner
# This runner belongs to one specific issue.
# ============================================================

import os

ISSUE_NAME = "login_failed"

PARAMS = {
    # account 解析自 $bfk-new 的输入
    "account": "13900000000",
    # password 无法从输入推断，请在首次执行前手工补全
    "password": "",
}

BASE_URL = "http://localhost:8000"

LOG_FILES = [
    "logs/app.log"
]

AFTER_REQUEST_WAIT_SECONDS = 2


def build_request(params: dict) -> dict:
    return {
        "method": "POST",
        "url": f"{BASE_URL}/api/login",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('LOCAL_AUTH_TOKEN', '')}",
            "X-BugFix-Issue": ISSUE_NAME,
        },
        "json": {
            "account": params["account"],
            "password": params["password"],
        },
    }


if __name__ == "__main__":
    # 手工执行只打印构造的请求 JSON，便于本地快速核对，不发送 HTTP 请求。
    import json

    print(json.dumps(build_request(PARAMS), ensure_ascii=False, indent=2))
```

### 6.8 runner.py 设计要求

`runner.py` 必须满足：

1. 顶部包含当前 issue 的固定参数。
2. 参数后续默认不再通过命令行重复传入。
3. 包含 `build_request(params)` 函数，返回本轮请求的完整描述。
4. 可被 `$bfk-run` 加载和调用。
5. 支持用户手工执行：直接运行 `runner.py` 只打印 `build_request(PARAMS)` 构造的请求 JSON，用于本地快速核对，不发送 HTTP 请求。
6. `runner.py` 自身只声明参数和构造请求，不负责创建 iteration 目录、执行请求、采集日志或保存产物。
7. 请求执行、日志采集（默认 `External HTTP + file offset`）和产物落盘统一由 `$bfk-run` 完成。

---

## 7. 命令三：$bfk-run

### 7.1 命令作用

执行当前异常问题的请求脚本，并采集本轮响应和日志。

### 7.2 使用方式

```text
$bfk-run [issue_id]
```

默认（省略 `issue_id`，操作最新 issue）：

```text
$bfk-run
```

或指定 issue：

```text
$bfk-run 20260625_143012_login_failed
```

### 7.3 命令职责

`$bfk-run` 负责：

1. 找到目标 issue 目录。
2. 读取 issue 的 `runner.py`。
3. 创建下一轮 iteration 目录。
4. 执行 runner。
5. 请求前记录日志文件 offset。
6. 请求后采集新增日志。
7. 保存当前 iteration 的真实请求。
8. 保存当前 iteration 的响应。
9. 保存当前 iteration 的日志。

### 7.4 输出产物

第一次执行：

```text
.bfk/issues/20260625_143012_login_failed/
└── iterations/
    └── 001/
        ├── request.json
        ├── response.json
        └── output.log
```

第二次执行：

```text
.bfk/issues/20260625_143012_login_failed/
└── iterations/
    └── 002/
        ├── request.json
        ├── response.json
        └── output.log
```

### 7.5 为什么每轮保存 request.json

每轮都保存 `request.json`，原因是：

1. 明确记录该轮真实执行的请求。
2. 如果 runner 被手工调整，可以追踪请求差异。
3. 某些字段如 timestamp、requestId 可能每轮变化。
4. 诊断时可以引用当前 iteration 的真实请求。
5. 不依赖隐含上下文。

### 7.6 response.json 格式

```json
{
  "status_code": 500,
  "headers": {},
  "body": {
    "error": "Internal Server Error"
  },
  "body_text": null,
  "elapsed_ms": 238,
  "transport_error": null
}
```

说明：

1. 如果响应体是 JSON，写入 `body`。
2. 如果响应体不是 JSON，写入 `body_text`。
3. `body` 和 `body_text` 至少一个有值。
4. 如果响应体为空，允许二者为空，但需要记录 `empty_body: true`。
5. 区分“传输失败”与“业务失败”：
   - 业务失败：请求已收到 HTTP 响应（如 4xx/5xx），按上面格式记录，`transport_error` 为 `null`。
   - 传输失败：请求未拿到 HTTP 响应，例如连接被拒、超时、服务未启动、DNS/端口错误、runner 抛出异常。
6. 发生传输失败时仍然写入 `response.json`，但 `status_code`、`body`、`body_text` 均为 `null`，并在 `transport_error` 中记录错误类型与原始信息。

传输失败示例：

```json
{
  "status_code": null,
  "headers": {},
  "body": null,
  "body_text": null,
  "elapsed_ms": 12,
  "transport_error": {
    "type": "connection_refused",
    "message": "Connection refused: localhost:8000"
  }
}
```

### 7.7 output.log

`output.log` 保存当前 iteration 请求期间新增日志。

日志采集方式来自 `.bfk/PROJECT.md` 和 `runner.py` 中的配置。

MVP 默认：

```text
External HTTP + file offset
```

---

## 8. 命令四：$bfk-diagnose

### 8.1 命令作用

基于当前 iteration 的执行结果和本地代码定位异常原因。

### 8.2 使用方式

```text
$bfk-diagnose [issue_id]
```

示例（默认最新 issue）：

```text
$bfk-diagnose
```

### 8.3 命令职责

`$bfk-diagnose` 负责：

1. 读取 `.bfk/PROJECT.md`
2. 读取 issue 的 `issue.md`
3. 读取最新 iteration 的 `request.json`
4. 读取最新 iteration 的 `response.json`
5. 读取最新 iteration 的 `output.log`
6. 如果不是第一轮，读取上一轮 `diagnosis.md`
7. 如果不是第一轮，读取上一轮 `fix.md`
8. 结合本地代码定位异常
9. 判断问题是否已经解决
10. 输出 Markdown 格式诊断报告

### 8.4 输出产物

```text
.bfk/issues/<issue_id>/iterations/<n>/diagnosis.md
```

### 8.5 第一轮诊断报告结构

```markdown
# Diagnosis Report

## Iteration

001

## Execution Summary

- Request: POST /api/login
- Status Code: 500
- Key Logs:
  - AttributeError: 'NoneType' object has no attribute 'status'

## Problem Status

failed

## Root Cause

账号不存在时，login_service 未处理 user 为空的情况，后续访问 user.status 导致异常。

## Evidence

- `iterations/001/response.json` 返回 500
- `iterations/001/output.log` 出现 NoneType 异常
- `app/services/login_service.py` 中缺少 user 为空分支处理

## Related Files

- `app/services/login_service.py`

## Suggested Fix

增加账号不存在时的显式处理，返回业务错误。

## Next Action

Run `$bfk-fix`.
```

### 8.6 后续轮次诊断报告结构

后续轮次需要额外回答：

1. 上一轮问题是否已修复？
2. 如果没有修复，现象是否变化？
3. 新问题和上一轮问题是什么关系？
4. 是否继续修复？

示例：

```markdown
# Diagnosis Report

## Iteration

002

## Previous Diagnosis

上一轮判断 login_service 未处理 user 为空。

## Previous Fix

上一轮增加了 user 为空判断。

## Current Execution Summary

- Status Code: 500
- Key Logs:
  - AttributeError: 'NoneType' object has no attribute 'status'

## Problem Status

failed

## Change Compared With Previous Iteration

接口仍然返回 500，但错误点从 user 为空变为 user.status 为空。

## Root Cause

上一轮修复只处理了 user 对象为空，没有处理 user.status 为空的异常分支。

## Evidence

- `iterations/002/output.log`
- `app/services/login_service.py`

## Suggested Fix

继续增加 user.status 为空时的兜底处理。

## Next Action

Run `$bfk-fix`.
```

### 8.7 诊断结果状态

`diagnosis.md` 中的 `Problem Status` 建议使用以下值：

```text
failed
passed
blocked
unknown
```

含义：

| 状态        | 含义                               |
| --------- | -------------------------------- |
| `failed`  | 请求执行成功，但问题仍存在，需要继续处理             |
| `passed`  | 当前问题已验证通过                        |
| `blocked` | 当前问题无法继续自动处理，例如缺少本地数据、服务未启动、日志缺失 |
| `unknown` | 证据不足，无法可靠判断                      |

补充：当本轮 `response.json` 中 `transport_error` 不为空（连接失败、超时、服务未启动等传输层问题）时，`Problem Status` 应判为 `blocked`。这类问题不是代码缺陷，`$bfk-fix` 不应修改代码，用户需先恢复本地服务或网络环境再重新 `$bfk-run`。

---

## 9. 命令五：$bfk-fix

### 9.1 命令作用

基于当前 iteration 的诊断报告（`diagnosis.md`）修复代码。

### 9.2 使用方式

```text
$bfk-fix [issue_id]
```

示例（默认最新 issue）：

```text
$bfk-fix
```

### 9.3 命令职责

`$bfk-fix` 负责：

1. 读取当前 iteration 的 `diagnosis.md`
2. 判断是否适合自动修复
3. 按诊断报告执行最小代码修改
4. 生成本轮修复记录

它不自动执行下一轮请求。

修复后用户需要继续执行：

```text
$bfk-run
```

说明：`fix.md` 写入与诊断相同的 iteration（即本轮）；修复效果的验证发生在下一次 `$bfk-run` 创建的新 iteration 中。

### 9.4 适合自动修复的条件

当最新 `diagnosis.md` 满足以下条件时，才建议执行自动修复：

1. `Problem Status` 为 `failed`
2. 根因明确
3. 相关文件明确
4. 问题类型属于代码缺陷
5. 不是本地数据缺失、服务未启动、权限缺失、依赖未 Mock 等环境问题

如果 `Problem Status` 为 `passed`，说明本轮问题已验证通过，`$bfk-fix` 不修改代码，直接提示无需修复。

如果根因不明确，或属于本地数据缺失、服务未启动、权限缺失、依赖未 Mock 等环境问题，`$bfk-fix` 应拒绝修改代码，并在当前 iteration 下生成 `fix.md` 说明原因。

### 9.5 输出产物

```text
.bfk/issues/<issue_id>/iterations/<n>/fix.md
```

### 9.6 fix.md 示例

```markdown
# Fix Report

## Iteration

001

## Diagnosis Used

`iterations/001/diagnosis.md`

## Fix Summary

增加账号不存在时的显式处理，避免 user 为空时继续访问 user.status。

## Changed Files

- `app/services/login_service.py`

## Change Details

- 在查询用户后增加 None 判断
- 用户不存在时返回明确业务错误

## Risk

影响范围集中在登录异常分支，不改变正常登录流程。

## Next Action

Run `$bfk-run` to verify.
```

### 9.7 修复原则

`$bfk-fix` 必须遵守：

1. 优先采用最小修改。
2. 不做顺手重构。
3. 不随意修改接口协议。
4. 不吞掉真实异常。
5. 不绕过业务校验。
6. 不修改无关文件。
7. 修复报告必须说明修改文件和风险。
8. 修复后不自动执行请求，由 `$bfk-run` 显式进入下一轮。

---

## 10. 完整使用链路

### 10.1 初始化项目

```text
$bfk-init
```

生成：

```text
.bfk/PROJECT.md
```

---

### 10.2 创建异常问题

```text
$bfk-new login_failed 13900000000
```

生成：

```text
.bfk/issues/20260625_143012_login_failed/
├── issue.md
├── runner.py
└── iterations/
```

---

### 10.3 第一轮执行

```text
$bfk-run
```

生成：

```text
iterations/001/
├── request.json
├── response.json
└── output.log
```

---

### 10.4 第一轮诊断

```text
$bfk-diagnose
```

生成：

```text
iterations/001/
└── diagnosis.md
```

---

### 10.5 第一轮修复

```text
$bfk-fix
```

生成：

```text
iterations/001/
└── fix.md
```

---

### 10.6 第二轮执行验证

```text
$bfk-run
```

生成：

```text
iterations/002/
├── request.json
├── response.json
└── output.log
```

---

### 10.7 第二轮诊断

```text
$bfk-diagnose
```

如果问题已解决，`diagnosis.md` 中标记：

```text
Problem Status: passed
```

如果问题未解决，继续：

```text
$bfk-fix
$bfk-run
$bfk-diagnose
```

---

## 11. issue 与 iteration 解析规则

`$bfk-run`、`$bfk-diagnose`、`$bfk-fix` 的 `issue_id` 参数可选：

1. 省略 `issue_id` 时，默认选择 `.bfk/issues/` 下创建时间最新的 issue 目录。
2. 显式传入 `issue_id` 时，操作该指定 issue（用于回到较早的 issue 继续处理）。
3. 如果存在多个同时间目录，按目录名排序后取最后一个。
4. 选定 issue 后，最新 iteration 为其 `iterations/` 下编号最大的目录。
5. 如果 issue 下还没有 iteration，`$bfk-diagnose` 和 `$bfk-fix` 应提示先执行 `$bfk-run`。

---

## 12. MVP 不包含的能力

MVP 暂不包含：

1. 项目级 `.bfk/runner/` 通用请求库
2. `$bfk-status`
3. `$bfk-verify`
4. `$bfk-auto`
5. 远程日志
6. OpenTelemetry
7. 多服务链路追踪
8. 自动 Mock 外部依赖
9. 数据库快照
10. Web UI
11. 自动提交 commit
12. YAML 配置
13. 自动判断所有请求类型
14. 多 issue 并发执行管理
15. 自动压缩历史日志
16. 自动生成测试用例

---

## 13. 验收标准

### 13.1 init 验收

执行：

```text
$bfk-init
```

应生成：

```text
.bfk/PROJECT.md
```

并包含：

* 本地服务地址
* 日志路径
* 日志采集方式
* 网络请求基础信息
* 修复原则

---

### 13.2 new 验收

执行：

```text
$bfk-new login_failed 13900000000
```

应生成：

```text
.bfk/issues/<issue_id>/
├── issue.md
├── runner.py
└── iterations/
```

其中：

1. `issue.md` 记录原始输入和解析后的参数。
2. `runner.py` 包含固定参数和请求构造逻辑。
3. `runner.py` 可以独立执行，直接运行时打印构造的请求 JSON（不发送 HTTP 请求）。

---

### 13.3 run 验收

执行：

```text
$bfk-run
```

应生成：

```text
iterations/001/
├── request.json
├── response.json
└── output.log
```

再次执行：

```text
$bfk-run
```

应生成：

```text
iterations/002/
├── request.json
├── response.json
└── output.log
```

要求：

1. 不覆盖上一轮 iteration。
2. 每轮都保存真实请求、响应和日志。
3. 日志来自本轮请求期间的新增日志。

---

### 13.4 diagnose 验收

执行：

```text
$bfk-diagnose
```

应在当前 iteration 下生成：

```text
diagnosis.md
```

诊断报告必须包含：

* 当前执行摘要
* 当前问题状态
* 关键日志
* 相关代码文件
* 根因判断
* 下一步建议

如果是后续轮次，还需要包含：

* 上一轮诊断摘要
* 上一轮修复摘要
* 本轮是否验证通过
* 问题是否发生变化

---

### 13.5 fix 验收

执行：

```text
$bfk-fix
```

应基于最新 `diagnosis.md` 修改代码，并在当前 iteration 下生成：

```text
fix.md
```

`fix.md` 必须包含：

* 使用的诊断报告
* 修复摘要
* 修改文件
* 修改细节
* 风险说明
* 下一步建议

如果诊断不适合自动修复，`fix.md` 应说明拒绝修复原因，且不得修改代码。

---

## 14. 最终 MVP 形态

Bug Fix Kit MVP 的最终命令为：

```text
$bfk-init
$bfk-new <issue_name> <params>
$bfk-run [issue_id]
$bfk-diagnose [issue_id]
$bfk-fix [issue_id]
```

最终目录结构为：

```text
.bfk/
├── PROJECT.md
└── issues/
    └── <issue_id>/
        ├── issue.md
        ├── runner.py
        └── iterations/
            └── <iteration_no>/
                ├── request.json
                ├── response.json
                ├── output.log
                ├── diagnosis.md
                └── fix.md
```

核心闭环为：

```text
初始化项目知识
  ↓
创建异常问题和请求脚本
  ↓
执行请求并收集日志
  ↓
诊断异常原因
  ↓
修复代码
  ↓
再次执行请求
  ↓
继续诊断和修复，直到问题解决
```
