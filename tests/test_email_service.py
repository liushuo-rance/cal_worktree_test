"""
邮件服务测试
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEmailService:
    """邮件服务测试"""

    def test_build_email_config_from_env(self):
        """应从环境变量构建邮件配置"""
        from src.services.email_service import build_email_config

        env = {
            'SMTP_HOST': 'smtp.example.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@example.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@example.com',
            'HR_NOTIFICATION_EMAIL': 'hr@example.com,admin@example.com'
        }

        config = build_email_config(env)
        assert config['host'] == 'smtp.example.com'
        assert config['port'] == 587
        assert config['user'] == 'user@example.com'
        assert config['password'] == 'secret'
        assert config['from_addr'] == 'noreply@example.com'
        assert config['hr_emails'] == ['hr@example.com', 'admin@example.com']

    def test_build_email_config_missing(self):
        """关键配置缺失时应返回不完整标记"""
        from src.services.email_service import build_email_config

        config = build_email_config({})
        assert config['is_configured'] is False

    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp_class):
        """发送邮件成功"""
        from src.services.email_service import send_email

        mock_smtp_instance = mock_smtp_class.return_value
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)

        result = send_email(
            to='hr@example.com',
            subject='Test Subject',
            html_body='<h1>Test</h1>',
            smtp_host='smtp.example.com',
            smtp_port=587,
            smtp_user='user@example.com',
            smtp_password='secret',
            from_addr='noreply@example.com'
        )

        assert result['success'] is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with('user@example.com', 'secret')
        mock_smtp_instance.send_message.assert_called_once()
