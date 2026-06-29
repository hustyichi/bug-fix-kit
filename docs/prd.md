# Bug Fix Kit MVP 产品文档（当前实现）

## 1. 产品定位

Bug Fix Kit（`bfk`）是一个本地 Codex 插件包，用于把一次本地服务异常处理沉淀为可重复查看的证据、根因报告和修复记录。

当前实现采用 **three-step minimal** 形态：

- Python stdlib helper CLI 只负责插件安装、外壳检查，以及 skills 复用的确定性请求/日志/artifact mechanics。
- Codex skills 暴露三个步骤：`$bfk-capture`、`$bfk-locate`、`$bfk-fix`。
- 根因定位必须基于日志/响应证据和代码直线链路；证据不足时输出 `unknown` 或 `blocked`，不能猜根因。
- 当前实现只跟踪一个活动 capture；`.bfk/` 顶层就是当前 capture，不维护多 issue 名称或多轮 iteration。

MVP 不内置 demo HTTP app、不提供 Web UI、不自动 mock 外部依赖。

## 2. 分发与安装

本项目是可发布到 PyPI 的本地 Codex plugin package：

```text
.codex-plugin/plugin.json
skills/bfk-*/SKILL.md
src/bug_fix_kit/*.py
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

CLI 命令保持：

```text
bfk install
bfk doctor
```

CLI 不提供公共问题处理命令。

## 3. 用户可见能力

```text
$bfk-capture <key=value ...>
$bfk-locate
$bfk-fix
```

直接日志定位：

```text
$bfk-locate --log logs/error.log --issue "login failed"
```

## 4. `.bfk` artifact contract

```text
.bfk/
├── runner.py
├── request.json
├── response.json
├── output.log
├── root-cause.md
└── fix.md
```

规则：

- `.bfk/runner.py` 是当前 capture 的请求构造脚本。
- 每次 capture 覆盖 `.bfk/` 顶层当前 capture 产物。
- 新 capture 会删除旧的 `request.json`、`response.json`、`output.log`、`runner.py`、`root-cause.md`、`fix.md`，也会清理旧版遗留的 `PROJECT.md` 和 `issue.md`。
- `request.json`、`response.json`、`output.log` 由 `$bfk-capture` 写入。
- `root-cause.md` 由 `$bfk-locate` 写入。
- `fix.md` 由 `$bfk-fix` 写入。
- 日志直接定位场景可以没有 `runner.py`、`request.json` 或 `response.json`，但报告必须写明缺失证据。

## 5. `$bfk-capture`

作用：一站式创建或替换当前 capture，或在无参数无新上下文时重放已有请求并采集证据。

输入：

- 请求参数或请求样例；
- base URL、headers、日志文件、等待时间等当前请求上下文。

行为：

1. 如果没有参数也没有新请求上下文，重放已有 `.bfk/runner.py`；若不存在则要求用户提供可复现请求。
2. 如果有参数或新上下文，只使用本次请求上下文创建新的独立 capture；上下文不足时说明缺失项，不复用旧请求。
3. 覆盖 `.bfk/` 下当前 capture 产物。
4. 创建新的 `runner.py`。
5. 执行一次本地请求。
6. 采集 request、response 和 offset 后新增日志。
7. 写入 `.bfk/request.json`、`.bfk/response.json`、`.bfk/output.log`。

边界：不定位根因、不编辑代码、不写 `root-cause.md` 或 `fix.md`。

## 6. `$bfk-locate`

作用：基于 capture 产物或显式日志文件，结合代码找到根因。

输入：

- `.bfk/request.json`、`.bfk/response.json`、`.bfk/output.log`；
- 或用户显式提供的日志文件与 issue 描述；
- 相关本地代码。

根因标准：

- 有“症状 -> 日志/响应证据 -> 代码路径 -> 根因”的直线链路时，输出 `root_cause_found`。
- 证据不足时，输出 `unknown` 并列出缺失证据。
- 服务、日志、输入或代码上下文不可用时，输出 `blocked`。
- 最终异常只能作为近端证据，不能单独当作已确认根因。

输出 `root-cause.md`，建议字段：

- `status`
- `symptom`
- `direct_chain`
- `root_cause`
- `evidence`
- `related_code`
- `missing_evidence`
- `recommended_fix`
- `confidence`

边界：不执行请求、不编辑代码、不写 `fix.md`。

## 7. `$bfk-fix`

作用：基于已确认的 `root-cause.md` 执行最小代码修复。

行为：

1. 读取最新 `root-cause.md`。
2. 若状态为 `unknown`、`blocked`、缺失根因或不是代码缺陷，则拒绝编辑。
3. 若根因明确，执行最小修复。
4. 有可复现 capture 上下文时，复用 `.bfk/` 下当前请求验证。
5. 只有日志上下文时，写 `changed_unverified`，并提示用户补充请求或手动验证。

最终状态：

- `fixed_verified`
- `changed_unverified`
- `still_failed`
- `refused`
- `blocked`

边界：不猜修、不做无关重构、不声称未执行过的验证。

## 8. 验收标准

必过检查：

```bash
python3 -m compileall -q src/bug_fix_kit scripts tests
pytest -q
python3 -m bug_fix_kit --help
bfk --help
bfk doctor
bfk install --home <tmp> --yes
bfk install --marketplace <tmp>/.agents/plugins/marketplace.json --yes
python3 /Users/bryan/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

旧公共合同扫描必须覆盖 README、docs、插件 metadata、skills、source、tests、scripts，并保持 zero-hit；旧公共合同字面量不留在源码、测试或用户文档中。
