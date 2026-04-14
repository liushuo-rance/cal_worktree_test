# AI 助手 Bash 工具调用

> 描述 AI 助手通过 `bash_run` 调用 CLI 命令的记录、展示与执行规则。

---

## 1. 需求

当 AI 助手需要执行后端操作（查询、统计、导入等）时，只能通过受限的 Bash 命令调用 `src/cli/commands.py` 中的 CLI 函数。工具调用过程需要在 UI 中**持久化显示**一条参数记录，并**保存在对话历史**中，供用户回溯查看。

---

## 2. 行为规则

### 2.1 后端行为 (`src/services/assistant_service.py`)

1. **工具定义**：仅允许 `bash_run` 一个函数，映射到 `exec_bash_command(db_conn, command)`。
2. **命令白名单**：`exec_bash_command` 通过正则严格校验命令：
   ```python
   _ALLOWED_CLI_RE = re.compile(
       r'^python3?\s+(?:-m\s+src\.cli|src/cli/commands\.py|src/cli/main\.py)(?:\s|$)'
   )
   ```
   只有调用 `python3 -m src.cli ...`、`python3 src/cli/commands.py ...` 或 `python3 src/cli/main.py ...` 的命令才会被执行；否则直接返回错误。
3. **执行环境**：命令通过 `subprocess.run(shlex.split(command), cwd=project_root, timeout=30)` 在项目根目录下执行，并捕获 `stdout` / `stderr` / `returncode`。
4. **TOOL_CALL 解析**：模型不在系统提示词中收到 `tools` 参数，而是在回复末尾按如下格式输出：
   ```json
   TOOL_CALL: {"function": "bash_run", "arguments": {"command": "python3 -m src.cli query --employee EMP001"}}
   ```
   `_parse_tool_call()` 从文本末尾提取该 JSON，`_strip_tool_call()` 清理返回给用户的文本。
5. **会话追加流程**：
   - 确认存在有效 `TOOL_CALL` 后，先向对话历史追加 `{"role": "tool_call", "content": "调用了 bash_run", "api_name": "bash_run", "arguments": {...}}`
   - 向 SSE 流输出 `{"type": "tool_call_record", "api_name": "bash_run", "arguments": {...}}`
   - 执行 `bash_run` 并通过 `{"type": "tool_result", ...}` 返回结果
   - 将 `{"role": "tool", "content": "..."}` 追加到对话历史
   - 进行第二次 LLM 调用，生成最终中文总结
6. **LLM 过滤**：`_prepare_llm_messages()` 构造发往 LLM 的消息列表时，**过滤掉** `role == "tool_call"` 的消息（Volces API 不接受该 role）。

### 2.2 前端行为 (`assistant.js` / `assistant.html`)

1. `assistant.js` 监听到 `tool_call_record` 事件后，会在消息列表中插入一个独立的 `.tool-record` DOM 节点（位于 AI 气泡上方）。
2. **卡片内容**：不再显示 "调用了 `api_name`"，而是直接显示**工具参数**（`arguments` 对象的 JSON 字符串）。若长度超过 60 个字符，自动截断并追加 `...`。
3. **参数截断示例**：
   - 短参数：`{"command":"python3 -m src.cli employee list"}`
   - 长参数：`{"command":"python3 -m src.cli query --employee EMP001 --st...`
4. `assistant.html` 对服务端历史中的 `role == "tool_call"` 消息也做同样的参数渲染和截断。
5. **隐藏 TOL_CALL 指令**：流式输出和页面初始加载时，JS 会通过 `stripToolCall()` 将 `TOOL_CALL:` 及之后的文本从气泡中移除，避免用户看到后端调用标记。

### 2.3 路由行为 (`src/web/routes/assistant.py`)

`assistant.py` 无需修改逻辑：

- `GET /assistant/`：从 `session['assistant_chat']` 读取完整对话历史（包含 `tool_call` 角色）并渲染模板。
- `POST /assistant/stream`：透传 `AssistantService.chat_stream()` 产生的所有 SSE 事件；当收到 `type == "done"` 且含 `messages` 时，将完整消息列表（含 `tool_call`）写回 session 并显式保存。
- `POST /assistant/clear`：清空 `session['assistant_chat']`。

---

## 3. SSE 事件类型扩展

新增 / 保留的 SSE 事件类型：

```json
// 思考状态
{"type": "status", "status": "thinking", "message": "AI 正在思考..."}

// 显示工具调用记录卡片
{"type": "tool_call_record", "api_name": "bash_run", "arguments": {"command": "python3 -m src.cli query --employee E001"}}

// 正在执行命令
{"type": "status", "status": "calling_api", "api_name": "bash_run", "message": "正在调用 bash_run..."}

// 工具执行结果
{"type": "tool_result", "api_name": "bash_run", "result": {"success": true, "stdout": "...", "stderr": "", "returncode": 0}}

// 对话完成
{"type": "done", "full_text": "查询完成", "messages": [...]}
```

---

## 4. 系统提示词规范

`AssistantService._build_system_prompt()` 向模型声明：

- 可用的 CLI 文档来自 `src/cli/cli_ref.md`。
- **唯一允许的工具调用格式**：
  ```
  TOOL_CALL: {"function": "bash_run", "arguments": {"command": "bash命令字符串"}}
  ```
- 命令必须通过 `python3 -m src.cli <子命令>`、`python3 src/cli/commands.py <子命令>` 或 `python3 src/cli/main.py <子命令>` 的形式调用。
- 可用的子命令包括：`query`、`report`、`export`、`salary`、`holidays`、`check-holiday`、`comp-off`、`mark-expired-comp-off`、`employee`、`review`、`holiday-import`、`holiday-delete`、`holiday-delete-year`、`overtime-delete`、`stats` 等。

---

## 5. 兼容性

- `tool_call` role 是内部约定，仅用于会话存储和 UI 渲染。
- 发往 LLM 的消息流中不会包含 `role == "tool_call"`，因此兼容 Volces / OpenAI 标准接口。
- 前端截断参数的逻辑（60 字符 + `...`）纯为展示优化，不影响会话存储的完整性。
