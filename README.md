# Bug Fix Kit

语言：简体中文 | [English](README.en.md)

Bug Fix Kit（`bfk`）是一个可通过 PyPI 分发的本地 Codex 插件，用于把本地服务异常处理压成三个步骤：采集证据、定位根因、执行最小修复。

它把确定性的请求重放、日志采集和 artifact 写入放在 stdlib Python helper 中，把根因判断和代码修复交给 Codex skills。

## 安装

发布版安装：

```bash
python3 -m pip install bug-fix-kit
bfk --help
bfk doctor
bfk install --yes
```

`pip install bug-fix-kit` 只安装 `bfk` CLI；不会自动启用 Codex 插件。

`bfk install` 会把插件复制到 `~/plugins/bug-fix-kit`，更新个人 marketplace 文件 `~/.agents/plugins/marketplace.json`，并打印下一步要执行的 `codex plugin add bug-fix-kit@personal` 命令。随后在 Codex `/plugins` 中启用 `Bug Fix Kit`；如果 skills 没有立即出现，开启一个新的 Codex 线程。

本地开发安装：

```bash
python3 -m pip install -e .
bfk install --yes
```

`--plugin-root` / `--source-root` 可指定自定义插件源；指向本仓库根目录时只复制 `.codex-plugin/` 与 `skills/`。从 wheel 运行时，`bfk` 使用构建生成的 `bug_fix_kit/plugin_payload/bug-fix-kit` 包资源。已存在的插件安装目录只有在传入 `--yes` 时才会被覆盖。

PyPI distribution 名称是 `bug-fix-kit`，安装后的 console script 是 `bfk`，Python import package 是 `bug_fix_kit`。

## 本地 helper CLI

```bash
bfk --help
bfk doctor
bfk install --yes
```

helper CLI 只负责插件安装和外壳检查。项目问题处理由 Codex skills 完成；CLI 不提供工作流命令。

## Codex 工作流

```text
$bfk-capture "<issue_name>" <key=value ...>
$bfk-locate [issue_id]
$bfk-fix [issue_id]
```

日志文件直接定位也走 locate：

```text
$bfk-locate --log logs/error.log --issue "login failed"
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
                ├── capture.md
                ├── root-cause.md
                └── fix.md
```

## 实际机制

### Capture

`$bfk-capture` 是一站式证据采集入口。它根据本地项目知识、请求样例、请求参数或已有 issue，创建或复用 issue/session 与 runner，执行一次本地请求，采集本轮 request、response 和新增日志。

边界：只执行和采集，不定位根因、不编辑代码、不写 `root-cause.md`。

### Locate

`$bfk-locate` 根据 capture 产物或用户直接提供的日志文件读取相关代码，沿着“症状 -> 日志/响应证据 -> 代码路径 -> 根因”的直线链路写 `root-cause.md`。

如果证据不足，它必须输出 `unknown` 并列出缺失证据；如果服务、日志、输入或代码上下文不可用，它输出 `blocked`。它不能把最后一个异常当作已确认根因。

边界：只分析和写根因报告，不执行请求、不编辑代码、不写 `fix.md`。

### Fix

`$bfk-fix` 只在 `root-cause.md` 给出已确认代码缺陷时执行最小修复。若存在可复现 capture 上下文，它会尽量复用同一 issue 验证；若只有日志定位上下文，则写出 `changed_unverified` 并提示用户补充可复现请求或手动验证。

边界：不从 `unknown` / `blocked` 报告猜修，不声称未执行过的验证。

## MVP 边界

- 无 runtime dependencies。
- 不提供 demo HTTP app、Web UI、OpenTelemetry、远程日志、YAML config 或自动 mock。
- 不新增公共工作流 CLI 命令。
