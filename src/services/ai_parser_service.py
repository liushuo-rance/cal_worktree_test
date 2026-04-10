"""
AI大模型解析服务
使用火山方舟API解析加班记录文本
"""

import os
import json
import re
from datetime import date
from typing import List, Dict, Any, Optional

# 尝试导入openai库
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    import requests


class AIParserService:
    """AI解析服务"""

    def __init__(self):
        # 硬编码火山方舟API配置
        self.api_key = "39fb2f6b-3062-41f7-8abb-3e879f03270b"
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.model = "ep-20260331092634-wfnm8"

        if HAS_OPENAI:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        else:
            self.client = None

    def _build_prompt(self, text_lines: List[str]) -> str:
        """构建解析提示词"""
        lines_text = "\n".join([f"{i+1}. {line}" for i, line in enumerate(text_lines)])

        return f"""你是一个加班记录解析助手。请解析以下文本中的每一行，提取日期、类型、时长等信息。

待解析的文本行：
{lines_text}

请对每一行进行分析，返回JSON数组格式：
[
  {{
    "line_num": 1,
    "date": "2024-01-15",
    "type": "overtime|leave|comp_off|unknown",
    "subtype": "weekday_evening|weekday_morning|weekday_lunch|weekend|holiday|personal|sick|annual|half_day|full_day",
    "hours": 2.0,
    "description": "描述文本",
    "confidence": 0.95,
    "reasoning": "解析理由"
  }}
]

解析规则：
1. 日期范围展开：如果一行文本包含日期范围（如"2025.10.27-29"）且描述对应多天（如"请假三天"），请为范围内的每一天返回一条独立记录，日期依次递增。例如"2025.10.27-29，请假三天"应返回3条记录，日期分别为2025-10-27、2025-10-28、2025-10-29。

2. type字段：
   - "overtime": 加班（包括"晚上xx小时"、"下午xx小时"、"加班"、"到岗"、"学习奖励xx小时"等）
   - "leave": 请假（包括"请假"、"病假"、"事假"等）
   - "comp_off": 调休（包括"调休"、"补休"等）
   - "unknown": 无法识别类型

3. subtype字段：
   加班类型：weekday_morning(早上)、weekday_lunch(午休)、weekday_evening(晚上)、weekday_mixed(全天)、weekend(周末)、holiday(法定节假日)
   请假类型：personal(事假)、sick(病假)、annual(年假)、marriage(婚假)、maternity(产假)、bereavement(丧假)
   调休类型：half_day(半天)、full_day(全天)

4. 特殊处理：
   - "到岗"视为加班，subtype为weekday_morning，hours为3.5（如未明确时长）
   - "学习奖励xx小时"视为加班，提取"xx"作为hours，subtype为weekday_mixed
   - "下午xx小时"、"晚上xx小时"默认为加班，subtype为weekday_evening
   - "请假半天"默认为leave，subtype为personal，hours为4
   - "请假一天"默认为leave，subtype为personal，hours为8
   - 只包含"累计"、"余额"字样的行标记为unknown

5. hours字段：
   - 提取数字部分，转换为小时（如"2小时"=2.0，"半天"=4.0，"一天"=8.0）
   - 如果无法提取，设为null

5. confidence字段：
   - 0.9-1.0: 非常确定
   - 0.7-0.9: 比较确定
   - 0.5-0.7: 不太确定
   - 0.0-0.5: 无法识别

请只返回JSON数组，不要返回其他内容。"""

    def parse_lines(self, text_lines: List[str], progress_callback=None) -> Dict[str, Any]:
        """
        使用AI解析文本行，分批处理避免超时

        Args:
            text_lines: 文本行列表
            progress_callback: 可选的进度回调函数，签名 progress_callback(current: int, total: int)

        Returns:
            包含解析结果、prompt、response的字典
        """
        if not text_lines:
            return {
                'records': [],
                'prompt': '',
                'response': '',
                'error': '没有要解析的文本行'
            }

        # 每批处理15行，平衡API响应速度和进度条更新频率
        BATCH_SIZE = 15
        all_results = []
        all_responses = []
        total_batches = (len(text_lines) + BATCH_SIZE - 1) // BATCH_SIZE

        full_prompt = self._build_prompt(text_lines)

        for batch_idx, batch_start in enumerate(range(0, len(text_lines), BATCH_SIZE)):
            batch_end = min(batch_start + BATCH_SIZE, len(text_lines))
            batch_lines = text_lines[batch_start:batch_end]

            print(f"[AI Parser] 处理批次 {batch_idx + 1}/{total_batches}, 行 {batch_start+1}-{batch_end}")

            if progress_callback:
                progress_callback(batch_idx + 1, total_batches)

            batch_result = self._parse_batch(batch_lines, batch_start)

            if batch_result.get('error'):
                return {
                    'records': [],
                    'prompt': full_prompt,
                    'response': '\n'.join(all_responses) + f"\n[批次错误] {batch_result['error']}",
                    'error': batch_result['error']
                }

            all_results.extend(batch_result.get('records', []))
            all_responses.append(batch_result.get('response', ''))

        return {
            'records': all_results,
            'prompt': full_prompt,
            'response': '\n---\n'.join(all_responses),
            'error': None
        }

    def _parse_batch(self, text_lines: List[str], line_offset: int = 0) -> Dict[str, Any]:
        """
        解析一批文本行

        Args:
            text_lines: 文本行列表
            line_offset: 行号偏移量

        Returns:
            包含解析结果、prompt、response的字典
        """
        prompt = self._build_prompt(text_lines)
        content = ''  # 初始化content变量

        try:
            if HAS_OPENAI and self.client:
                # 使用OpenAI SDK调用火山方舟API
                print(f"[AI Parser] 使用OpenAI SDK调用火山方舟API")
                print(f"[AI Parser] Model: {self.model}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的加班记录解析助手，擅长从非结构化文本中提取时间、类型、时长等信息。请严格返回JSON格式。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1,
                    max_tokens=4000,
                    timeout=300,
                )

                # 提取响应内容
                content = response.choices[0].message.content
                print(f"[AI Parser] Response received, content length: {len(content)}")
                print(f"[AI Parser] Content preview: {content[:200]}...")

            else:
                # 使用requests直接调用API
                print(f"[AI Parser] 使用requests调用火山方舟API")

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个专业的加班记录解析助手，擅长从非结构化文本中提取时间、类型、时长等信息。请严格返回JSON格式。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                }

                api_response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=300
                )
                api_response.raise_for_status()
                data = api_response.json()

                print(f"[AI Parser] API Response status: {api_response.status_code}")
                print(f"[AI Parser] Response keys: {data.keys() if isinstance(data, dict) else 'not dict'}")

                content = data["choices"][0]["message"]["content"]
                print(f"[AI Parser] Extracted content length: {len(content)}")
                print(f"[AI Parser] Content preview: {content[:200]}...")

            # 解析JSON响应
            # 提取JSON部分（AI可能在JSON前后添加文字）
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                json_content = json_match.group(0)
            else:
                json_content = content

            try:
                parsed_results = json.loads(json_content)
            except json.JSONDecodeError as e:
                return {
                    'records': [],
                    'prompt': prompt,
                    'response': content,
                    'error': f'JSON解析失败: {str(e)}'
                }

            # 转换AI结果为内部格式
            results = []
            for i, result in enumerate(parsed_results):
                # 行号加上偏移量
                batch_line_num = result.get('line_num', i + 1)
                actual_line_num = batch_line_num + line_offset
                parsed_date = result.get('date')

                record = {
                    'line_num': actual_line_num,
                    'raw_line': text_lines[batch_line_num - 1] if batch_line_num <= len(text_lines) else '',
                    'parsed_date': parsed_date,
                    'date_str': parsed_date,
                    'weekday': self._get_weekday(parsed_date),
                    'type': result.get('type', 'unknown'),
                    'overtime_type': result.get('subtype') if result.get('type') == 'overtime' else None,
                    'leave_type': result.get('subtype') if result.get('type') == 'leave' else None,
                    'parsed_hours': result.get('hours'),
                    'content': result.get('description', ''),
                    'confidence': result.get('confidence', 0.5),
                    'reasoning': result.get('reasoning', ''),
                    'ai_parsed': True
                }
                results.append(record)

            return {
                'records': results,
                'prompt': prompt,
                'response': content,
                'error': None
            }

        except Exception as e:
            error_msg = f"AI解析失败: {str(e)}"
            print(f"[AI Parser Error] {error_msg}")
            print(f"[AI Parser Response Content] {content[:500] if content else '(empty)'}")
            import traceback
            print(f"[AI Parser Traceback] {traceback.format_exc()}")
            return {
                'records': [],
                'prompt': prompt,
                'response': content if content else f'[API调用异常] {str(e)}',
                'error': error_msg
            }

    def _get_weekday(self, date_str: Optional[str]) -> Optional[str]:
        """根据日期字符串获取星期几"""
        if not date_str:
            return None
        try:
            d = date.fromisoformat(date_str)
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            return weekdays[d.weekday()]
        except:
            return None


