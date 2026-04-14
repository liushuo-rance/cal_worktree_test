"""
AI 助手服务
提供基于火山方舟 API 的对话流式响应，支持工具调用
"""

import json
import re
import os
import logging
import sqlite3
import shlex
import subprocess
from typing import List, Dict, Any, Optional, Generator

# 尝试导入 openai 库
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    import requests

from src.cli.commands import CLIError

logger = logging.getLogger(__name__)

# 允许的 CLI 命令正则
_ALLOWED_CLI_RE = re.compile(
    r'^python3?\s+(?:-m\s+src\.cli|src/cli/commands\.py|src/cli/main\.py)(?:\s|$)'
)


def exec_bash_command(db_conn: sqlite3.Connection, command: str) -> Any:
    """通过 Bash 执行 CLI 命令，仅限调用 src/cli/commands.py 相关的入口"""
    command = command.strip()
    if not _ALLOWED_CLI_RE.match(command):
        return {"success": False, "error": "只允许调用 src/cli/commands.py 相关的 CLI 命令"}

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..')
    )

    try:
        args = shlex.split(command)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=project_root,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as e:
        logger.exception("Bash 命令执行异常")
        return {"success": False, "error": str(e)}


ALLOWED_FUNCTIONS = {
    'bash_run': exec_bash_command,
}

# 参数类型强制转换规则
ARGUMENT_COERCION: Dict[str, Any] = {}

CLI_REF_PATH = os.path.join(
    os.path.dirname(__file__),
    '..', '..', 'src', 'cli', 'cli_ref.md'
)

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_RESULT_LENGTH = 2000
MAX_TOOL_CALL_ROUNDS = 10


def _truncate_tool_result(result: Any) -> Any:
    """截断过大的工具返回结果，避免会话文件膨胀"""
    if not isinstance(result, dict):
        return result
    truncated = {}
    for k, v in result.items():
        if isinstance(v, str) and len(v) > MAX_TOOL_RESULT_LENGTH:
            truncated[k] = v[:MAX_TOOL_RESULT_LENGTH] + '\n...（内容已截断）'
        elif isinstance(v, list) and len(v) > 50:
            truncated[k] = v[:50]
            truncated[k].append('...（列表已截断，共 {} 项）'.format(len(v)))
        else:
            truncated[k] = v
    return truncated


def _parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """从 assistant 回复文本末尾解析 TOOL_CALL 指令"""
    text = text.strip()
    marker = 'TOOL_CALL:'
    idx = text.rfind(marker)
    if idx == -1:
        return None
    json_str = text[idx + len(marker):].strip()
    if not json_str:
        return None
    try:
        payload = json.loads(json_str)
        if isinstance(payload, dict) and 'function' in payload:
            return payload
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _strip_tool_call(text: str) -> str:
    """移除 assistant 回复末尾的 TOOL_CALL 指令"""
    idx = text.rfind('TOOL_CALL:')
    if idx != -1:
        return text[:idx].strip()
    return text.strip()


