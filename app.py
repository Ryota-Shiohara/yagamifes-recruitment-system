#!/usr/keio/Anaconda3-2025.12-2/bin/python
"""矢上祭実行委員会の新規局員採用を題材にしたDB Webアプリ。"""

import sqlite3
from datetime import datetime
from functools import wraps
from typing import Final, Optional
import unicodedata

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug import Response


DATABASE = 'database.db'
MAX_NAME_LENGTH: Final[int] = 80
MAX_EMAIL_LENGTH: Final[int] = 254
MAX_REMARK_LENGTH: Final[int] = 500
MAX_CRITERION_NAME_LENGTH: Final[int] = 80
MAX_CRITERION_DESCRIPTION_LENGTH: Final[int] = 500
DECISION_LABELS: Final[dict[Optional[str], str]] = {
    None: '未決定',
    'accepted': '採用',
    'rejected': '不採用',
    'waitlisted': '保留',
    'withdrawn': '辞退',
}

ROLE_LABELS: Final[dict[str, str]] = {
    'applicant': '応募者',
    'interviewer': '面接官',
    'bureau_manager': '局責任者',
}
ROLE_HOME_ENDPOINTS: Final[dict[str, str]] = {
    'applicant': 'applicant_home',
    'interviewer': 'interviewer_home',
    'bureau_manager': 'bureau_manager_home',
}
ROLE_PATH_PREFIXES: Final[dict[str, str]] = {
    'applicant': '/applicant',
    'interviewer': '/interviewer',
    'bureau_manager': '/manager',
}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
# 認証用ではなく、入口で選択した画面区分をリクエスト間で保持するためだけに使う。
app.config['SECRET_KEY'] = 'yagamifes-role-selection-demo'


@app.context_processor
def inject_role_context() -> dict[str, object]:
    """テンプレートへ現在の画面区分を渡す。"""
    active_role = session.get('active_role')
    return {
        'current_role': active_role if active_role in ROLE_LABELS else None,
        'role_labels': ROLE_LABELS,
    }