# 全局实例
_ai_parser = None


def get_ai_parser() -> AIParserService:
    """获取AI解析服务实例"""
    global _ai_parser
    if _ai_parser is None:
        _ai_parser = AIParserService()
    return _ai_parser


def parse_with_ai(text_lines: List[str], progress_callback=None) -> Dict[str, Any]:
    """
    使用AI解析文本行的便捷函数

    Args:
        text_lines: 文本行列表
        progress_callback: 可选的进度回调函数，签名 progress_callback(current: int, total: int)

    Returns:
        包含解析结果、prompt、response的字典
    """
    # 先构建prompt，即使后续失败也能显示给用户
    lines_text = "\n".join([f"{i+1}. {line}" for i, line in enumerate(text_lines)])
    prompt = f"""你是一个加班记录解析助手。请解析以下文本中的每一行，提取日期、类型、时长等信息。

待解析的文本行：
{lines_text}

请对每一行进行分析，返回JSON数组格式..."""

    try:
        parser = get_ai_parser()
        return parser.parse_lines(text_lines, progress_callback=progress_callback)
    except Exception as e:
        error_msg = f"AI解析服务初始化失败: {e}"
        print(error_msg)
        return {
            'records': [],
            'prompt': prompt,
            'response': f'服务初始化错误: {str(e)}',
            'error': error_msg
        }
