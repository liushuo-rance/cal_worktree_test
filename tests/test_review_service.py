"""
审批会话管理服务测试
测试内容:
1. 逐条确认界面逻辑
2. 批量确认/拒绝
3. 导入报告生成
"""

import pytest
import sqlite3


@pytest.fixture
def memory_db():
    """内存数据库，带完整Schema"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE review_queue (
            id INTEGER PRIMARY KEY,
            import_session_id INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            parsed_type TEXT,
            parsed_date TEXT,
            parsed_hours REAL,
            parsed_minutes INTEGER,
            confidence_level TEXT,
            confidence_score REAL,
            anomalies TEXT,
            status TEXT DEFAULT 'pending',
            reviewer_note TEXT,
            reviewed_at TIMESTAMP
        );

        CREATE TABLE import_sessions (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_name TEXT,
            total_records INTEGER DEFAULT 0,
            success_records INTEGER DEFAULT 0,
            failed_records INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending'
        );

        INSERT INTO import_sessions (id, employee_id, file_name, status) VALUES
            (1, 'EMP001', 'test1.md', 'pending'),
            (2, 'EMP001', 'test2.md', 'reviewing');

        INSERT INTO review_queue (id, import_session_id, raw_text, parsed_type,
            parsed_date, parsed_hours, confidence_level, confidence_score, status) VALUES
            (1, 1, '2026.1.15 晚上3.5小时', 'overtime', '2026-01-15', 3.5, 'HIGH', 0.95, 'pending'),
            (2, 1, '2026.1.16 请假半天', 'leave', '2026-01-16', 4.0, 'HIGH', 0.92, 'pending'),
            (3, 1, 'xxx 加班', 'unknown', NULL, NULL, 'LOW', 0.3, 'pending'),
            (4, 1, '2026.1.17 加班15小时', 'overtime', '2026-01-17', 15.0, 'MEDIUM', 0.7, 'pending');
    """)
    conn.commit()
    yield conn
    conn.close()


class TestReviewQueueOperations:
    """审批队列操作测试"""

    def test_get_pending_reviews(self, memory_db):
        from src.services.review_service import get_pending_reviews

        reviews = get_pending_reviews(memory_db, session_id=1)

        assert len(reviews) == 4
        assert all(r['status'] == 'pending' for r in reviews)

    def test_get_next_pending_review(self, memory_db):
        from src.services.review_service import get_next_pending_review

        review = get_next_pending_review(memory_db, session_id=1)

        assert review is not None
        assert review['status'] == 'pending'

    def test_get_review_by_id(self, memory_db):
        from src.services.review_service import get_review_by_id

        review = get_review_by_id(memory_db, review_id=1)

        assert review is not None
        assert review['id'] == 1
        assert review['raw_text'] == '2026.1.15 晚上3.5小时'


class TestApproveReview:
    """审批通过测试"""

    def test_approve_high_confidence(self, memory_db):
        from src.services.review_service import approve_review

        result = approve_review(memory_db, review_id=1, reviewer_note='确认无误')

        assert result['success'] is True

        cursor = memory_db.cursor()
        cursor.execute("SELECT status, reviewer_note FROM review_queue WHERE id = 1")
        row = cursor.fetchone()
        assert row['status'] == 'approved'
        assert row['reviewer_note'] == '确认无误'

    def test_approve_with_modifications(self, memory_db):
        from src.services.review_service import approve_review

        result = approve_review(
            memory_db,
            review_id=4,
            modifications={'hours': 8.0, 'note': '修正异常时长'},
            reviewer_note='已修正为8小时'
        )

        assert result['success'] is True

        cursor = memory_db.cursor()
        cursor.execute("SELECT parsed_hours, status FROM review_queue WHERE id = 4")
        row = cursor.fetchone()
        assert row['parsed_hours'] == 8.0
        assert row['status'] == 'approved'

    def test_approve_nonexistent_review(self, memory_db):
        from src.services.review_service import approve_review, ReviewServiceError

        with pytest.raises(ReviewServiceError):
            approve_review(memory_db, review_id=999)


class TestRejectReview:
    """审批拒绝测试"""

    def test_reject_review(self, memory_db):
        from src.services.review_service import reject_review

        result = reject_review(
            memory_db,
            review_id=3,
            reason='无法识别的记录'
        )

        assert result['success'] is True

        cursor = memory_db.cursor()
        cursor.execute("SELECT status, reviewer_note FROM review_queue WHERE id = 3")
        row = cursor.fetchone()
        assert row['status'] == 'rejected'
        assert '无法识别' in row['reviewer_note']

    def test_reject_already_processed(self, memory_db):
        from src.services.review_service import reject_review, ReviewServiceError

        # 先通过一条记录
        from src.services.review_service import approve_review
        approve_review(memory_db, review_id=1)

        # 再拒绝同一条
        with pytest.raises(ReviewServiceError):
            reject_review(memory_db, review_id=1, reason='测试')


