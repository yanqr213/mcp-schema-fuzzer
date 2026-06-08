# mcp-schema-fuzzer

`mcp-schema-fuzzer` 是一个离线 Python CLI，用来测试 MCP server、agent tool wrapper、resource handler 的输入校验和报错稳定性。它读取 MCP 风格 schema、JSON Schema 风格输入定义、示例 tool calls 与录制 transcript，自动生成缺字段、错类型、越界值、超长文本、危险路径字符串等 fuzz case，然后验证这些非法输入是否被稳定拒绝，并输出 Markdown、JSON、JUnit 报告供本地审查与 CI gate 使用。

项目目标不是做在线渗透，也不会执行危险 payload。它专注于“接口契约是否守住边界”和“错误响应是否稳定可依赖”。

## 适用场景

- MCP tool 的 `inputSchema` 在演进后，担心必填字段或 enum 漏校验
- agent tool wrapper 会把 JSON 参数转给本地代码，想验证错类型和超长文本是否被一致拒绝
- resource handler 接收路径、URI、过滤器、分页参数，想检查路径穿越字符串是否被安全处理
- CI 中希望阻止新的 `warning` 或 `error` 级别问题进入主分支

## 特性

- 零运行时依赖，Python 3.9+
- 可安装 CLI：`mcp-schema-fuzzer`
- 子命令：`fuzz`、`validate-fixtures`、`init-suite`、`explain`、`check`
- 支持对象、数组、字符串、整数、数字、布尔值、enum、required、min/max 边界
- 生成危险路径字符串，但绝不执行
- 从示例 payload 派生 fuzz case；无示例时可按 schema 合成最小有效请求
- transcript 结构校验、重复 case 稳定性校验、按类别错误码稳定性校验
- 去重、severity 分级、Markdown/JSON/JUnit 报告
- `--output` 自动创建父目录
- `--check warning|error` 可直接作为 CI gate

## 安装

```bash
python -m pip install .
```

开发模式：

```bash
python -m pip install -e .
```

## 快速开始

初始化一个新 suite：

```bash
mcp-schema-fuzzer init-suite work/my-suite
```

校验 fixture：

```bash
mcp-schema-fuzzer validate-fixtures examples/filesystem-tool/suite.json
```

生成报告并在 `error` 级别做 gate：

```bash
mcp-schema-fuzzer fuzz examples/filesystem-tool/suite.json --output outputs/example/filesystem --check error
```

解释某个 case 的生成原因：

```bash
mcp-schema-fuzzer explain examples/filesystem-tool/suite.json filesystem.read.dangerous-path.path
```

对已生成 JSON 报告再次执行 gate：

```bash
mcp-schema-fuzzer check outputs/example/filesystem.json --check warning
```

## Suite 输入格式

最小 suite 文件如下：

```json
{
  "name": "filesystem-suite",
  "description": "Read-only filesystem wrapper fixtures.",
  "targets": [
    {
      "id": "filesystem.read",
      "kind": "tool",
      "schema": "schemas/filesystem.read.schema.json",
      "examples": "fixtures/filesystem.read.examples.json",
      "transcripts": "fixtures/filesystem.read.transcripts.json"
    }
  ]
}
```

### schema 文件

支持常见 JSON Schema 风格字段：

- `type`
- `properties`
- `required`
- `items`
- `enum`
- `minimum` / `maximum`
- `minLength` / `maxLength`
- `minItems` / `maxItems`

### examples 文件

```json
{
  "examples": [
    {
      "name": "read README",
      "payload": {
        "path": "docs/guide.md",
        "encoding": "utf-8",
        "limit": 128
      }
    }
  ]
}
```

### transcripts 文件

```json
{
  "entries": [
    {
      "case_id": "filesystem.read.missing-required.path",
      "target": "filesystem.read",
      "request": {
        "encoding": "utf-8",
        "limit": 128
      },
      "response": {
        "ok": false,
        "error": {
          "code": "INVALID_ARGUMENT",
          "message": "path is required"
        }
      }
    }
  ]
}
```

`response.ok` 为 `true` 表示 server 接受了一个本应失败的非法输入，`fuzz` 会将其判定为 `error`。

## MCP / Agent Tool 测试工作流

1. 从 MCP server 或 tool wrapper 中导出 `inputSchema` 或等价 schema。
2. 录入一到多个“正常调用”示例，确保能覆盖你关心的可选字段。
3. 把离线录制的错误 transcript 保存为 fixtures。
4. 运行 `fuzz` 生成非法请求矩阵并验证响应。
5. 在 PR / CI 中使用 `--check warning` 或 `--check error` 作为 gate。
6. 用 `explain` 帮助开发者理解某个 case 为什么被生成、其 severity 是什么。

## 报告输出

给定 `--output outputs/run/report`，会生成：

- `outputs/run/report.md`
- `outputs/run/report.json`
- `outputs/run/report.xml`

JSON 适合程序读取，Markdown 适合代码审查，JUnit XML 适合 CI 平台展示。

## 隐私与安全边界

- 完全离线，不调用外部服务
- 不会发送 schema、transcript、payload 到网络
- 只读取你提供的本地 fixture 文件
- 会生成危险路径字符串，但不会打开文件、执行命令、访问网络或尝试利用它们
- 不负责判断业务逻辑漏洞，只验证输入边界和错误响应行为

## 限制

- 当前专注于常见 JSON Schema 子集，不覆盖完整草案语义
- 不执行被测 server；需要你提供离线 transcript
- 对 `oneOf` / `allOf` / `$ref` 等复杂组合的支持仍然保守
- 错误稳定性基于 transcript 中的结构和错误码，而不是运行时重放

## CI 集成

GitHub Actions 示例已包含在 `.github/workflows/ci.yml`。如果你想在自己的仓库中 gate `warning`：

```bash
python -m mcp_schema_fuzzer fuzz suites/main/suite.json --output artifacts/fuzz/report --check warning
```

## 示例

- `examples/filesystem-tool`
- `examples/resource-tool`

两个目录都可以直接运行 `validate-fixtures` 和 `fuzz`。

## English

`mcp-schema-fuzzer` is an offline Python CLI for validating MCP and agent-tool input contracts. It reads schema files, example calls, and recorded transcripts, generates invalid boundary cases, checks whether those cases are rejected consistently, and emits Markdown, JSON, and JUnit reports for local review and CI gating.

Core commands:

- `fuzz`
- `validate-fixtures`
- `init-suite`
- `explain`
- `check`

Key safety guarantees:

- No external services
- No execution of dangerous path strings
- Standard-library-first implementation

Typical flow:

1. Export a schema from your MCP server or wrapper.
2. Add one or more valid example payloads.
3. Record invalid-input transcripts offline.
4. Run `fuzz` and gate your CI with `--check warning` or `--check error`.