def role_required(role: str):
    """選択中の役割と異なる画面へ入らないようにする。

    認証・認可ではなく、入口で選んだ画面導線を分離するためのガードである。
    既存URLは移行互換のため、役割未選択時だけ引き続き利用できる。
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            active_role = session.get('active_role')
            role_prefix = ROLE_PATH_PREFIXES[role]
            is_role_path = (
                request.path == role_prefix
                or request.path.startswith(role_prefix + '/')
            )
            if active_role == role:
                return view(*args, **kwargs)
            if active_role is None and not is_role_path:
                # 既存の未プレフィックスURLを、古いブックマークやテスト用に残す。
                return view(*args, **kwargs)
            if active_role in ROLE_HOME_ENDPOINTS:
                return redirect(url_for(ROLE_HOME_ENDPOINTS[active_role]))
            return redirect(url_for('index'))
        return wrapped
    return decorator


def get_db() -> sqlite3.Connection:
    """リクエスト中で共有するSQLite接続を返す。"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('PRAGMA busy_timeout = 3000')
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception: Optional[BaseException]) -> None:
    """リクエスト終了時にSQLite接続を閉じる。"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def has_control_character(value: str) -> bool:
    """文字列に制御文字が含まれるかを返す。"""
    return any(unicodedata.category(character) == 'Cc'
               for character in value)


def parse_positive_int(value: Optional[str]) -> Optional[int]:
    """正の整数文字列を整数へ変換し、不正ならNoneを返す。"""
    try:
        parsed = int(value or '')
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def is_valid_email(value: str) -> bool:
    """課題用の簡易的なメールアドレス形式検証を行う。"""
    if not value or len(value) > MAX_EMAIL_LENGTH:
        return False
    if has_control_character(value) or any(char.isspace() for char in value):
        return False
    if value.count('@') != 1:
        return False
    local, domain = value.split('@')
    return bool(
        local and domain and '.' in domain and not domain.startswith('.')
    )


def get_bureaus() -> list[sqlite3.Row]:
    """局一覧を返す。"""
    return get_db().execute(
        'SELECT id, name, capacity FROM bureaus ORDER BY id'
    ).fetchall()


def get_slots_for_bureau(bureau_id: int) -> list[sqlite3.Row]:
    """指定局の面接枠を、予約状況とともに返す。"""
    return get_db().execute(
        '''
        SELECT
            bureau_schedule.id,
            bureau_schedule.bureau_id,
            schedule.start_at,
            schedule.end_at,
            booked.id AS booked_applicant_id,
            booked.name AS booked_applicant_name,
            COUNT(availability.applicant_id) AS availability_count
        FROM bureau_schedules AS bureau_schedule
        JOIN schedules AS schedule
          ON schedule.id = bureau_schedule.schedule_id
        LEFT JOIN applicants AS booked
          ON booked.confirmed_bureau_schedule_id = bureau_schedule.id
        LEFT JOIN applicant_availabilities AS availability
          ON availability.bureau_schedule_id = bureau_schedule.id
        WHERE bureau_schedule.bureau_id = ?
        GROUP BY bureau_schedule.id
        ORDER BY schedule.start_at, bureau_schedule.id
        ''',
        (bureau_id,),
    ).fetchall()


def get_assignment_board(bureau_id: int) -> dict[str, list[object]]:
    """指定局の応募者と面接枠を、割り当てボード用にまとめる。"""
    con = get_db()
    applicant_rows = con.execute(
        '''
        SELECT
            applicant.id,
            applicant.name,
            applicant.email,
            applicant.confirmed_bureau_schedule_id,
            applicant.decision,
            COALESCE(GROUP_CONCAT(availability.bureau_schedule_id), '')
                AS availability_ids,
            EXISTS(
                SELECT 1 FROM scores
                WHERE scores.applicant_id = applicant.id
            ) AS has_scores
        FROM applicants AS applicant
        LEFT JOIN applicant_availabilities AS availability
          ON availability.applicant_id = applicant.id
        WHERE applicant.bureau_id = ?
        GROUP BY applicant.id
        ORDER BY applicant.id
        ''',
        (bureau_id,),
    ).fetchall()

    applicants: list[dict[str, object]] = []
    for row in applicant_rows:
        applicant = dict(row)
        applicant['availability_ids'] = [
            int(value) for value in row['availability_ids'].split(',')
            if value
        ]
        applicant['has_scores'] = bool(row['has_scores'])
        applicants.append(applicant)

    applicant_by_slot = {
        applicant['confirmed_bureau_schedule_id']: applicant
        for applicant in applicants
        if applicant['confirmed_bureau_schedule_id'] is not None
    }
    slots: list[dict[str, object]] = []
    for row in get_slots_for_bureau(bureau_id):
        slot = dict(row)
        slot['applicant'] = applicant_by_slot.get(slot['id'])
        slots.append(slot)

    return {
        'unassigned': [
            applicant for applicant in applicants
            if applicant['confirmed_bureau_schedule_id'] is None
        ],
        'slots': slots,
    }


def normalize_schedule_datetime(value: Optional[str]) -> Optional[str]:
    """datetime-local等の入力をDB保存形式へ変換する。"""
    raw_value = (value or '').strip()
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')


def escape_like(value: str) -> str:
    """LIKE検索でワイルドカードを通常文字として扱えるようにする。"""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def render_error(message: str, status: int = 400):
    """利用者向けエラーページを返す。"""
    return render_template('error.html', message=message), status


def validate_applicant_form(
        name: str,
        email: str,
        bureau_id: Optional[int],
        remark: str,
        availability_values: list[str],
) -> tuple[list[str], list[int]]:
    """応募者フォームを検証し、エラーと面接枠IDを返す。"""
    errors: list[str] = []
    availability_ids: list[int] = []

    if not name:
        errors.append('氏名は必須です。')
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f'氏名は{MAX_NAME_LENGTH}文字以内で入力してください。')
    elif has_control_character(name):
        errors.append('氏名に制御文字は使用できません。')

    if not is_valid_email(email):
        errors.append('メールアドレスの形式が正しくありません。')

    if len(remark) > MAX_REMARK_LENGTH:
        errors.append(f'備考は{MAX_REMARK_LENGTH}文字以内で入力してください。')
    elif has_control_character(remark):
        errors.append('備考に制御文字は使用できません。')

    if bureau_id is None:
        errors.append('希望局を選択してください。')
    else:
        bureau = get_db().execute(
            'SELECT id FROM bureaus WHERE id = ?', (bureau_id,)
        ).fetchone()
        if bureau is None:
            errors.append('指定された局は存在しません。')

    for raw_value in availability_values:
        slot_id = parse_positive_int(raw_value)
        if slot_id is None:
            errors.append('面接可能枠の指定が正しくありません。')
            break
        availability_ids.append(slot_id)
    availability_ids = list(dict.fromkeys(availability_ids))

    if not availability_ids:
        errors.append('面接可能枠を一つ以上選択してください。')
    elif bureau_id is not None:
        placeholders = ','.join('?' for _ in availability_ids)
        rows = get_db().execute(
            f'''
            SELECT id
            FROM bureau_schedules
            WHERE bureau_id = ? AND id IN ({placeholders})
            ''',
            (bureau_id, *availability_ids),
        ).fetchall()
        if len(rows) != len(availability_ids):
            errors.append('希望局に属さない面接枠が含まれています。')

    return errors, availability_ids


def validate_criterion_form(
        name: str, description: str, bureau_id: Optional[int],
) -> list[str]:
    """採用基準フォームを検証する。"""
    errors: list[str] = []
    if not name:
        errors.append('基準名は必須です。')
    elif len(name) > MAX_CRITERION_NAME_LENGTH:
        errors.append(
            f'基準名は{MAX_CRITERION_NAME_LENGTH}文字以内で入力してください。',
        )
    elif has_control_character(name):
        errors.append('基準名に制御文字は使用できません。')

    if not description:
        errors.append('説明は必須です。')
    elif len(description) > MAX_CRITERION_DESCRIPTION_LENGTH:
        errors.append(
            '説明は'
            f'{MAX_CRITERION_DESCRIPTION_LENGTH}文字以内で入力してください。',
        )
    elif has_control_character(description):
        errors.append('説明に制御文字は使用できません。')

    if bureau_id is None:
        errors.append('局を選択してください。')
    else:
        bureau = get_db().execute(
            'SELECT id FROM bureaus WHERE id = ?', (bureau_id,),
        ).fetchone()
        if bureau is None:
            errors.append('指定された局は存在しません。')
    return errors


@app.route('/')
def index() -> str:
    """役割を選択する入口ページを表示する。"""
    session.pop('active_role', None)
    return render_template('index.html')


@app.route('/role/<role>')
def select_role(role: str):
    """ログインなしで利用する画面区分を選択する。"""
    if role not in ROLE_HOME_ENDPOINTS:
        return render_error('役割の指定が正しくありません。', 404)
    session['active_role'] = role
    return redirect(url_for(ROLE_HOME_ENDPOINTS[role]))


@app.route('/applicant')
@role_required('applicant')
def applicant_home() -> str:
    """応募者向けの入口を表示する。"""
    return render_template('role_home_applicant.html')


@app.route('/interviewer')
@role_required('interviewer')
def interviewer_home() -> str:
    """面接官向けの入口を表示する。"""
    return render_template('role_home_interviewer.html')


@app.route('/manager')
@role_required('bureau_manager')
def bureau_manager_home() -> str:
    """局責任者向けの入口を表示する。"""
    return render_template('role_home_manager.html')


@app.route('/applicant/applications/new', methods=['GET', 'POST'])
@role_required('applicant')
def applicant_new():
    """応募者と複数の希望面接枠を一括登録する。"""
    bureaus = get_bureaus()
    errors: list[str] = []
    form = {
        'name': '',
        'email': '',
        'bureau_id': request.args.get('bureau_id', ''),
        'remark': '',
    }
    selected_ids: list[int] = []

    if request.method == 'POST':
        form = {
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip().lower(),
            'bureau_id': request.form.get('bureau_id', ''),
            'remark': request.form.get('remark', '').strip(),
        }
        bureau_id = parse_positive_int(form['bureau_id'])
        errors, selected_ids = validate_applicant_form(
            form['name'], form['email'], bureau_id, form['remark'],
            request.form.getlist('availability_ids'),
        )
        if not errors and bureau_id is not None:
            con = get_db()
            try:
                con.execute('BEGIN')
                cursor = con.execute(
                    '''
                    INSERT INTO applicants
                        (name, email, bureau_id, remark)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (form['name'], form['email'], bureau_id, form['remark']),
                )
                applicant_id = cursor.lastrowid
                con.executemany(
                    '''
                    INSERT INTO applicant_availabilities
                        (applicant_id, bureau_schedule_id)
                    VALUES (?, ?)
                    ''',
                    [(applicant_id, slot_id) for slot_id in selected_ids],
                )
                con.commit()
            except sqlite3.IntegrityError as exception:
                con.rollback()
                if 'applicants.email' in str(exception):
                    errors.append('このメールアドレスは既に登録されています。')
                else:
                    errors.append('入力内容がデータベースの制約に違反しています。')
            except sqlite3.Error:
                con.rollback()
                errors.append('データベースエラーのため登録できませんでした。')
            else:
                return redirect(url_for(
                    'applicant_home', registered='1',
                ))

    selected_bureau_id = parse_positive_int(form['bureau_id'])
    slots = (get_slots_for_bureau(selected_bureau_id)
             if selected_bureau_id is not None else [])
    return render_template(
        'applicant_form.html',
        title='応募登録',
        action_label='登録する',
        form=form,
        bureaus=bureaus,
        slots=slots,
        selected_ids=selected_ids,
        errors=errors,
        bureau_locked=False,
    )


@app.route('/manager/applicants')
@role_required('bureau_manager')
def applicants() -> str:
    """VIEWを利用して応募者一覧を検索する。"""
    bureau_id = parse_positive_int(request.args.get('bureau_id'))
    name = request.args.get('name', '').strip()
    schedule_status = request.args.get('schedule_status', 'all')
    decision = request.args.get('decision', 'all')

    clauses: list[str] = []
    parameters: list[object] = []
    if bureau_id is not None:
        clauses.append('bureau_id = ?')
        parameters.append(bureau_id)
    if name:
        clauses.append("applicant_name LIKE ? ESCAPE '\\'")
        parameters.append(f'%{escape_like(name)}%')
    if schedule_status == 'confirmed':
        clauses.append('confirmed_bureau_schedule_id IS NOT NULL')
    elif schedule_status == 'unconfirmed':
        clauses.append('confirmed_bureau_schedule_id IS NULL')
    if decision == 'undecided':
        clauses.append('decision IS NULL')
    elif decision in ('accepted', 'rejected', 'waitlisted', 'withdrawn'):
        clauses.append('decision = ?')
        parameters.append(decision)

    sql = 'SELECT * FROM applicant_overview'
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    sql += ' ORDER BY bureau_id, applicant_id'
    rows = get_db().execute(sql, parameters).fetchall()
    return render_template(
        'applicants.html',
        applicants=rows,
        bureaus=get_bureaus(),
        selected_bureau_id=bureau_id,
        name=name,
        schedule_status=schedule_status,
        decision=decision,
        decision_labels=DECISION_LABELS,
    )


@app.route('/manager/applicants/<id>')
@role_required('bureau_manager')
def applicant_detail(id: str):
    """応募者の希望枠、確定枠、評価進捗を表示する。"""
    applicant_id = parse_positive_int(id)
    if applicant_id is None:
        return render_error('応募者IDが正しくありません。', 404)
    applicant = get_db().execute(
        'SELECT * FROM applicant_overview WHERE applicant_id = ?',
        (applicant_id,),
    ).fetchone()
    if applicant is None:
        return render_error('指定された応募者は存在しません。', 404)

    availabilities = get_db().execute(
        '''
        SELECT
            bureau_schedule.id,
            schedule.start_at,
            schedule.end_at,
            booked.id AS booked_applicant_id,
            booked.name AS booked_applicant_name
        FROM applicant_availabilities AS availability
        JOIN bureau_schedules AS bureau_schedule
          ON bureau_schedule.id = availability.bureau_schedule_id
        JOIN schedules AS schedule
          ON schedule.id = bureau_schedule.schedule_id
        LEFT JOIN applicants AS booked
          ON booked.confirmed_bureau_schedule_id = bureau_schedule.id
        WHERE availability.applicant_id = ?
        ORDER BY schedule.start_at
        ''',
        (applicant_id,),
    ).fetchall()
    evaluation_progress = get_db().execute(
        '''
        SELECT
            interviewer.id AS interviewer_id,
            interviewer.name AS interviewer_name,
            COUNT(score.criterion_id) AS score_count,
            (SELECT COUNT(*) FROM criteria
             WHERE bureau_id = interviewer.bureau_id) AS criterion_count
        FROM interviewers AS interviewer
        LEFT JOIN scores AS score
          ON score.interviewer_id = interviewer.id
         AND score.applicant_id = ?
        WHERE interviewer.bureau_id = ?
        GROUP BY interviewer.id
        ORDER BY interviewer.id
        ''',
        (applicant_id, applicant['bureau_id']),
    ).fetchall()
    return render_template(
        'applicant_detail.html',
        applicant=applicant,
        availabilities=availabilities,
        evaluation_progress=evaluation_progress,
        decision_labels=DECISION_LABELS,
        message=request.args.get('message', ''),
        error=request.args.get('error', ''),
    )


@app.route('/manager/applicants/<id>/edit', methods=['GET', 'POST'])
@role_required('bureau_manager')
def applicant_edit(id: str):
    """応募者情報と希望枠をトランザクションで更新する。"""
    applicant_id = parse_positive_int(id)
    if applicant_id is None:
        return render_error('応募者IDが正しくありません。', 404)
    applicant = get_db().execute(
        'SELECT * FROM applicants WHERE id = ?', (applicant_id,)
    ).fetchone()
    if applicant is None:
        return render_error('指定された応募者は存在しません。', 404)

    errors: list[str] = []
    selected_ids = [row['bureau_schedule_id'] for row in get_db().execute(
        '''SELECT bureau_schedule_id FROM applicant_availabilities
           WHERE applicant_id = ?''', (applicant_id,)
    ).fetchall()]
    form = {
        'name': applicant['name'],
        'email': applicant['email'],
        'bureau_id': str(applicant['bureau_id']),
        'remark': applicant['remark'],
    }

    if request.method == 'POST':
        form['name'] = request.form.get('name', '').strip()
        form['email'] = request.form.get('email', '').strip().lower()
        form['remark'] = request.form.get('remark', '').strip()
        errors, selected_ids = validate_applicant_form(
            form['name'], form['email'], applicant['bureau_id'],
            form['remark'],
            request.form.getlist('availability_ids'),
        )
        confirmed_id = applicant['confirmed_bureau_schedule_id']
        if confirmed_id is not None and confirmed_id not in selected_ids:
            errors.append('確定済みの面接枠は希望枠から外せません。')

        if not errors:
            con = get_db()
            try:
                con.execute('BEGIN')
                con.execute(
                    '''UPDATE applicants SET name = ?, email = ?, remark = ?
                       WHERE id = ?''',
                    (form['name'], form['email'],
                     form['remark'], applicant_id),
                )
                con.executemany(
                    '''INSERT OR IGNORE INTO applicant_availabilities
                       (applicant_id, bureau_schedule_id) VALUES (?, ?)''',
                    [(applicant_id, slot_id) for slot_id in selected_ids],
                )
                placeholders = ','.join('?' for _ in selected_ids)
                con.execute(
                    f'''DELETE FROM applicant_availabilities
                        WHERE applicant_id = ?
                          AND bureau_schedule_id NOT IN ({placeholders})''',
                    (applicant_id, *selected_ids),
                )
                con.commit()
            except sqlite3.IntegrityError as exception:
                con.rollback()
                if 'applicants.email' in str(exception):
                    errors.append('このメールアドレスは既に登録されています。')
                else:
                    errors.append('入力内容がデータベースの制約に違反しています。')
            except sqlite3.Error:
                con.rollback()
                errors.append('データベースエラーのため更新できませんでした。')
            else:
                return redirect(url_for(
                    'applicant_detail', id=applicant_id,
                    message='応募情報を更新しました。',
                ))

    return render_template(
        'applicant_form.html',
        title='応募情報の編集',
        action_label='更新する',
        form=form,
        bureaus=get_bureaus(),
        slots=get_slots_for_bureau(applicant['bureau_id']),
        selected_ids=selected_ids,
        errors=errors,
        bureau_locked=True,
    )


def update_applicant_schedule(
        applicant_id: int, slot_id: Optional[int],
) -> tuple[bool, str]:
    """応募者の確定面接枠を検証付きで更新する。"""
    con = get_db()
    applicant = con.execute(
        'SELECT id, bureau_id FROM applicants WHERE id = ?',
        (applicant_id,),
    ).fetchone()
    if applicant is None:
        return False, '指定された応募者は存在しません。'

    if slot_id is not None:
        slot = con.execute(
            'SELECT bureau_id FROM bureau_schedules WHERE id = ?',
            (slot_id,),
        ).fetchone()
        if slot is None:
            return False, '指定された面接枠は存在しません。'
        if slot['bureau_id'] != applicant['bureau_id']:
            return False, '応募者と面接枠の局が一致していません。'
        availability = con.execute(
            '''SELECT 1 FROM applicant_availabilities
               WHERE applicant_id = ? AND bureau_schedule_id = ?''',
            (applicant_id, slot_id),
        ).fetchone()
        if availability is None:
            return False, '応募者が希望していない面接枠は確定できません。'

    try:
        con.execute(
            '''UPDATE applicants SET confirmed_bureau_schedule_id = ?
               WHERE id = ?''', (slot_id, applicant_id),
        )
        con.commit()
    except sqlite3.IntegrityError as exception:
        con.rollback()
        if 'locked after scoring' in str(exception):
            return False, '評価入力後は確定面接枠を変更できません。'
        return False, 'その面接枠は既に予約されているか、選択できません。'
    except sqlite3.Error:
        con.rollback()
        return False, 'データベースエラーのため面接枠を更新できませんでした。'
    return True, '確定面接枠を更新しました。'


@app.route('/manager/applicants/<id>/schedule', methods=['POST'])
@role_required('bureau_manager')
def applicant_schedule(id: str) -> Response:
    """希望枠の一つを確定面接枠として割り当てる。"""
    applicant_id = parse_positive_int(id)
    if applicant_id is None:
        return redirect(url_for('applicants'))
    raw_slot_id = request.form.get('bureau_schedule_id', '')
    slot_id = None if raw_slot_id == '' else parse_positive_int(raw_slot_id)
    if raw_slot_id != '' and slot_id is None:
        return redirect(url_for(
            'applicant_detail', id=applicant_id,
            error='面接枠の指定が正しくありません。',
        ))

    success, message = update_applicant_schedule(applicant_id, slot_id)
    if not success:
        if message == '指定された応募者は存在しません。':
            return redirect(url_for('applicants'))
        return redirect(url_for(
            'applicant_detail', id=applicant_id, error=message,
        ))
    return redirect(url_for(
        'applicant_detail', id=applicant_id, message=message,
    ))


@app.route('/manager/assignments', methods=['POST'])
@role_required('bureau_manager')
def manager_assignment():
    """割り当てボードからの面接枠変更をJSONで受け付ける。"""
    applicant_id = parse_positive_int(request.form.get('applicant_id'))
    raw_slot_id = request.form.get('bureau_schedule_id', '')
    slot_id = None if raw_slot_id == '' else parse_positive_int(raw_slot_id)
    if applicant_id is None or (raw_slot_id != '' and slot_id is None):
        return jsonify(
            success=False, error='応募者または面接枠の指定が正しくありません。',
        ), 400

    success, message = update_applicant_schedule(applicant_id, slot_id)
    if not success:
        return jsonify(success=False, error=message), 409
    return jsonify(success=True, message=message)


@app.route('/manager/applicants/<id>/decision', methods=['POST'])
@role_required('bureau_manager')
def applicant_decision(id: str) -> Response:
    """局責任者による採否決定を保存する。"""
    applicant_id = parse_positive_int(id)
    if applicant_id is None:
        return redirect(url_for('applicants'))
    raw_decision = request.form.get('decision', '')
    decision = None if raw_decision == '' else raw_decision
    if decision not in (
            None, 'accepted', 'rejected', 'waitlisted', 'withdrawn'):
        return redirect(url_for(
            'applicant_detail', id=applicant_id,
            error='採否の指定が正しくありません。',
        ))
    con = get_db()
    cursor = con.execute(
        'UPDATE applicants SET decision = ? WHERE id = ?',
        (decision, applicant_id),
    )
    con.commit()
    if cursor.rowcount == 0:
        return redirect(url_for('applicants'))
    return redirect(url_for(
        'applicant_detail', id=applicant_id,
        message='採否を更新しました。',
    ))


@app.route('/manager/criteria', methods=['GET', 'POST'])
@role_required('bureau_manager')
def criteria_manage():
    """局責任者が自局の採用基準を一覧・作成する。"""
    con = get_db()
    bureaus = get_bureaus()
    raw_bureau_id = (
        request.form.get('bureau_id') if request.method == 'POST'
        else request.args.get('bureau_id')
    )
    bureau_id = parse_positive_int(raw_bureau_id) or 1
    name = request.form.get('name', '').strip() if request.method == 'POST' else ''
    description = (
        request.form.get('description', '').strip()
        if request.method == 'POST' else ''
    )
    errors: list[str] = []
    message = request.args.get('message', '')

    if request.method == 'POST':
        errors = validate_criterion_form(name, description, bureau_id)
        if not errors:
            try:
                con.execute(
                    '''INSERT INTO criteria (bureau_id, name, description)
                       VALUES (?, ?, ?)''',
                    (bureau_id, name, description),
                )
                con.commit()
            except sqlite3.IntegrityError:
                con.rollback()
                errors.append('同じ局に同名の採用基準は作成できません。')
            except sqlite3.Error:
                con.rollback()
                errors.append('データベースエラーのため作成できませんでした。')
            else:
                return redirect(url_for(
                    'criteria_manage', bureau_id=bureau_id,
                    message='採用基準を作成しました。',
                ))

    criteria_rows = con.execute(
        '''
        SELECT criterion.id, criterion.bureau_id, criterion.name,
               criterion.description, COUNT(score.applicant_id) AS score_count
        FROM criteria AS criterion
        LEFT JOIN scores AS score ON score.criterion_id = criterion.id
        WHERE criterion.bureau_id = ?
        GROUP BY criterion.id
        ORDER BY criterion.id
        ''',
        (bureau_id,),
    ).fetchall()
    selected_bureau = next(
        (bureau for bureau in bureaus if bureau['id'] == bureau_id), None,
    )
    return render_template(
        'criteria.html',
        bureaus=bureaus,
        selected_bureau=selected_bureau,
        selected_bureau_id=bureau_id,
        criteria=criteria_rows,
        form={'name': name, 'description': description},
        errors=errors,
        message=message,
    )


@app.route('/manager/criteria/<id>/edit', methods=['GET', 'POST'])
@role_required('bureau_manager')
def criterion_edit(id: str):
    """局責任者が自局の採用基準を編集する。"""
    criterion_id = parse_positive_int(id)
    if criterion_id is None:
        return render_error('採用基準IDが正しくありません。', 404)

    con = get_db()
    criterion = con.execute(
        '''
        SELECT criterion.id, criterion.bureau_id, criterion.name,
               criterion.description, COUNT(score.applicant_id) AS score_count
        FROM criteria AS criterion
        LEFT JOIN scores AS score ON score.criterion_id = criterion.id
        WHERE criterion.id = ?
        GROUP BY criterion.id
        ''',
        (criterion_id,),
    ).fetchone()
    if criterion is None:
        return render_error('指定された採用基準は存在しません。', 404)

    raw_bureau_id = (
        request.form.get('bureau_id') if request.method == 'POST'
        else request.args.get('bureau_id')
    )
    requested_bureau_id = parse_positive_int(raw_bureau_id)
    if raw_bureau_id and requested_bureau_id is None:
        return render_error('局の指定が正しくありません。', 400)
    bureau_id = requested_bureau_id or criterion['bureau_id']
    if bureau_id != criterion['bureau_id']:
        return render_error('自局の採用基準だけを編集できます。', 404)

    name = criterion['name']
    description = criterion['description']
    errors: list[str] = []
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        errors = validate_criterion_form(name, description, bureau_id)
        if not errors:
            try:
                cursor = con.execute(
                    '''UPDATE criteria
                       SET name = ?, description = ?
                       WHERE id = ? AND bureau_id = ?''',
                    (name, description, criterion_id, bureau_id),
                )
                con.commit()
            except sqlite3.IntegrityError:
                con.rollback()
                errors.append('同じ局に同名の採用基準は設定できません。')
            except sqlite3.Error:
                con.rollback()
                errors.append('データベースエラーのため更新できませんでした。')
            else:
                if cursor.rowcount == 0:
                    return render_error('指定された採用基準は存在しません。', 404)
                return redirect(url_for(
                    'criteria_manage', bureau_id=bureau_id,
                    message='採用基準を更新しました。',
                ))

    bureau = con.execute(
        'SELECT id, name FROM bureaus WHERE id = ?', (bureau_id,),
    ).fetchone()
    return render_template(
        'criterion_form.html',
        criterion=criterion,
        bureau=bureau,
        bureau_id=bureau_id,
        form={'name': name, 'description': description},
        errors=errors,
    )


@app.route('/manager/bureau-schedules', methods=['GET', 'POST'])
@role_required('bureau_manager')
def bureau_schedules():
    """局別面接枠を一覧表示し、新規登録する。"""
    bureau_id = parse_positive_int(
        request.form.get('bureau_id') if request.method == 'POST'
        else request.args.get('bureau_id')) or 1
    con = get_db()
    bureaus = get_bureaus()
    message = request.args.get('message', '')
    error = request.args.get('error', '')
    new_start_at = request.form.get('start_at', '')
    new_end_at = request.form.get('end_at', '')

    if request.method == 'POST':
        raw_schedule_id = request.form.get('schedule_id', '')
        schedule_id = parse_positive_int(raw_schedule_id)
        normalized_start_at = normalize_schedule_datetime(new_start_at)
        normalized_end_at = normalize_schedule_datetime(new_end_at)
        if raw_schedule_id and schedule_id is None:
            error = '共通時間帯の指定が正しくありません。'
        elif schedule_id is None and not new_start_at and not new_end_at:
            error = '既存の時間帯を選ぶか、新しい開始・終了時刻を入力してください。'
        elif schedule_id is None and (
                normalized_start_at is None or normalized_end_at is None):
            error = '開始・終了時刻の形式が正しくありません。'
        elif schedule_id is None and normalized_start_at >= normalized_end_at:
            error = '終了時刻は開始時刻より後にしてください。'
        else:
            try:
                con.execute('BEGIN')
                if schedule_id is None:
                    con.execute(
                        '''INSERT OR IGNORE INTO schedules (start_at, end_at)
                           VALUES (?, ?)''',
                        (normalized_start_at, normalized_end_at),
                    )
                    schedule = con.execute(
                        '''SELECT id FROM schedules
                           WHERE start_at = ? AND end_at = ?''',
                        (normalized_start_at, normalized_end_at),
                    ).fetchone()
                    if schedule is None:
                        raise sqlite3.IntegrityError(
                            'schedule could not be created',
                        )
                    schedule_id = schedule['id']
                con.execute(
                    '''INSERT INTO bureau_schedules (bureau_id, schedule_id)
                       VALUES (?, ?)''', (bureau_id, schedule_id),
                )
                con.commit()
            except sqlite3.IntegrityError as exception:
                con.rollback()
                if 'overlaps' in str(exception):
                    error = '同じ局の既存面接枠と時間が重複します。'
                else:
                    error = 'この局と時間帯の面接枠は登録できません。'
            except sqlite3.Error:
                con.rollback()
                error = 'データベースエラーのため登録できませんでした。'
            else:
                return redirect(url_for(
                    'bureau_schedules', bureau_id=bureau_id,
                    message='局別面接枠を追加しました。',
                ))

    common_schedules = con.execute(
        '''SELECT id, start_at, end_at FROM schedules ORDER BY start_at'''
    ).fetchall()
    selected_bureau = next(
        (bureau for bureau in bureaus if bureau['id'] == bureau_id), None,
    )
    return render_template(
        'bureau_schedules.html',
        bureaus=bureaus,
        selected_bureau=selected_bureau,
        selected_bureau_id=bureau_id,
        slots=get_slots_for_bureau(bureau_id),
        board=get_assignment_board(bureau_id),
        common_schedules=common_schedules,
        new_start_at=new_start_at,
        new_end_at=new_end_at,
        message=message,
        error=error,
    )


@app.route('/manager/bureau-schedules/<id>/edit', methods=['GET', 'POST'])
@role_required('bureau_manager')
def bureau_schedule_edit(id: str):
    """未使用の局別面接枠が参照する共通時間帯を変更する。"""
    slot_id = parse_positive_int(id)
    if slot_id is None:
        return render_error('面接枠IDが正しくありません。', 404)
    con = get_db()
    slot = con.execute(
        '''
        SELECT bureau_schedule.id, bureau_schedule.bureau_id,
               bureau_schedule.schedule_id, bureau.name AS bureau_name,
               schedule.start_at, schedule.end_at,
               (SELECT COUNT(*) FROM applicant_availabilities
                WHERE bureau_schedule_id = bureau_schedule.id)
                    AS reference_count
        FROM bureau_schedules AS bureau_schedule
        JOIN bureaus AS bureau ON bureau.id = bureau_schedule.bureau_id
        JOIN schedules AS schedule ON schedule.id = bureau_schedule.schedule_id
        WHERE bureau_schedule.id = ?
        ''', (slot_id,),
    ).fetchone()
    if slot is None:
        return render_error('指定された面接枠は存在しません。', 404)

    error = ''
    if request.method == 'POST':
        schedule_id = parse_positive_int(request.form.get('schedule_id'))
        if schedule_id is None:
            error = '共通時間帯を選択してください。'
        elif (slot['reference_count'] > 0
              and schedule_id != slot['schedule_id']):
            error = '応募者が希望している面接枠の時間は変更できません。'
        else:
            try:
                con.execute(
                    'UPDATE bureau_schedules SET schedule_id = ? WHERE id = ?',
                    (schedule_id, slot_id),
                )
                con.commit()
            except sqlite3.IntegrityError as exception:
                con.rollback()
                if 'overlaps' in str(exception):
                    error = '同じ局の既存面接枠と時間が重複します。'
                else:
                    error = '指定された時間帯へ変更できません。'
            else:
                return redirect(url_for(
                    'bureau_schedules', bureau_id=slot['bureau_id'],
                    message='局別面接枠を更新しました。',
                ))
    common_schedules = con.execute(
        'SELECT id, start_at, end_at FROM schedules ORDER BY start_at'
    ).fetchall()
    return render_template(
        'bureau_schedule_edit.html',
        slot=slot,
        common_schedules=common_schedules,
        error=error,
    )


@app.route('/manager/bureau-schedules/<id>/delete', methods=['POST'])
@role_required('bureau_manager')
def bureau_schedule_delete(id: str) -> Response:
    """応募者から参照されていない局別面接枠を削除する。"""
    slot_id = parse_positive_int(id)
    if slot_id is None:
        return redirect(url_for('bureau_schedules'))
    con = get_db()
    slot = con.execute(
        'SELECT bureau_id FROM bureau_schedules WHERE id = ?', (slot_id,)
    ).fetchone()
    if slot is None:
        return redirect(url_for('bureau_schedules'))
    reference_count = con.execute(
        '''
        SELECT
            (SELECT COUNT(*) FROM applicant_availabilities
             WHERE bureau_schedule_id = ?)
          + (SELECT COUNT(*) FROM applicants
             WHERE confirmed_bureau_schedule_id = ?) AS reference_count
        ''', (slot_id, slot_id),
    ).fetchone()['reference_count']
    if reference_count > 0:
        return redirect(url_for(
            'bureau_schedules', bureau_id=slot['bureau_id'],
            error='応募者から参照されている面接枠は削除できません。',
        ))
    try:
        con.execute('DELETE FROM bureau_schedules WHERE id = ?', (slot_id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        return redirect(url_for(
            'bureau_schedules', bureau_id=slot['bureau_id'],
            error='データベースエラーのため削除できませんでした。',
        ))
    return redirect(url_for(
        'bureau_schedules', bureau_id=slot['bureau_id'],
        message='局別面接枠を削除しました。',
    ))


@app.route('/interviewer/interviewers')
@role_required('interviewer')
def interviewers() -> str:
    """面接官メニューを表示する。"""
    rows = get_db().execute(
        '''
        SELECT interviewer.id, interviewer.name, interviewer.role,
               bureau.id AS bureau_id, bureau.name AS bureau_name,
               COUNT(applicant.id) AS confirmed_applicant_count
        FROM interviewers AS interviewer
        JOIN bureaus AS bureau ON bureau.id = interviewer.bureau_id
        LEFT JOIN applicants AS applicant
          ON applicant.bureau_id = interviewer.bureau_id
         AND applicant.confirmed_bureau_schedule_id IS NOT NULL
        GROUP BY interviewer.id
        ORDER BY bureau.id, interviewer.id
        ''').fetchall()
    return render_template('interviewers.html', interviewers=rows)


@app.route('/interviewer/interviewers/<id>/evaluations')
@role_required('interviewer')
def interviewer_evaluations(id: str):
    """指定面接官と同じ局の面接確定済み応募者を表示する。"""
    interviewer_id = parse_positive_int(id)
    if interviewer_id is None:
        return render_error('面接官IDが正しくありません。', 404)
    con = get_db()
    interviewer = con.execute(
        '''SELECT interviewer.*, bureau.name AS bureau_name
           FROM interviewers AS interviewer
           JOIN bureaus AS bureau ON bureau.id = interviewer.bureau_id
           WHERE interviewer.id = ?''', (interviewer_id,)
    ).fetchone()
    if interviewer is None:
        return render_error('指定された面接官は存在しません。', 404)
    applicants_for_evaluation = con.execute(
        '''
        SELECT applicant.id, applicant.name, schedule.start_at,
               schedule.end_at, COUNT(score.criterion_id) AS score_count,
               (SELECT COUNT(*) FROM criteria
                WHERE bureau_id = applicant.bureau_id) AS criterion_count
        FROM applicants AS applicant
        JOIN bureau_schedules AS bureau_schedule
          ON bureau_schedule.id = applicant.confirmed_bureau_schedule_id
        JOIN schedules AS schedule ON schedule.id = bureau_schedule.schedule_id
        LEFT JOIN scores AS score
          ON score.applicant_id = applicant.id
         AND score.interviewer_id = ?
        WHERE applicant.bureau_id = ?
        GROUP BY applicant.id
        ORDER BY schedule.start_at, applicant.id
        ''', (interviewer_id, interviewer['bureau_id']),
    ).fetchall()
    return render_template(
        'evaluations.html',
        interviewer=interviewer,
        applicants=applicants_for_evaluation,
        message=request.args.get('message', ''),
    )


@app.route(
    '/interviewer/interviewers/<interviewer_id>/applicants/<applicant_id>/scores',
    methods=['GET', 'POST'],
)
@role_required('interviewer')
def score_edit(interviewer_id: str, applicant_id: str):
    """局の全評価項目を一つのトランザクションで保存する。"""
    parsed_interviewer_id = parse_positive_int(interviewer_id)
    parsed_applicant_id = parse_positive_int(applicant_id)
    if parsed_interviewer_id is None or parsed_applicant_id is None:
        return render_error('面接官または応募者IDが正しくありません。', 404)
    con = get_db()
    context = con.execute(
        '''
        SELECT interviewer.id AS interviewer_id,
               interviewer.name AS interviewer_name,
               interviewer.bureau_id,
               bureau.name AS bureau_name,
               applicant.id AS applicant_id,
               applicant.name AS applicant_name
        FROM interviewers AS interviewer
        JOIN bureaus AS bureau ON bureau.id = interviewer.bureau_id
        JOIN applicants AS applicant
          ON applicant.id = ?
         AND applicant.bureau_id = interviewer.bureau_id
         AND applicant.confirmed_bureau_schedule_id IS NOT NULL
        WHERE interviewer.id = ?
        ''', (parsed_applicant_id, parsed_interviewer_id),
    ).fetchone()
    if context is None:
        return render_error(
            '同じ局に所属し、面接が確定した応募者だけを評価できます。', 404,
        )
    criteria = con.execute(
        '''
        SELECT criterion.id, criterion.name, criterion.description,
               score.score
        FROM criteria AS criterion
        LEFT JOIN scores AS score
          ON score.criterion_id = criterion.id
         AND score.applicant_id = ?
         AND score.interviewer_id = ?
        WHERE criterion.bureau_id = ?
        ORDER BY criterion.id
        ''',
        (parsed_applicant_id, parsed_interviewer_id, context['bureau_id']),
    ).fetchall()
    errors: list[str] = []
    entered_scores = {
        criterion['id']: (str(criterion['score'])
                          if criterion['score'] is not None else '')
        for criterion in criteria
    }
    if request.method == 'POST':
        score_values: list[tuple[int, int, int, int]] = []
        for criterion in criteria:
            raw_score = request.form.get(
                f"score_{criterion['id']}", '').strip()
            entered_scores[criterion['id']] = raw_score
            score = parse_positive_int(raw_score)
            if score is None or score > 10:
                errors.append(
                    f"{criterion['name']}は1〜10の整数で入力してください。"
                )
            else:
                score_values.append((
                    parsed_applicant_id, parsed_interviewer_id,
                    criterion['id'], score,
                ))
        if not errors:
            try:
                con.execute('BEGIN')
                con.executemany(
                    '''
                    INSERT INTO scores
                        (applicant_id, interviewer_id, criterion_id, score)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (applicant_id, interviewer_id, criterion_id)
                    DO UPDATE SET score = excluded.score
                    ''', score_values,
                )
                con.commit()
            except sqlite3.IntegrityError:
                con.rollback()
                errors.append('局または評価項目の組み合わせが正しくありません。')
            except sqlite3.Error:
                con.rollback()
                errors.append('データベースエラーのため評価を保存できませんでした。')
            else:
                return redirect(url_for(
                    'interviewer_evaluations', id=parsed_interviewer_id,
                    message='全評価項目を保存しました。',
                ))
    return render_template(
        'score_form.html',
        context=context,
        criteria=criteria,
        entered_scores=entered_scores,
        errors=errors,
    )


def calculate_rankings(con: sqlite3.Connection, bureau_id: int):
    """評価者×評価項目のz得点と応募者別T得点を計算する。"""
    bureau = con.execute(
        'SELECT id, name, capacity FROM bureaus WHERE id = ?', (bureau_id,)
    ).fetchone()
    if bureau is None:
        return None, []
    criterion_ids = {
        row['id'] for row in con.execute(
            'SELECT id FROM criteria WHERE bureau_id = ?', (bureau_id,)
        ).fetchall()
    }
    applicant_rows = con.execute(
        '''SELECT * FROM applicant_overview
           WHERE bureau_id = ? ORDER BY applicant_id''', (bureau_id,)
    ).fetchall()
    score_rows = con.execute(
        '''
        SELECT score.applicant_id, score.interviewer_id,
               score.criterion_id, score.score,
               interviewer.name AS interviewer_name
        FROM scores AS score
        JOIN applicants AS applicant ON applicant.id = score.applicant_id
        JOIN interviewers AS interviewer
          ON interviewer.id = score.interviewer_id
        WHERE applicant.bureau_id = ?
        ORDER BY score.applicant_id, score.interviewer_id, score.criterion_id
        ''', (bureau_id,),
    ).fetchall()
    statistic_rows = con.execute(
        '''
        SELECT score.interviewer_id, score.criterion_id,
               COUNT(score.score) AS sample_count,
               AVG(score.score) AS mean_score,
               AVG(score.score * score.score) AS mean_square
        FROM scores AS score
        JOIN applicants AS applicant ON applicant.id = score.applicant_id
        WHERE applicant.bureau_id = ?
        GROUP BY score.interviewer_id, score.criterion_id
        ''', (bureau_id,),
    ).fetchall()
    statistics = {
        (row['interviewer_id'], row['criterion_id']): row
        for row in statistic_rows
    }
    scores_by_applicant: dict[int, list[sqlite3.Row]] = {}
    for row in score_rows:
        scores_by_applicant.setdefault(row['applicant_id'], []).append(row)

    ranking_rows: list[dict[str, object]] = []
    for applicant in applicant_rows:
        applicant_scores = scores_by_applicant.get(
            applicant['applicant_id'], [])
        raw_average = (
            sum(row['score']
                for row in applicant_scores) / len(applicant_scores)
            if applicant_scores else None
        )
        evaluator_criteria: dict[int, set[int]] = {}
        for row in applicant_scores:
            evaluator_criteria.setdefault(row['interviewer_id'], set()).add(
                row['criterion_id'])
        reasons: list[str] = []
        if applicant['decision'] == 'withdrawn':
            reasons.append('辞退')
        if applicant['confirmed_bureau_schedule_id'] is None:
            reasons.append('面接未確定')
        if len(evaluator_criteria) < 2:
            reasons.append('評価者不足')
        if any(criteria_set != criterion_ids
               for criteria_set in evaluator_criteria.values()):
            reasons.append('評価項目不足')

        t_scores: list[float] = []
        if not reasons:
            for row in applicant_scores:
                statistic = statistics.get(
                    (row['interviewer_id'], row['criterion_id']))
                if statistic is None or statistic['sample_count'] < 2:
                    reasons.append('補正用標本不足')
                    break
                mean = float(statistic['mean_score'])
                variance = float(statistic['mean_square']) - mean * mean
                variance = max(0.0, variance)
                if variance <= 1e-12:
                    z_score = 0.0
                else:
                    z_score = (row['score'] - mean) / (variance ** 0.5)
                t_scores.append(50.0 + 10.0 * z_score)

        normalized_score = (
            sum(t_scores) / len(t_scores) if t_scores and not reasons else None
        )
        ranking_rows.append({
            'applicant': applicant,
            'raw_average': raw_average,
            'normalized_score': normalized_score,
            'evaluator_count': len(evaluator_criteria),
            'reasons': list(dict.fromkeys(reasons)),
            'rank': None,
            'candidate_status': 'incomplete',
        })

    complete_rows = [
        row for row in ranking_rows if row['normalized_score'] is not None
    ]
    complete_rows.sort(key=lambda row: (
        -float(row['normalized_score']),
        row['applicant']['applicant_id'],
    ))
    for row in complete_rows:
        score = float(row['normalized_score'])
        higher_count = sum(
            1 for other in complete_rows
            if float(other['normalized_score']) > score + 1e-9
        )
        same_count = sum(
            1 for other in complete_rows
            if abs(float(other['normalized_score']) - score) <= 1e-9
        )
        start_position = higher_count + 1
        end_position = higher_count + same_count
        row['rank'] = start_position
        if start_position <= bureau['capacity'] < end_position:
            row['candidate_status'] = 'boundary_tie'
        elif end_position <= bureau['capacity']:
            row['candidate_status'] = 'candidate'
        else:
            row['candidate_status'] = 'outside'

    incomplete_rows = [
        row for row in ranking_rows if row['normalized_score'] is None
    ]
    incomplete_rows.sort(key=lambda row: row['applicant']['applicant_id'])
    return bureau, complete_rows + incomplete_rows


@app.route('/manager/rankings')
@role_required('bureau_manager')
def rankings() -> str:
    """局別の補正前平均と補正後ランキングを表示する。"""
    bureau_id = parse_positive_int(request.args.get('bureau_id')) or 1
    bureau, rows = calculate_rankings(get_db(), bureau_id)
    if bureau is None:
        return render_error('指定された局は存在しません。', 404)
    return render_template(
        'rankings.html',
        bureaus=get_bureaus(),
        bureau=bureau,
        rows=rows,
        decision_labels=DECISION_LABELS,
        message=request.args.get('message', ''),
    )


# 未プレフィックスのURLは移行期間の互換用として残す。通常の画面遷移では
# 役割プレフィックス付きURLだけを使うため、ナビゲーション上の混在は起きない。
LEGACY_RULES: Final[tuple[tuple[str, str, object, list[str]], ...]] = (
    ('/applicants/new', 'legacy_applicant_new', applicant_new, ['GET', 'POST']),
    ('/applicants', 'legacy_applicants', applicants, ['GET']),
    ('/applicants/<id>', 'legacy_applicant_detail', applicant_detail, ['GET']),
    (
        '/applicants/<id>/edit', 'legacy_applicant_edit', applicant_edit,
        ['GET', 'POST'],
    ),
    (
        '/applicants/<id>/schedule', 'legacy_applicant_schedule',
        applicant_schedule, ['POST'],
    ),
    (
        '/applicants/<id>/decision', 'legacy_applicant_decision',
        applicant_decision, ['POST'],
    ),
    (
        '/bureau-schedules', 'legacy_bureau_schedules', bureau_schedules,
        ['GET', 'POST'],
    ),
    (
        '/bureau-schedules/<id>/edit', 'legacy_bureau_schedule_edit',
        bureau_schedule_edit, ['GET', 'POST'],
    ),
    (
        '/bureau-schedules/<id>/delete', 'legacy_bureau_schedule_delete',
        bureau_schedule_delete, ['POST'],
    ),
    ('/interviewers', 'legacy_interviewers', interviewers, ['GET']),
    (
        '/interviewers/<id>/evaluations', 'legacy_interviewer_evaluations',
        interviewer_evaluations, ['GET'],
    ),
    (
        '/interviewers/<interviewer_id>/applicants/<applicant_id>/scores',
        'legacy_score_edit', score_edit, ['GET', 'POST'],
    ),
    ('/rankings', 'legacy_rankings', rankings, ['GET']),
)
for legacy_rule, endpoint, view, methods in LEGACY_RULES:
    app.add_url_rule(
        legacy_rule, endpoint=endpoint, view_func=view, methods=methods,
    )


@app.errorhandler(404)
def not_found(error):
    """存在しないURLに利用者向けページを返す。"""
    return render_template('error.html', message='ページが見つかりません。'), 404


@app.errorhandler(413)
def request_too_large(error):
    """大きすぎるリクエストを拒否する。"""
    return render_template(
        'error.html', message='送信されたデータが大きすぎます。'
    ), 413


if __name__ == '__main__':
    app.run(debug=True)
