"""
AI 助手服务测试
验证文本解析式 tool calling 与 bash_run 单工具逻辑
"""

import pytest
import sys
import os
import sqlite3
import tempfile
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.assistant_service import (
    AssistantService,
    ALLOWED_FUNCTIONS,
    _parse_tool_call,
    _strip_tool_call,
    exec_bash_command,
)


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    yield conn
    conn.close()
    os.unlink(path)


class TestAssistantServiceTextToolCalls:
    """测试文本解析式工具调用（仅 bash_run）"""

    def test_only_bash_run_allowed(self):
        """只允许 bash_run 一个函数"""
        assert set(ALLOWED_FUNCTIONS.keys()) == {"bash_run"}

    def test_tool_call_record_yielded_from_text_parsing(self, test_db, monkeypatch):
        """模型通过文本中的 TOOL_CALL 返回工具调用时，应 yield tool_call_record 事件"""
        service = AssistantService()

        call_count = 0
        def mock_yield_llm_stream(messages):
            nonlocal call_count
            call_count += 1
            text = '正在查询记录。\n\nTOOL_CALL: {"function": "bash_run", "arguments": {"command": "python3 -m src.cli stats"}}'
            yield {"type": "delta", "content": text}
            return text, {"role": "assistant", "content": text}

        monkeypatch.setattr(service, '_yield_llm_stream', mock_yield_llm_stream)
        monkeypatch.setattr(service, '_execute_tool', lambda fn, args, db: {"success": True, "stdout": "{}"})

        messages = [{"role": "user", "content": "查询记录"}]
        events = list(service.chat_stream(messages, test_db))

        tool_call_events = [e for e in events if e.get('type') == 'tool_call_record']
        assert len(tool_call_events) == 1
        assert tool_call_events[0]['api_name'] == 'bash_run'
        assert tool_call_events[0]['arguments'] == {"command": "python3 -m src.cli stats"}

    def test_tool_result_appended_as_role_tool(self, test_db, monkeypatch):
        """工具执行后，对话历史应追加 role=tool 消息"""
        service = AssistantService()

        def mock_yield_llm_stream(messages):
            text = '正在计算。\n\nTOOL_CALL: {"function": "bash_run", "arguments": {"command": "python3 -m src.cli employee list"}}'
            yield {"type": "delta", "content": text}
            return text, {"role": "assistant", "content": text}

        monkeypatch.setattr(service, '_yield_llm_stream', mock_yield_llm_stream)
        monkeypatch.setattr(service, '_execute_tool', lambda fn, args, db: {"success": True, "stdout": "2\n"})

        messages = [{"role": "user", "content": "计算"}]
        events = list(service.chat_stream(messages, test_db))

        done_events = [e for e in events if e.get('type') == 'done']
        final_messages = done_events[0]['messages']

        tool_msgs = [m for m in final_messages if m.get('role') == 'tool']
        assert len(tool_msgs) == 1
        assert json.loads(tool_msgs[0]['content']) == {"success": True, "stdout": "2\n"}

    def test_prepare_llm_messages_keeps_tool_role_and_filters_tool_call(self):
        """构造 LLM 消息时应保留 role=tool，但过滤掉 role=tool_call"""
        service = AssistantService()
        messages = [
            {"role": "user", "content": "帮我查一下"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "bash_run", "arguments": "{}"}}]},
            {"role": "tool_call", "api_name": "bash_run", "arguments": {}, "content": "调用了 bash_run"},
            {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
            {"role": "assistant", "content": "好的"},
        ]
        llm_messages = service._prepare_llm_messages(messages)

        roles = [m['role'] for m in llm_messages]
        assert 'tool_call' not in roles
        assert 'tool' in roles
        assert roles.count('tool') == 1
        assert 'assistant' in roles

    def test_yield_llm_stream_does_not_pass_tools_to_client(self, monkeypatch):
        """_yield_llm_stream 不应将 tools 参数传递给 OpenAI client"""
        service = AssistantService()

        captured = {}

        class MockStream:
            def __iter__(self):
                return iter([])

        def mock_create(*, model, messages, temperature, max_tokens, stream, timeout, tools=None):
            captured['tools'] = tools
            return MockStream()

        class FakeClient:
            pass
        fake_client = FakeClient()
        fake_client.chat = FakeClient()
        fake_client.chat.completions = FakeClient()
        fake_client.chat.completions.create = mock_create

        monkeypatch.setattr(service, 'client', fake_client)
        import services.assistant_service as svc_module
        monkeypatch.setattr(svc_module, 'HAS_OPENAI', True)

        list(service._yield_llm_stream([{"role": "user", "content": "test"}]))

        assert captured.get('tools') is None

    def test_bash_run_executes_allowed_cli_command(self, test_db, monkeypatch):
        """bash_run 应执行允许的 CLI 命令并返回输出"""
        class FakeResult:
            returncode = 0
            stdout = '{"success": true}'
            stderr = ''

        def mock_run(*args, **kwargs):
            return FakeResult()

        monkeypatch.setattr(subprocess, 'run', mock_run)
        result = exec_bash_command(test_db, 'python3 -m src.cli stats')
        assert result['success'] is True
        assert result['stdout'] == '{"success": true}'

    def test_bash_run_rejects_unallowed_command(self, test_db):
        """bash_run 应拒绝未允许的命令"""
        result = exec_bash_command(test_db, 'rm -rf /')
        assert result['success'] is False
        assert 'src/cli/commands.py' in result['error']

    def test_system_prompt_contains_tool_call_instruction(self):
        """系统提示词中应包含 TOOL_CALL 指令"""
        service = AssistantService()
        prompt = service.system_prompt
        assert 'TOOL_CALL:' in prompt
        assert 'bash_run' in prompt

    def test_tool_call_record_arguments_are_parsed_json_not_coerced(self, test_db, monkeypatch):
        """tool_call_record 中保存的 arguments 应为模型返回的原始 JSON 解析值（未经 coerce）"""
        service = AssistantService()

        def mock_yield_llm_stream(messages):
            text = 'TOOL_CALL: {"function": "bash_run", "arguments": {"command": "python3 -m src.cli stats --year 2025"}}'
            yield {"type": "delta", "content": text}
            return text, {"role": "assistant", "content": text}

        monkeypatch.setattr(service, '_yield_llm_stream', mock_yield_llm_stream)
        monkeypatch.setattr(service, '_execute_tool', lambda fn, args, db: {"success": True, "stdout": ""})

        messages = [{"role": "user", "content": "查询"}]
        events = list(service.chat_stream(messages, test_db))

        tool_call_event = [e for e in events if e.get('type') == 'tool_call_record'][0]
        assert tool_call_event['arguments']['command'] == 'python3 -m src.cli stats --year 2025'

        done_events = [e for e in events if e.get('type') == 'done']
        final_messages = done_events[0]['messages']
        tool_call_msg = [m for m in final_messages if m.get('role') == 'tool_call'][0]
        assert tool_call_msg['arguments']['command'] == 'python3 -m src.cli stats --year 2025'


class TestParseToolCallHelpers:
    """测试文本解析辅助函数"""

    def test_parse_tool_call_extracts_payload(self):
        text = '思考中...\nTOOL_CALL: {"function": "bash_run", "arguments": {"command": "ls"}}'
        result = _parse_tool_call(text)
        assert result == {"function": "bash_run", "arguments": {"command": "ls"}}

    def test_parse_tool_call_returns_none_when_missing(self):
        assert _parse_tool_call('普通回复') is None

    def test_strip_tool_call_removes_marker(self):
        text = '思考中...\nTOOL_CALL: {"function": "bash_run"}'
        assert _strip_tool_call(text) == '思考中...'

    def test_strip_tool_call_keeps_text_when_missing(self):
        assert _strip_tool_call('普通回复') == '普通回复'
