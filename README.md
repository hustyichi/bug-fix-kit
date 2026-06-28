# Bug Fix Kit

语言：简体中文 | [English](README.en.md)

Bug Fix Kit（`bfk`）是一个本地 Codex 插件，帮你把一次本地服务 bug 处理成清晰的三步：

```text
采集证据 -> 定位根因 -> 最小修复
```

它适合这样的场景：你有一个本地运行的服务、一个可以复现问题的请求，以及一份本地日志。你把这些信息交给 Codex，BFK 会保存请求、响应和本次新增日志，让后续定位和修复不靠猜。

## 安装

### 发布版安装

```bash
python3 -m pip install bug-fix-kit
bfk doctor
bfk install --yes
```

`pip install bug-fix-kit` 只安装本地 `bfk` 命令。`bfk install --yes` 会安装 Codex 插件，并打印类似下面的下一步命令：

```bash
codex plugin add bug-fix-kit@personal
```

执行打印出的命令后，在 Codex 的 `/plugins` 中启用 `Bug Fix Kit`。如果没有立刻看到 BFK skills，开一个新的 Codex 线程即可。

## 快速开始

### 1. 准备本地服务

使用前请先确认：

- 本地服务已经启动。
- 你知道要请求的 base URL，例如 `http://127.0.0.1:8000`。
- 你知道日志文件位置，例如 `logs/app.log`。
- 最好有一条可以复现问题的 curl 请求。

首次使用时，可以直接把这些信息告诉 Codex：

```text
我要用 Bug Fix Kit 调试这个项目。
本地服务：http://127.0.0.1:8000
日志文件：logs/app.log
复现请求：
curl --location 'http://127.0.0.1:8000/login' \
  --header 'Content-Type: application/json' \
  --data '{"account":"13900000000","password":"bad"}'
```

BFK 会把项目级配置保存到 `.bfk/PROJECT.md`，后面同一个项目可以复用。

### 2. 采集一次复现证据

在 Codex 中运行：

```text
$bfk-capture "login failed" account=13900000000 password=bad
```

`$bfk-capture` 会执行一次本地请求，并写入：

- `.bfk/request.json`：实际发送的请求
- `.bfk/response.json`：本次响应或连接错误
- `.bfk/output.log`：请求期间日志文件新增的内容

### 3. 定位根因

```text
$bfk-locate
```

Codex 会读取 capture 产物、日志和相关代码，写出 `.bfk/root-cause.md`。如果证据不足，它会说明缺什么，而不是猜根因。

只有日志、没有可复现请求时，也可以这样用：

```text
$bfk-locate --log logs/error.log --issue "login failed"
```

### 4. 执行最小修复

```text
$bfk-fix
```

`$bfk-fix` 只在 `root-cause.md` 已经确认代码缺陷时修改代码。能复用 capture 验证时会重新跑请求；不能验证时会在 `.bfk/fix.md` 里写清楚。

## 日志怎么获取

BFK 当前使用本地文件日志。

执行请求前，它会记录日志文件当前大小；请求完成后，再读取这之后新增的内容，并写入 `.bfk/output.log`。所以 `output.log` 存的是日志文本，不是偏移量。

这个机制对本地 `logging.FileHandler`、普通 app log 文件很友好。需要注意：

- 日志路径要写对，推荐使用相对项目根目录的路径或绝对路径。
- 如果服务异步写日志，可以把等待时间调长后再 capture。
- 如果同时有其他请求写日志，`output.log` 可能混入其他请求的日志。
- 如果日志写到 Docker stdout、journalctl 或远程日志，需要先把相关日志落到本地文件，或直接用 `$bfk-locate --log ...`。

更精确的做法是在应用日志里打印请求 ID。BFK 生成的请求会带上 `X-BugFix-Issue` header，你也可以让服务把类似 request id / capture id 写进日志，定位时会更稳。

## `.bfk/` 里有什么

```text
.bfk/
├── PROJECT.md       # 本地服务、日志、请求样例等项目配置
├── issue.md         # 当前问题描述和参数
├── runner.py        # 当前问题的请求构造脚本
├── request.json     # 本次实际请求
├── response.json    # 本次响应
├── output.log       # 本次执行窗口内新增日志
├── root-cause.md    # locate 生成的根因报告
└── fix.md           # fix 生成的修复记录
```

BFK 只保留一个当前问题。新的 `$bfk-capture` 会覆盖旧的 capture 产物，并清理旧的 `root-cause.md` 和 `fix.md`。

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

- `.bfk/PROJECT.md` 里的日志路径是否正确。
- 本地服务是否真的把日志写入文件。
- 请求完成后日志是否异步延迟写入。

必要时，把日志文件改成绝对路径，或把请求后的等待时间调大。

### 我只想让 Codex 看一份错误日志，可以吗？

可以，直接运行：

```text
$bfk-locate --log logs/error.log --issue "这里写问题现象"
```

这种模式可以定位根因，但通常无法自动复现和验证修复。

## 本地开发

开发本插件时：

```bash
python3 -m pip install -e .
bfk install --yes
```

发布包中的插件内容来自构建生成的 `bug_fix_kit/plugin_payload/bug-fix-kit`。从源码安装时，`--plugin-root` / `--source-root` 可以指向本仓库根目录；安装器只会复制 `.codex-plugin/` 和 `skills/`。