class TestBatchReview:
    """批量审批测试"""

    def test_batch_approve(self, memory_db):
        from src.services.review_service import batch_approve

        # 批量审批高置信度记录
        result = batch_approve(
            memory_db,
            review_ids=[1, 2],
            reviewer_note='批量确认'
        )

        assert result['success_count'] == 2

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'approved'")
        assert cursor.fetchone()[0] == 2

    def test_batch_reject(self, memory_db):
        from src.services.review_service import batch_reject

        result = batch_reject(
            memory_db,
            review_ids=[3, 4],
            reason='批量拒绝'
        )

        assert result['success_count'] == 2

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'rejected'")
        assert cursor.fetchone()[0] == 2

    def test_batch_approve_all_high_confidence(self, memory_db):
        from src.services.review_service import batch_approve_high_confidence

        result = batch_approve_high_confidence(memory_db, session_id=1)

        # 应该自动通过两条HIGH置信度的
        assert result['success_count'] == 2

        cursor = memory_db.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM review_queue
            WHERE status = 'approved' AND confidence_level = 'HIGH'
        """)
        assert cursor.fetchone()[0] == 2


class TestImportReport:
    """导入报告测试"""

    def test_generate_import_report(self, memory_db):
        from src.services.review_service import generate_import_report

        # 先处理一些记录
        from src.services.review_service import approve_review, reject_review
        approve_review(memory_db, review_id=1)
        approve_review(memory_db, review_id=2)
        reject_review(memory_db, review_id=3, reason='无效')

        report = generate_import_report(memory_db, session_id=1)

        assert report['session_id'] == 1
        assert report['total_records'] == 4
        assert report['approved_count'] == 2
        assert report['rejected_count'] == 1
        assert report['pending_count'] == 1

    def test_generate_detailed_report(self, memory_db):
        from src.services.review_service import generate_detailed_report

        from src.services.review_service import approve_review, reject_review
        approve_review(memory_db, review_id=1, reviewer_note='OK')
        reject_review(memory_db, review_id=3, reason='无效')

        report = generate_detailed_report(memory_db, session_id=1)

        assert 'approved_records' in report
        assert 'rejected_records' in report
        assert 'pending_records' in report
        assert len(report['approved_records']) == 1
        assert len(report['rejected_records']) == 1
        assert len(report['pending_records']) == 2


class TestReviewSession:
    """审批会话测试"""

    def test_start_review_session(self, memory_db):
        from src.services.review_service import start_review_session

        result = start_review_session(memory_db, session_id=1)

        assert result['success'] is True

        cursor = memory_db.cursor()
        cursor.execute("SELECT status FROM import_sessions WHERE id = 1")
        assert cursor.fetchone()['status'] == 'reviewing'

    def test_complete_review_session(self, memory_db):
        from src.services.review_service import complete_review_session

        # 先处理完所有记录
        from src.services.review_service import approve_review, reject_review
        approve_review(memory_db, review_id=1)
        approve_review(memory_db, review_id=2)
        reject_review(memory_db, review_id=3, reason='无效')
        reject_review(memory_db, review_id=4, reason='异常')

        result = complete_review_session(memory_db, session_id=1)

        assert result['success'] is True

        cursor = memory_db.cursor()
        cursor.execute("SELECT status FROM import_sessions WHERE id = 1")
        assert cursor.fetchone()['status'] == 'completed'

    def test_cannot_complete_with_pending(self, memory_db):
        from src.services.review_service import complete_review_session, ReviewServiceError

        # 有未处理的记录
        with pytest.raises(ReviewServiceError):
            complete_review_session(memory_db, session_id=1)


class TestReviewStatistics:
    """审批统计测试"""

    def test_get_review_statistics(self, memory_db):
        from src.services.review_service import get_review_statistics

        from src.services.review_service import approve_review, reject_review
        approve_review(memory_db, review_id=1)
        approve_review(memory_db, review_id=2)
        reject_review(memory_db, review_id=3, reason='无效')

        stats = get_review_statistics(memory_db, session_id=1)

        assert stats['total'] == 4
        assert stats['approved'] == 2
        assert stats['rejected'] == 1
        assert stats['pending'] == 1
        assert stats['approval_rate'] == 0.5  # 2/4

    def test_get_confidence_distribution(self, memory_db):
        from src.services.review_service import get_confidence_distribution

        dist = get_confidence_distribution(memory_db, session_id=1)

        assert dist['HIGH'] == 2
        assert dist['MEDIUM'] == 1
        assert dist['LOW'] == 1
