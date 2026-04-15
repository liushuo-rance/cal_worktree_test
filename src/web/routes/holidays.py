"""
节假日管理路由
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
import sqlite3
import logging
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from parsers.holiday_notification_parser import parse_notification
from web.decorators import admin_required

bp = Blueprint('holidays', __name__, url_prefix='/holidays')
logger = logging.getLogger(__name__)


def get_db():
    """获取数据库连接"""
    db_path = current_app.config['DATABASE']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@bp.route('/')
@admin_required
def list_holidays():
    """节假日列表"""
    conn = get_db()
    cursor = conn.cursor()

    holidays = []
    year = request.args.get('year', datetime.now().year, type=int)

    # 获取所有可用年份（按降序排列，最新的年份在前）
    available_years = []
    try:
        cursor.execute("SELECT DISTINCT year FROM holiday_config ORDER BY year DESC")
        available_years = [row['year'] for row in cursor.fetchall()]
        logger.info(f"可用年份: {available_years}")
    except sqlite3.Error as e:
        logger.error(f"查询可用年份失败: {e}")

    # 如果当前年份不在列表中，添加它
    current_year = datetime.now().year
    if current_year not in available_years:
        available_years.insert(0, current_year)

    try:
        cursor.execute("""
            SELECT * FROM holiday_config
            WHERE year = ?
            ORDER BY holiday_date
        """, (year,))
        holidays = [dict(row) for row in cursor.fetchall()]
        logger.info(f"查询到 {len(holidays)} 条节假日记录 (年份: {year})")
    except sqlite3.Error as e:
        logger.error(f"查询节假日失败: {e}")
        flash('查询节假日失败', 'error')
    finally:
        conn.close()

    return render_template('holidays.html', holidays=holidays, year=year,
                         available_years=available_years)


@bp.route('/import/', methods=['GET', 'POST'])
@admin_required
def import_holidays():
    """导入节假日"""
    if request.method == 'POST':
        text = request.form.get('holiday_text', '').strip()

        logger.info(f"收到节假日导入请求，文本长度: {len(text)}")

        if not text:
            logger.warning("导入失败: 文本为空")
            flash('请输入节假日文本', 'error')
            return redirect(url_for('holidays.import_holidays'))

        try:
            # 解析节假日通知
            logger.debug("开始解析节假日文本...")
            parsed_holidays = parse_notification(text)
            logger.info(f"解析到 {len(parsed_holidays)} 个节假日条目")

            if not parsed_holidays:
                logger.warning("未解析到任何节假日信息")
                flash('未能从文本中解析出节假日信息，请检查格式', 'error')
                return redirect(url_for('holidays.import_holidays'))

            # 保存到数据库
            conn = get_db()
            cursor = conn.cursor()

            success_count = 0
            error_count = 0

            for holiday in parsed_holidays:
                try:
                    name = holiday['name']
                    year = holiday['start_date'].year
                    start_date = holiday['start_date']
                    end_date = holiday['end_date']
                    statutory_days = holiday.get('statutory_days', [])
                    adjusted_workdays = holiday.get('adjusted_workdays', [])

                    logger.debug(f"处理节假日: {name}, 日期范围: {start_date} 至 {end_date}")

                    # 删除同一年该节假日的旧数据
                    cursor.execute("""
                        DELETE FROM holiday_config
                        WHERE holiday_name = ? AND year = ?
                    """, (name, year))

                    # 插入假期每一天
                    current_date = start_date
                    while current_date <= end_date:
                        if current_date in statutory_days:
                            holiday_type = 'statutory'  # 法定节假日
                        else:
                            holiday_type = 'adjusted_holiday'  # 调休假期

                        cursor.execute("""
                            INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
                            VALUES (?, ?, ?, ?)
                        """, (current_date, name, holiday_type, year))
                        success_count += 1
                        current_date = datetime.fromordinal(current_date.toordinal() + 1).date()

                    # 插入调休上班日
                    for workday in adjusted_workdays:
                        cursor.execute("""
                            INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
                            VALUES (?, ?, ?, ?)
                        """, (workday, f"{name}调休", 'adjusted_workday', year))
                        success_count += 1

                    logger.info(f"节假日 '{name}' 导入成功")

                except Exception as e:
                    error_count += 1
                    logger.error(f"处理节假日失败: {e}", exc_info=True)

            conn.commit()
            conn.close()

            if success_count > 0:
                logger.info(f"节假日导入完成: 成功 {success_count} 条, 失败 {error_count} 条")
                flash(f'节假日导入完成: 成功 {success_count} 条, 失败 {error_count} 条', 'success')
            else:
                logger.warning("节假日导入失败: 没有成功导入任何记录")
                flash('导入失败，请检查文本格式', 'error')

        except Exception as e:
            logger.error(f"节假日导入异常: {e}", exc_info=True)
            flash(f'导入失败: {str(e)}', 'error')

        return redirect(url_for('holidays.list_holidays'))

    return render_template('import_holidays.html')


@bp.route('/delete/<date>', methods=['POST'])
@admin_required
def delete_holiday(date):
    """删除指定日期的节假日"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM holiday_config WHERE holiday_date = ?",
            (date,)
        )
        conn.commit()

        if cursor.rowcount > 0:
            logger.info(f"删除节假日成功: {date}")
            flash(f'已删除 {date} 的节假日记录', 'success')
        else:
            logger.warning(f"删除节假日失败: 未找到 {date}")
            flash('未找到该日期的节假日记录', 'warning')
    except sqlite3.Error as e:
        logger.error(f"删除节假日失败: {e}")
        flash('删除失败', 'error')
    finally:
        conn.close()

    # 获取当前年份参数，保持页面状态
    year = request.args.get('year', datetime.now().year, type=int)
    return redirect(url_for('holidays.list_holidays', year=year))


@bp.route('/delete-year/<int:year>', methods=['POST'])
@admin_required
def delete_year_holidays(year):
    """删除指定年份的所有节假日"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM holiday_config WHERE year = ?",
            (year,)
        )
        conn.commit()

        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.info(f"删除 {year} 年节假日成功，共 {deleted_count} 条")
            flash(f'已删除 {year} 年的 {deleted_count} 条节假日记录', 'success')
        else:
            logger.warning(f"删除 {year} 年节假日: 无数据")
            flash(f'{year} 年没有节假日数据', 'warning')
    except sqlite3.Error as e:
        logger.error(f"删除 {year} 年节假日失败: {e}")
        flash('删除失败', 'error')
    finally:
        conn.close()

    return redirect(url_for('holidays.list_holidays'))
