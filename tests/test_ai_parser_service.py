"""
AI解析服务测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestAIParserServiceLineLimit:
    """测试AI解析行数限制"""

    def test_parse_lines_processes_all_lines_no_5_line_limit(self, monkeypatch):
        """parse_lines 不应该硬限制为只处理前5行"""
        from services.ai_parser_service import AIParserService

        service = AIParserService()
        text_lines = [f"2024-01-{i:02d} 晚上加班2小时" for i in range(1, 11)]

        call_count = 0

        def mock_parse_batch(self, batch_lines, line_offset=0):
            nonlocal call_count
            call_count += 1
            return {
                'records': [
                    {
                        'line_num': line_offset + 1 + j,
                        'parsed_date': f'2024-01-{line_offset + 1 + j:02d}',
                        'type': 'overtime',
                        'confidence': 0.95
                    }
                    for j in range(len(batch_lines))
                ],
                'prompt': 'mock',
                'response': 'mock',
                'error': None
            }

        monkeypatch.setattr(AIParserService, '_parse_batch', mock_parse_batch)

        result = service.parse_lines(text_lines)

        assert len(result['records']) == 10, f"期望解析10行，实际只解析了{len(result['records'])}行"
        assert call_count == 2, f"期望10行调用2次批次解析（batch_size=5），实际调用了{call_count}次"

    def test_parse_lines_90_lines_sends_18_batches(self, monkeypatch):
        """90 行数据应分 18 个 batch 发送（batch_size=5）"""
        from services.ai_parser_service import AIParserService

        service = AIParserService()
        text_lines = [f"2024-01-{i:02d} 晚上加班2小时" for i in range(1, 91)]

        call_count = 0

        def mock_parse_batch(self, batch_lines, line_offset=0):
            nonlocal call_count
            call_count += 1
            return {
                'records': [
                    {
                        'line_num': line_offset + 1 + j,
                        'parsed_date': f'2024-01-{line_offset + 1 + j:02d}',
                        'type': 'overtime',
                        'confidence': 0.95
                    }
                    for j in range(len(batch_lines))
                ],
                'prompt': 'mock',
                'response': 'mock',
                'error': None
            }

        monkeypatch.setattr(AIParserService, '_parse_batch', mock_parse_batch)

        result = service.parse_lines(text_lines)

        assert len(result['records']) == 90, f"期望解析90行，实际只解析了{len(result['records'])}行"
        assert call_count == 18, f"期望90行调用18次批次解析（batch_size=5），实际调用了{call_count}次"

    def test_parse_lines_51_lines_sends_11_batches(self, monkeypatch):
        """51 行数据应分 11 个 batch 发送（batch_size=5）"""
        from services.ai_parser_service import AIParserService

        service = AIParserService()
        text_lines = [f"2024-01-{i:02d} 晚上加班2小时" for i in range(1, 52)]

        call_count = 0

        def mock_parse_batch(self, batch_lines, line_offset=0):
            nonlocal call_count
            call_count += 1
            return {
                'records': [
                    {
                        'line_num': line_offset + 1 + j,
                        'parsed_date': f'2024-01-{line_offset + 1 + j:02d}',
                        'type': 'overtime',
                        'confidence': 0.95
                    }
                    for j in range(len(batch_lines))
                ],
                'prompt': 'mock',
                'response': 'mock',
                'error': None
            }

        monkeypatch.setattr(AIParserService, '_parse_batch', mock_parse_batch)

        result = service.parse_lines(text_lines)

        assert len(result['records']) == 51, f"期望解析51行，实际只解析了{len(result['records'])}行"
        assert call_count == 11, f"期望51行调用11次批次解析（batch_size=5），实际调用了{call_count}次"


class TestAIParserServiceSubtypeMapping:
    """测试 overtime_type 非法值会被映射到合法值"""

    def test_weekday_mixed_mapped_to_weekday_evening(self, monkeypatch):
        """AI 返回 weekday_mixed 时应映射为 weekday_evening"""
        from services.ai_parser_service import AIParserService

        service = AIParserService()

        def mock_parse_batch(self, batch_lines, line_offset=0):
            return {
                'records': [
                    {
                        'line_num': 1,
                        'date': '2024-01-15',
                        'type': 'overtime',
                        'subtype': 'weekday_mixed',
                        'hours': 8.0,
                        'description': '全天加班',
                        'confidence': 0.9,
                        'reasoning': 'mock'
                    }
                ],
                'prompt': 'mock',
                'response': 'mock',
                'error': None
            }

        monkeypatch.setattr(AIParserService, '_parse_batch', mock_parse_batch)

        result = service.parse_lines(['全天加班8小时'])
        record = result['records'][0]
        assert record['overtime_type'] == 'weekday_evening', (
            f"weekday_mixed 应被映射为 weekday_evening，实际为 {record['overtime_type']}"
        )

    def test_invalid_overtime_type_mapped_to_weekday_evening(self, monkeypatch):
        """AI 返回未知 overtime_type 时应映射为 weekday_evening"""
        from services.ai_parser_service import AIParserService

        service = AIParserService()

        def mock_parse_batch(self, batch_lines, line_offset=0):
            return {
                'records': [
                    {
                        'line_num': 1,
                        'date': '2024-01-15',
                        'type': 'overtime',
                        'subtype': 'unknown_subtype',
                        'hours': 2.0,
                        'description': '加班',
                        'confidence': 0.9,
                        'reasoning': 'mock'
                    }
                ],
                'prompt': 'mock',
                'response': 'mock',
                'error': None
            }

        monkeypatch.setattr(AIParserService, '_parse_batch', mock_parse_batch)

        result = service.parse_lines(['加班2小时'])
        record = result['records'][0]
        assert record['overtime_type'] == 'weekday_evening', (
            f"非法 overtime_type 应被映射为 weekday_evening，实际为 {record['overtime_type']}"
        )
