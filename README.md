# Bug Fix Kit

语言：简体中文 | [English](README.en.md)

Bug Fix Kit（`bfk`）是一个本地 Codex 插件，用于可重复的 bug 复现、诊断和修复会话。

它把确定性的机械动作放在一个小型 stdlib Python helper CLI 中，把根因诊断和修复判断交给 Codex skills。

## 安装

本地开发安装：

```bash
python3 -m pip install -e .
bfk install --yes
```

`bfk install` 会把插件复制到 `~/plugins/bug-fix-kit`，更新个人 marketplace 文件 `~/.agents/plugins/marketplace.json`，并打印下一步要执行的 `codex plugin add bug-fix-kit@personal` 命令。随后在 Codex `/plugins` 中启用 `Bug Fix Kit`；如果 skills 没有立即出现，开启一个新的 Codex 线程。

高级本地安装路径显式传入：

```bash
bfk install --plugin-root . --marketplace ~/.agents/plugins/marketplace.json --yes
```

`--source-root` 仍作为 `--plugin-root` 的兼容别名。已存在的插件安装目录只有在传入 `--yes` 时才会被覆盖。

## 本地 helper CLI

```bash
bfk --help
bfk doctor
bfk init-project --base-url http://localhost:8000 --log-file logs/app.log --header Content-Type=application/json
bfk new login_failed account=13900000000
bfk run --timeout 3
```

已实现的 CLI 命令：

- `bfk install`：复制/注册本地插件，并初始化或更新个人 marketplace。
- `bfk init-project`：创建或更新 `.bfk/PROJECT.md`，写入 base URL、日志文件、默认 headers 和 auth note。
- `bfk new`：创建一个 issue 目录和对应的 `runner.py`。
- `bfk run`：执行选中的 issue runner，并写入一个编号递增的 iteration。
- `bfk doctor`：报告 package/plugin shell 状态。

helper CLI 故意不提供确定性的 `bfk diagnose`、`bfk fix`、`bfk status`、`bfk verify` 或 `bfk auto` 命令。诊断和代码修复需要 Codex 判断力，因此暴露为 skills。

## Codex 工作流

```text
$bfk-init
$bfk-new <issue_name> <key=value ...>
$bfk-run [issue_id]
$bfk-diagnose [issue_id]
$bfk-fix [issue_id]
```

循环证据写在 `.bfk/` 下：

```text
.bfk/
├── PROJECT.md
└── issues/
    └── <issue_id>/
        ├── issue.md
        ├── runner.py
        └── iterations/
            └── 001/
                ├── request.json
                ├── response.json
                ├── output.log
                ├── diagnosis.md   # 由 skill 创建，执行 $bfk-diagnose 前可不存在
                └── fix.md         # 由 skill 创建，执行 $bfk-fix 前可不存在
```

## 实际机制

### 项目初始化

`bfk init-project` 写入 `.bfk/PROJECT.md`。`--header Key=Value` 可以重复传入；这些 headers 会保留到生成的 issue runner 中。`--auth-note` 只作为文档记录，不会被 helper 执行。

### Issue 创建

`bfk new` 要求 `.bfk/PROJECT.md` 已存在；缺失时会给出简洁错误，提示先运行 `$bfk-init`。

参数处理保持简单：

- `key=value` 会写成 `runner.py` 中的 `PARAMS[key] = value`。
- 当没有显式 `value=` 时，自由位置参数会合并成一个 `value` 参数。
- bfk 不推断 password、user ID 等 endpoint 业务字段；需要自定义请求形状时，编辑 `runner.py`。

生成的 runner 默认：

- `POST {BASE_URL}/`
- JSON body 来自 `PARAMS`
- headers 来自 `.bfk/PROJECT.md`，并追加 `X-BugFix-Issue`
- `LOG_FILES` 来自 `.bfk/PROJECT.md`
- `AFTER_REQUEST_WAIT_SECONDS = 2`

直接运行 `python .bfk/issues/<issue_id>/runner.py` 只会打印 request JSON，不会发送 HTTP 请求。

### Run artifacts

`bfk run [issue_id]` 会解析目标 issue，加载 `runner.py`，记录日志文件 offset，执行 HTTP 请求，按配置等待，读取新增日志，然后写入下一个 iteration 目录。

`response.json` 行为：

- 包括 4xx/5xx 在内的 HTTP 响应会记录为 `transport_error: null`。
- 连接失败、错误 URL、畸形请求数据、不可序列化 payload 会记录为 `transport_error.type = "transport_error"`。
- runner import/config/build 失败会记录为 `transport_error.type = "runner_error"`。
- 显式传入不存在的 issue ID 会快速失败：`bfk: issue not found: <id>`，没有 traceback。

`output.log` 只包含捕获 offset 之后追加的日志内容。如果日志文件在捕获 offset 后变短，输出会先包含 `log file truncated` 说明，然后从文件开头读取。

## E2E smoke check

当前产品已跑过真实 mock-service 检查：

1. 启动本地 `127.0.0.1` mock HTTP server；
2. 运行 `bfk init-project`，写入 `Content-Type` 和 `Authorization` headers；
3. 运行 `bfk new "login failed" account=13900000000 mode=e2e`；
4. 运行 `bfk run --timeout 3`；
5. 验证 `request.json`、`response.json` 和 `output.log`。

观察结果：mock service 收到 `POST /`，`response.json.status_code` 为 `200`，`transport_error` 为 `null`，请求 headers 和 JSON body 与 runner 匹配，mock 日志被捕获到 `output.log`。

## MVP 边界

- `$bfk-run` 只执行和采集，不诊断、不编辑代码。
- `$bfk-diagnose` 只写 `diagnosis.md`，不编辑代码、不运行请求。
- `$bfk-fix` 写 `fix.md`，只有明确代码缺陷时才可编辑代码；它不运行验证。
- MVP 不包含 PyPI release 自动化、demo HTTP app、Web UI、OpenTelemetry、远程日志、YAML config 或 auto-fix loop。