class AssistantService:
    """AI 助手服务"""

    def __init__(self):
        self.api_key = os.environ.get('VOLCES_API_KEY', '39fb2f6b-3062-41f7-8abb-3e879f03270b')
        self.base_url = os.environ.get('VOLCES_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        self.model = os.environ.get('VOLCES_MODEL', 'ep-20260331092634-wfnm8')

        if HAS_OPENAI:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        else:
            self.client = None

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """读取 CLI 文档并构建系统提示词"""
        try:
            with open(CLI_REF_PATH, 'r', encoding='utf-8') as f:
                cli_doc = f.read()
        except Exception as e:
            logger.warning(f"读取 CLI 文档失败: {e}")
            cli_doc = "（文档暂时不可用）"

        return f"""你是一个加班记录管理系统的智能助手。你可以帮助用户查询、导入、统计加班记录和工资信息。

以下是可用的 CLI 文档：

{cli_doc}

## 工具调用规则
当且仅当你的回复需要通过执行命令才能满足用户需求时，在回复末尾单独一行输出：
TOOL_CALL: {{"function": "bash_run", "arguments": {{"command": "bash命令字符串"}}}}
命令必须通过以下方式之一调用 src/cli/commands.py：
- python3 -m src.cli <子命令> [参数...]
- python3 src/cli/commands.py <子命令> [参数...]
- python3 src/cli/main.py <子命令> [参数...]

可用的子命令包括：query、report、export、salary、holidays、check-holiday、comp-off、mark-expired-comp-off、employee、review、holiday-import、holiday-delete、holiday-delete-year、overtime-delete、stats 等。
数据库路径默认为 data/overtime.db，如无需自定义请不要加 --db 参数。

一次只能调用一个工具，但你可以在收到上一次执行结果后继续调用下一个工具，直到获取全部所需信息后再给用户简洁友好的中文回复。最多允许连续调用 {MAX_TOOL_CALL_ROUNDS} 轮。
"""

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        db_conn: sqlite3.Connection
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式对话主循环

        Yields SSE 事件字典
        """
        if not messages:
            yield {"type": "error", "message": "对话历史为空"}
            return

        round_num = 0
        while True:
            round_num += 1
            if round_num > MAX_TOOL_CALL_ROUNDS:
                yield {"type": "error", "message": f"工具调用轮数超过上限（{MAX_TOOL_CALL_ROUNDS}轮），请简化需求后重试"}
                return

            llm_messages = self._prepare_llm_messages(messages)
            yield {"type": "status", "status": "thinking", "message": "AI 正在思考..."}

            try:
                full_text, assistant_msg = yield from self._yield_llm_stream(llm_messages)
            except Exception as e:
                logger.exception("LLM 调用失败")
                yield {"type": "error", "message": f"AI 调用失败: {str(e)}"}
                return

            text = assistant_msg.get('content') or ''
            tool_call = _parse_tool_call(text)

            if not tool_call:
                messages.append(assistant_msg)
                yield {
                    "type": "done",
                    "full_text": _strip_tool_call(text),
                    "messages": messages,
                }
                return

            clean_text = _strip_tool_call(text)
            if clean_text:
                messages.append({"role": "assistant", "content": clean_text})

            func_name = tool_call['function']
            arguments = tool_call.get('arguments', {})

            if func_name not in ALLOWED_FUNCTIONS:
                logger.warning(f"模型请求了未允许的函数: {func_name}")
                error_result = {"success": False, "error": f"不支持的函数: {func_name}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": "",
                    "content": json.dumps(error_result, ensure_ascii=False, default=str),
                })
                # 回到循环开头，再次请求 LLM，让模型处理错误
                continue
            else:
                messages.append({
                    "role": "tool_call",
                    "content": f"调用了 {func_name}",
                    "api_name": func_name,
                    "arguments": arguments,
                })
                yield {
                    "type": "tool_call_record",
                    "api_name": func_name,
                    "arguments": arguments,
                }

                yield {
                    "type": "status",
                    "status": "calling_api",
                    "api_name": func_name,
                    "message": f"正在调用 {func_name}...",
                }

                try:
                    result = self._execute_tool(func_name, arguments, db_conn)
                except CLIError as e:
                    result = {"success": False, "error": str(e)}
                except Exception as e:
                    logger.exception(f"工具调用异常: {func_name}")
                    result = {"success": False, "error": f"调用异常: {str(e)}"}

                result = _truncate_tool_result(result)

                yield {
                    "type": "tool_result",
                    "api_name": func_name,
                    "result": result,
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": "",
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
                # 回到循环开头，继续下一轮 LLM 调用（支持多轮工具调用）
                continue

    def _prepare_llm_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        构造发送给 LLM 的消息列表：system prompt + 最近最多 MAX_HISTORY_MESSAGES 条历史
        过滤掉内部 role=tool_call 的记录（Volces API 不接受该 role）
        """
        history = messages[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else messages
        history = [m for m in history if m.get('role') != 'tool_call']
        return [{"role": "system", "content": self.system_prompt}] + history

    def _yield_llm_stream(
        self,
        messages: List[Dict[str, str]]
    ) -> tuple[str, Dict[str, Any]]:
        """
        调用 LLM 流式接口，透传 delta 事件，最后返回完整文本和 assistant 消息字典
        """
        full_text_parts = []

        if HAS_OPENAI and self.client:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,  # type: ignore[arg-type]
                "temperature": 0.3,
                "max_tokens": 4000,
                "stream": True,
                "timeout": 300,
            }
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta
                content = getattr(delta, 'content', None) or ''
                if content:
                    full_text_parts.append(content)
                    yield {"type": "delta", "content": content}
        else:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4000,
                "stream": True,
            }
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=300
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data = line_text[6:]
                    if data.strip() == '[DONE]':
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj['choices'][0].get('delta', {}).get('content', '') or ''
                        if delta:
                            full_text_parts.append(delta)
                            yield {"type": "delta", "content": delta}
                    except Exception:
                        pass

        full_text = ''.join(full_text_parts)
        assistant_msg: Dict[str, Any] = {"role": "assistant", "content": full_text or None}
        return full_text, assistant_msg

    def _execute_tool(
        self,
        func_name: str,
        arguments: Dict[str, Any],
        db_conn: sqlite3.Connection
    ) -> Any:
        """执行工具调用"""
        func = ALLOWED_FUNCTIONS[func_name]

        coerced_args = {}
        for key, value in arguments.items():
            if key in ARGUMENT_COERCION and value is not None:
                try:
                    coerced_args[key] = ARGUMENT_COERCION[key](value)
                except Exception as e:
                    raise CLIError(f"参数 {key} 格式错误: {value} ({e})")
            else:
                coerced_args[key] = value

        return func(db_conn, **coerced_args)


# 全局实例
_assistant_service = None


def get_assistant_service() -> AssistantService:
    """获取 AI 助手服务实例"""
    global _assistant_service
    if _assistant_service is None:
        _assistant_service = AssistantService()
    return _assistant_service
