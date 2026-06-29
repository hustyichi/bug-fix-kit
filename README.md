# Bug Fix Kit

语言：简体中文 | [English](README.en.md)

[![PyPI](https://img.shields.io/pypi/v/bug-fix-kit.svg)](https://pypi.org/project/bug-fix-kit/)

Bug Fix Kit（`bfk`）是一个本地 Codex 插件，帮你把一次本地服务 bug 处理成清晰的三步：

```text
采集证据 -> 定位根因 -> 最小修复
```

它适合这样的场景：你有一个本地运行的服务、一个可以复现问题的请求，以及一份本地日志。你把这些信息交给 Codex，BFK 会保存请求、响应和本次新增日志，让后续定位和修复不靠猜。

## 适合谁

适合你，如果你已经有：

- 一个可以在本地启动的服务。
- 一条能复现问题的请求，最好是完整 curl。
- 一份服务日志文件，例如 `logs/app.log`。
- 想让 Codex 基于证据定位根因，并只做必要修复。

## 安装

推荐使用 PyPI 包一键安装插件：

```bash
uvx --from bug-fix-kit bfk install --yes
```

如果希望长期保留 `bfk` 命令，也可以用 pip 安装：

```bash
python3 -m pip install bug-fix-kit
bfk doctor
bfk install --yes
```

`bfk install --yes` 会打印下一步命令，通常类似：

```bash
codex plugin add bug-fix-kit@personal
```

执行打印出的命令后，在 Codex 的 `/plugins` 中启用 `Bug Fix Kit`。如果刚启用后当前会话里还看不到 BFK skills，开一个新的 Codex 线程即可。

## 快速开始

下面这些命令都在**你的项目**里运行，不是在本仓库里运行。

### 1. 准备本次问题信息

使用前请先确认：

- 本地服务已经启动。
- 你知道要请求的 base URL，例如 `http://127.0.0.1:8000`。
- 你知道日志文件位置，例如 `logs/app.log`。
- 你有一条可以复现问题的请求。

### 2. 采集复现证据

在 Codex 中运行，并把本次请求的完整上下文一起传给 `$bfk-capture`：

```text
$bfk-capture 我要用 Bug Fix Kit 处理这个登录失败问题。
本地服务：http://127.0.0.1:8000
日志文件：logs/app.log
复现请求：
curl --location 'http://127.0.0.1:8000/login' \
  --header 'Content-Type: application/json' \
  --data '{"account":"13900000000","password":"bad"}'
```

`$bfk-capture` 会执行一次本地请求，并写入：

- `.bfk/request.json`：实际发送的请求。
- `.bfk/response.json`：本次响应或连接错误。
- `.bfk/output.log`：请求期间日志文件新增的内容。

如果要改变请求内容，请再次提供完整的本次请求上下文。没有提供任何参数或新上下文时，`$bfk-capture` 会重放已有 `.bfk/runner.py`。

### 3. 定位根因

```text
$bfk-locate
```

Codex 会读取 capture 产物、日志和相关代码，写出 `.bfk/root-cause.md`。如果证据不足，它会说明缺什么，而不是猜根因。

只有日志、没有可复现请求时，也可以这样用：

```text
$bfk-locate
日志文件：logs/error.log
问题现象：login failed
```

### 4. 执行最小修复

```text
$bfk-fix
```

`$bfk-fix` 只在 `root-cause.md` 已经确认代码缺陷时修改代码。能复用 capture 验证时会重新跑请求，并把本次回归新增日志写入 `.bfk/fix_output.log`；不能验证时会在 `.bfk/fix.md` 里写清楚。

## 输出结构

BFK 只保留一个当前 bug 现场。新的 `$bfk-capture` 会先把旧现场归档，再替换 `.bfk/` 顶层产物。

```text
.bfk/
├── runner.py        # 当前 capture 的请求脚本
├── request.json     # 本次实际请求
├── response.json    # 本次响应
├── output.log       # 本次执行窗口内新增日志
├── root-cause.md    # locate 生成的根因报告
├── fix.md           # fix 生成的修复记录
├── fix_output.log   # fix 回归验证期间新增日志
└── archive/         # 历史 bug 现场归档
```

## 日志说明

BFK 当前读取本地文件日志。执行请求前，它会记录日志文件当前大小；请求完成后，再读取这之后新增的内容，并写入 `.bfk/output.log`。

需要注意：

- 日志路径要写对，推荐使用相对项目根目录的路径或绝对路径。
- 如果服务异步写日志，可以把等待时间调长后再 capture。
- 如果同时有其他请求写日志，`output.log` 可能混入其他请求的日志。
- 如果日志写到 Docker stdout、journalctl 或远程日志，请先把相关日志落到本地文件，或直接用 `$bfk-locate` 提供日志内容。

更精确的做法是在应用日志里打印请求 ID。如果你的服务支持 request id / capture id，可以在本次请求上下文里带上对应 header，定位时会更稳。

## 常见问题

### `bfk` 命令里为什么没有 capture / locate / fix？

这是正常的。`bfk` CLI 只负责安装和检查插件：

```bash
bfk --help
bfk doctor
bfk install --yes
```

真正处理 bug 的入口是 Codex skills：

```text
$bfk-capture
$bfk-locate
$bfk-fix
```

### 没有 curl 请求可以用吗？

可以，但效果会差一些。你可以先提供 base URL、endpoint、headers 和关键参数，让 BFK 生成一个简单请求。最好还是补一条真实 curl，请求结构越真实，capture 越可靠。

### `output.log` 为空怎么办？

先检查三件事：

- 本次 `$bfk-capture` 提供的日志路径是否正确。
- 本地服务是否真的把日志写入文件。
- 请求完成后日志是否异步延迟写入。

必要时，把日志文件改成绝对路径，或把请求后的等待时间调大。

### 我只想让 Codex 看一份错误日志，可以吗？

可以，直接运行：

```text
$bfk-locate
日志文件：logs/error.log
问题现象：这里写问题现象
```

这种模式可以定位根因，但通常无法自动复现和验证修复。
