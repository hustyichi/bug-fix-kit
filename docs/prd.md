# Bug Fix Kit MVP 产品文档（当前实现）

## 1. 产品定位

Bug Fix Kit（`bfk`）是一个本地 Codex 插件包，用于把一次 bug 反馈沉淀为可重复执行的本地问题处理会话。

当前实现采用 **hybrid-minimal** 形态：

- Python stdlib helper CLI 只负责确定性机械动作：安装插件、初始化 `.bfk`、创建 issue、执行 runner、采集响应和日志、写 artifact。
- Codex skills 负责需要判断力的动作：诊断根因和执行最小修复。

MVP 现在包含 PyPI 发布准备与最小发布脚本；仍不内置 demo HTTP app、不提供 Web UI、不自动 mock 外部依赖。

---

## 2. 分发与安装

本项目是可发布到 PyPI 的本地 Codex plugin package：

```text
.codex-plugin/plugin.json
skills/bfk-*/SKILL.md
bug_fix_kit/*.py
pyproject.toml
```

发布版安装：

```bash
python3 -m pip install bug-fix-kit
bfk --help
bfk doctor
bfk install --yes
```

`pip install bug-fix-kit` 只安装 `bfk` CLI；插件启用仍由 `bfk install --yes` 打印的 Codex 指令完成。

本地开发安装：

```bash
python3 -m pip install -e .
bfk install --yes
```

高级安装路径：

```bash
bfk install --marketplace ~/.agents/plugins/marketplace.json --yes
```

实际行为：

1. 校验 `.codex-plugin/plugin.json` 和五个 skills。
2. 复制插件到 `<home>/plugins/bug-fix-kit`。
3. 排除 `.git`、`.omx`、`.bfk`、`.venv`、缓存、build/dist、`*.egg-info`。
4. 创建或更新 `<home>/.agents/plugins/marketplace.json`。
5. 目标目录已存在时必须显式传 `--yes` 才覆盖。

---

## 3. 用户可见能力

### 3.1 Codex skills

用户工作流：

```text
$bfk-init
$bfk-new <issue_name> <key=value ...>
$bfk-run [issue_id]
$bfk-diagnose [issue_id]
$bfk-fix [issue_id]
```

### 3.2 Helper CLI

实际 CLI 命令只有：

```text
bfk install
bfk doctor
```

CLI 只负责插件安装和外壳检查。项目初始化、issue 创建、请求执行、诊断和修复都由 Codex skill 执行；CLI 不提供 `init-project`、`new`、`run`、`diagnose`、`fix`、`status`、`verify`、`auto`。

---

## 4. `.bfk` artifact contract

```text
.bfk/
├── PROJECT.md
└── issues/
    └── <YYYYMMDD_HHMMSS>_<issue_name>/
        ├── issue.md
        ├── runner.py
        └── iterations/
            └── <nnn>/
                ├── request.json
                ├── response.json
                ├── output.log
                ├── diagnosis.md   # $bfk-diagnose 写入，按需出现
                └── fix.md         # $bfk-fix 写入，按需出现
```

规则：

- `.bfk/PROJECT.md` 是项目级调试知识。
- 每个 issue 有自己的 `runner.py`，不维护项目级通用 runner 库。
- 每次 `$bfk-run` 创建新的递增 iteration，例如 `001`、`002`。
- `request.json`、`response.json`、`output.log` 由 Codex skill 写入。
- `diagnosis.md`、`fix.md` 由 Codex skills 写入。

---

## 5. `$bfk-init`

作用：创建或更新 `.bfk/PROJECT.md`。

当前 `PROJECT.md` 格式由 Codex skill 生成，包含：

- Local Service / Base URL
- Logs
- Log Capture
- Request Defaults
- Auth（可选说明文本）
- Request Sample（可选，原始 curl）
- Request Contract（可选，请求 method/path、外层模型、内层 payload 位置）
- Parameter Contract（可选，`$bfk-new` 参数到请求字段的映射）
- Repository Evidence（可选，仓库交叉验证锚点）
- Fix Principles

请求 headers 会写入 `PROJECT.md` 并传递到后续 `runner.py` 的 `DEFAULT_HEADERS`。

当用户提供真实请求样例时，skill 会保存原始样例，并尽力从 curl/request 中沉淀 method、URL/path、headers、JSON body，以及 `input[0].content[0].text` 这类 JSON 字符串内层 payload。默认保留认证 header 等复现请求所需信息；安全边界是 `.bfk/` 作为本地 gitignored 工作区。只有用户在样例中显式写入 `${ENV_NAME}` 占位符时，后续 runner 才会按环境变量展开。

边界：不创建 issue、不执行请求、不诊断、不修复。

---

## 6. `$bfk-new`

作用：创建一个 issue session 和 issue 级 runner。

示例：

```text
$bfk-new login_failed account=13900000000 mode=e2e
```

实际参数规则：

1. 必须先存在 `.bfk/PROJECT.md`；缺失时提示先运行 `$bfk-init`。
2. `key=value` 会原样写入 `PARAMS`。
3. 非 `key=value` 的位置参数会合并为 `value`，前提是没有显式 `value=`。
4. 如果 `PROJECT.md` 中存在 Request Sample + Parameter Contract，生成的 `runner.py` 会复制样例请求并按映射替换参数；未传入的映射字段保留样例值。
5. skill 不做契约外业务字段推断，不自动生成 password/user_id 等字段；需要复杂请求时手工编辑 `PROJECT.md` 或 `runner.py`。

无请求契约时，生成的 `runner.py` 默认：

- `POST {BASE_URL}/`
- JSON body 为 `PARAMS`
- headers 为 `DEFAULT_HEADERS + X-BugFix-Issue`
- `LOG_FILES` 来自 `PROJECT.md`
- `AFTER_REQUEST_WAIT_SECONDS = 2`

有请求契约时，生成的 `runner.py` 默认：

- method/path 来自样例请求或 `Endpoint`
- JSON body 来自样例请求
- 参数按 `Parameter Contract` 写入 `body.*` 或内层 `text.*`
- 内层 payload 重新 JSON encode 回用户文本字段
- 样例中显式写入的 `${ENV_NAME}` header 占位符在运行时从环境变量展开

直接执行 `python runner.py` 只打印请求 JSON，不发送 HTTP。

边界：不执行请求、不诊断、不修复。

---

## 7. `$bfk-run`

作用：执行 issue runner，采集本轮请求、响应和日志。

实际流程：

1. 省略 `issue_id` 时选择 `.bfk/issues/` 下目录名排序最后的 issue。
2. 显式 `issue_id` 不存在时，返回简洁错误且无 traceback。
3. 加载 `runner.py` 的 `LOG_FILES` 和 `AFTER_REQUEST_WAIT_SECONDS`。
4. 调用 `build_request(PARAMS)` 得到请求描述。
5. 请求前记录日志文件 offset。
6. 用 stdlib `urllib` 发送 HTTP 请求。
7. 等待 `AFTER_REQUEST_WAIT_SECONDS`。
8. 读取 offset 后新增日志。
9. 写入下一轮 `iterations/<nnn>/`。

### 7.1 `request.json`

保存本轮真实请求。即使请求 payload 不能 JSON 序列化，artifact 写入也会用 `default=str` 保留可读证据。

### 7.2 `response.json`

成功或 HTTP 业务错误（包括 4xx/5xx）：

```json
{
  "status_code": 200,
  "headers": {},
  "body": {},
  "body_text": null,
  "empty_body": false,
  "elapsed_ms": 12,
  "transport_error": null
}
```

传输/构造错误：

```json
{
  "status_code": null,
  "headers": {},
  "body": null,
  "body_text": null,
  "empty_body": false,
  "elapsed_ms": 0,
  "transport_error": {
    "type": "transport_error",
    "message": "..."
  }
}
```

runner import/config/build 错误：

```json
{
  "status_code": null,
  "headers": {},
  "body": null,
  "body_text": null,
  "empty_body": false,
  "elapsed_ms": 0,
  "transport_error": {
    "type": "runner_error",
    "message": "..."
  }
}
```

### 7.3 `output.log`

保存本轮请求期间新增日志。

- 日志缺失时写入 `[bfk] missing log file: ...`。
- 日志被截断时写入 `[bfk] log file truncated, reading from start: ...`，然后从头读取。

边界：只执行和采集，不诊断、不编辑代码、不写 `diagnosis.md` 或 `fix.md`。

---

## 8. `$bfk-diagnose`

作用：Codex skill 读取最新 iteration evidence 并写 `diagnosis.md`。

输入 evidence：

- `.bfk/PROJECT.md`
- `issue.md`
- 当前 iteration 的 `request.json`
- 当前 iteration 的 `response.json`
- 当前 iteration 的 `output.log`
- 之前的 `diagnosis.md` / `fix.md`（存在时）

建议 `Problem Status`：

```text
failed | passed | blocked | unknown
```

当 `response.json.transport_error` 不为空时，应标记 `blocked`，因为这通常表示服务未启动、网络/端口问题、runner 错误或本地环境问题，不应直接进入代码修复。

边界：写 `diagnosis.md`，不改代码、不执行请求、不写 `fix.md`。

---

## 9. `$bfk-fix`

作用：Codex skill 基于最新 `diagnosis.md` 执行最小修复，并写 `fix.md`。

允许改代码的条件：

1. `Problem Status` 为 `failed`。
2. 根因明确。
3. 相关文件明确。
4. 问题属于代码缺陷。
5. 不是服务未启动、鉴权、本地数据、依赖/mock 环境、传输错误等 blocked case。

边界：不运行 `$bfk-run`，不自动验证；修复后提示用户再次运行 `$bfk-run`。

---

## 10. 已验证 E2E 行为

当前实现已用本地 mock HTTP 服务验证：

1. 启动 `127.0.0.1` mock 服务。
2. 使用 `$bfk-init` 写入 base URL、log file、`Content-Type`、`Authorization`。
3. 使用 `$bfk-new "login failed" account=13900000000 mode=e2e`。
4. 使用 `$bfk-run`。
5. 验证：
   - mock 服务收到 `POST /`；
   - `request.json` 含正确 headers 和 JSON body；
   - `response.json.status_code == 200`；
   - `response.json.transport_error == null`；
   - mock 追加日志被写入 `output.log`。

---

## 11. 验收标准

必过检查：

```bash
python3 -m compileall -q bug_fix_kit tests
pytest -q
python3 -m bug_fix_kit --help
bfk --help
bfk doctor
bfk install --home <tmp> --yes
bfk install --marketplace <tmp>/.agents/plugins/marketplace.json --yes
python3 /Users/bryan/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

核心不变量：

- 无 runtime dependencies。
- 无 demo HTTP app。
- plugin manifest 有 `defaultPrompt` array，且没有 unsupported `hooks` / `apps` / `mcpServers`。
- CLI 命令边界保持 `install/doctor`。
- `.bfk` artifact contract 保持稳定。
