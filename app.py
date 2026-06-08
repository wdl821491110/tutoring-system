"""

课消管理系统 v3.0 - 主程序

新增：登录鉴权(管理员/教师/用户)、备份恢复、小程序适配

"""

import os

import sys

import io

import zipfile

import hashlib

import secrets

import logging

import threading

import time

import webbrowser

import requests  # PyInstaller 需要顶层导入才能自动打包

from functools import wraps

from datetime import datetime, date

from flask import Flask, request, jsonify, render_template, g, send_file, after_this_request, Response

# 打包后资源路径处理

if getattr(sys, 'frozen', False):

    BASE_DIR = sys._MEIPASS

else:

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,

            template_folder=os.path.join(BASE_DIR, 'templates'),

            static_folder=os.path.join(BASE_DIR, 'static'))

app.config['JSON_AS_ASCII'] = False

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB上传限制

# 错误日志

ERROR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error.log')

logging.basicConfig(filename=ERROR_LOG, level=logging.ERROR,

                    format='%(asctime)s [%(levelname)s] %(message)s')

from database import get_db, init_db, get_data_dir, DB_PATH

# Token 存储 (内存，重启失效)

TOKENS = {}  # token -> {'user_id': id, 'role': role, 'expires': timestamp}

# ==================== 统一响应 ====================

def api_response(data=None, message='ok', code=200, http_status=200):

    body = {'code': code, 'message': message}

    if data is not None:

        body['data'] = data

    return jsonify(body), http_status

def api_error(message, code=400, http_status=400):

    return api_response(message=message, code=code, http_status=http_status)

# ==================== 运行模式检测 ====================

CLOUDBASE_API = 'https://wdl1110-d1g8w3lcf657b61fd.service.tcloudbase.com'

IS_CLOUD = bool(os.environ.get('PORT') or os.environ.get('KUBERNETES_SERVICE_HOST') or os.path.exists('/.dockerenv'))

# ==================== CORS ====================

@app.before_request

def handle_local_proxy_or_cors():

    """本地模式：/api/* 请求代理到 CloudBase；CORS 预检放行"""

    # CORS 预检处理（必须在代理之前）
    if request.method == 'OPTIONS' and request.path.startswith('/api/'):

        resp = app.make_default_options_response()

        resp.headers['Access-Control-Allow-Origin'] = '*'

        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'

        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'

        resp.headers['Access-Control-Max-Age'] = '3600'

        return resp

    # 本地 exe 模式：所有 /api/* 请求（含鉴权）转发到 CloudBase
    if not IS_CLOUD and request.path.startswith('/api/'):

        return _proxy_to_cloudbase()

def _proxy_to_cloudbase():

    """将请求转发到 CloudBase 后端"""

    target_url = CLOUDBASE_API + request.full_path.split('?')[0] if request.full_path.startswith('/api') else CLOUDBASE_API + request.path

    

    # 转发的请求头

    fwd_headers = {}

    for k, v in request.headers:

        if k.lower() in ('host', 'content-length'):

            continue

        fwd_headers[k] = v

    

    # 获取请求体

    body = request.get_data()

    

    try:

        resp = requests.request(

            method=request.method,

            url=target_url,

            headers=fwd_headers,

            data=body,

            params=request.args if request.method == 'GET' else None,

            timeout=30,

            allow_redirects=False

        )

    except requests.exceptions.RequestException as e:

        logging.error(f'代理请求失败: {e}')

        return api_error('服务器连接失败，请稍后重试', 502, 502)

    

    # 构建响应

    excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}

    resp_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

    return Response(resp.content, status=resp.status_code, headers=resp_headers)

@app.after_request

def add_cors_headers(response):

    response.headers['Access-Control-Allow-Origin'] = '*'

    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'

    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'

    # 写操作后触发云端备份（仅CloudRun环境）

    if request.method in ('POST', 'PUT', 'DELETE') and response.status_code < 400:

        if os.environ.get('TCB_API_KEY'):

            trigger_cloud_backup()

    return response

# ==================== 全局错误处理 ====================

@app.errorhandler(404)
def not_found_error(e):
    """处理 404，对 API 请求返回 JSON，对页面请求返回友好提示"""
    # 不把 favicon.ico 等常见请求记入 ERROR 日志
    logging.info(f"404: {str(e)}")
    # API 请求返回 JSON
    if request.path.startswith('/api/'):
        return api_error('请求的资源不存在', 404, 404)
    # 非 API 请求返回友好 HTML
    return '<h1>404 - 页面未找到</h1><p><a href="/">返回首页</a></p>', 404

@app.errorhandler(500)

def internal_error(e):

    logging.error(f"500: {str(e)}", exc_info=True)

    return api_error('服务器内部错误', 500, 500)

@app.errorhandler(Exception)

def handle_exception(e):
    # HTTPException（如 404/405/403）由各自的 errorhandler 处理，这里只处理真正的服务器异常
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e  # 交还给 Flask 默认处理
    logging.error(f"Exception: {str(e)}", exc_info=True)
    return api_error(f'服务器错误: {str(e)}', 500, 500)

# ==================== DB 连接 ====================

@app.before_request

def before_request():

    g.db = get_db()

@app.teardown_request

def teardown_request(exception):

    db = getattr(g, 'db', None)

    if db is not None:

        db.close()

# ==================== 鉴权系统 ====================

from werkzeug.security import generate_password_hash as _gen_pw_hash, check_password_hash

def hash_password(password):

    """密码哈希（用于存储）"""

    return _gen_pw_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(stored_hash, password):

    """验证密码"""

    return check_password_hash(stored_hash, password)

def generate_token():

    token = secrets.token_hex(32)

    while token in TOKENS:

        token = secrets.token_hex(32)

    return token

def get_current_user():

    """从请求头获取当前用户信息"""

    token = request.headers.get('Authorization', '')

    if token.startswith('Bearer '):

        token = token[7:]

    if token in TOKENS:

        user_data = TOKENS[token]

        # 检查过期 (24小时)

        if time.time() - user_data.get('created', 0) > 86400:

            del TOKENS[token]

            return None

        return user_data

    return None

def get_role_permissions(role):

    """获取指定角色的权限配置（带缓存）"""

    db = get_db()

    row = db.execute("SELECT * FROM role_permissions WHERE role = ?", (role,)).fetchone()

    if row:

        return dict(row)

    # 返回空权限（默认全部关闭）

    return {'can_manage_students':0,'can_manage_teachers':0,'can_manage_courses':0,

            'can_manage_enrollments':0,'can_create_schedules':0,'can_checkin':0,

            'can_view_all_data':0,'can_view_prices':0,'can_manage_users':0,'can_backup':0}

def get_user_permission_override(user_id):

    """获取用户权限覆盖记录（-1=使用角色默认）"""
    db = get_db()

    row = db.execute("SELECT * FROM user_permissions WHERE user_id=?", (user_id,)).fetchone()

    if row:

        return dict(row)

    return None

def get_effective_permissions(user):

    """计算用户实际权限：角色默认 → 用户覆盖"""
    role = user.get('role', 'parent')

    perms = get_role_permissions(role)

    

    # 用户个人权限覆盖优先
    override = get_user_permission_override(user.get('id'))

    if override:

        permission_fields = ['can_manage_students', 'can_manage_teachers', 'can_manage_courses',

            'can_manage_enrollments', 'can_create_schedules', 'can_checkin',

            'can_view_all_data', 'can_view_prices', 'can_manage_users', 'can_backup']

        for field in permission_fields:

            if override.get(field, -1) >= 0:

                perms[field] = override[field]

    

    perms['role'] = role

    return perms

def teacher_course_ids(db, teacher_id):

    """获取教师所教课程ID列表（含多教师课程）"""

    rows = db.execute("""

        SELECT DISTINCT c.id FROM courses c

        LEFT JOIN course_teachers ct ON c.id = ct.course_id

        WHERE c.status='active' AND (c.teacher_id = ? OR ct.teacher_id = ?)

    """, (teacher_id, teacher_id)).fetchall()

    return [r['id'] for r in rows]

def require_auth(roles=None):

    """鉴权装饰器，roles为允许的角色列表"""

    def decorator(f):

        @wraps(f)

        def decorated(*args, **kwargs):

            user = get_current_user()

            if not user:

                return api_error('请先登录', 401, 401)

            if roles and user['role'] not in roles:

                return api_error('权限不足', 403, 403)

            g.current_user = user

            return f(*args, **kwargs)

        return decorated

    return decorator

# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])

def health():

    return api_response({'version': '3.0', 'status': 'running'})

# ==================== 认证接口 ====================

@app.route('/api/auth/login', methods=['POST'])

def login():

    db = g.db

    data = request.get_json()

    username = (data.get('username') or '').strip()

    password = data.get('password') or ''

    if not username or not password:

        return api_error('请输入用户名和密码')

    user = db.execute(

        "SELECT * FROM users WHERE username=? AND status='active'", (username,)

    ).fetchone()

    if not user or not verify_password(user['password_hash'], password):

        return api_error('用户名或密码错误')

    token = generate_token()

    TOKENS[token] = {

        'user_id': user['id'],

        'username': user['username'],

        'role': user['role'],

        'real_name': user['real_name'] or user['username'],

        'linked_student_id': user['linked_student_id'],

        'linked_teacher_id': user['linked_teacher_id'],

        'created': time.time()

    }

    return api_response(data={

        'token': token,

        'user': {

            'id': user['id'],

            'username': user['username'],

            'role': user['role'],

            'real_name': user['real_name'],

            'linked_student_id': user['linked_student_id'],

            'linked_teacher_id': user['linked_teacher_id']

        }

    }, message='登录成功')

@app.route('/api/auth/logout', methods=['POST'])

def logout():

    token = request.headers.get('Authorization', '')

    if token.startswith('Bearer '):

        token = token[7:]

    TOKENS.pop(token, None)

    return api_response(message='已退出')

@app.route('/api/auth/me', methods=['GET'])

@require_auth()

def get_me():

    u = g.current_user

    return api_response(data={

        'user_id': u['user_id'], 'username': u['username'],

        'role': u['role'], 'real_name': u['real_name'],

        'linked_student_id': u.get('linked_student_id'),

        'linked_teacher_id': u.get('linked_teacher_id')

    })

@app.route('/api/auth/register', methods=['POST'])

def register():

    """注册（仅限教师角色）"""

    db = g.db

    data = request.get_json()

    username = (data.get('username') or '').strip()

    password = data.get('password') or ''

    role = data.get('role', 'teacher')

    if not username or not password:

        return api_error('请输入用户名和密码')

    if len(password) < 6:

        return api_error('密码至少6位')

    if role != 'teacher':

        return api_error('仅支持教师角色注册，管理员账号请联系机构创建')

    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()

    if existing:

        return api_error('用户名已存在')

    db.execute("""

        INSERT INTO users (username, password_hash, role, real_name, phone)

        VALUES (?, ?, ?, ?, ?)

    """, (username, hash_password(password), role, data.get('real_name', username),

          data.get('phone', '')))

    db.commit()

    return api_response(message='注册成功，请联系管理员激活账号')

# ==================== 用户管理（管理员端） ====================

@app.route('/api/users', methods=['GET'])

@require_auth(['admin'])

def get_users():

    db = g.db

    users = db.execute("""

        SELECT u.*, s.name as student_name, t.name as teacher_name

        FROM users u

        LEFT JOIN students s ON u.linked_student_id = s.id

        LEFT JOIN teachers t ON u.linked_teacher_id = t.id

        ORDER BY u.created_at DESC

    """).fetchall()

    return api_response(data=[dict(u) for u in users])

@app.route('/api/users', methods=['POST'])

@require_auth(['admin'])

def create_user():

    db = g.db

    data = request.get_json()

    username = (data.get('username') or '').strip()

    password = data.get('password') or '123456'

    role = data.get('role', 'teacher')

    if not username:

        return api_error('请输入用户名')

    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()

    if existing:

        return api_error('用户名已存在')

    db.execute("""

        INSERT INTO users (username, password_hash, role, real_name, phone,

                           linked_student_id, linked_teacher_id, status)

        VALUES (?, ?, ?, ?, ?, ?, ?, 'active')

    """, (username, hash_password(password), role, data.get('real_name', username),

          data.get('phone', ''), data.get('linked_student_id'), data.get('linked_teacher_id')))

    db.commit()

    return api_response(data={'username': username, 'password': password}, message='创建成功')

@app.route('/api/users/<int:uid>', methods=['PUT'])

@require_auth(['admin'])

def update_user(uid):

    db = g.db

    data = request.get_json()

    u = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    if not u:

        return api_error('用户不存在', 404, 404)

    updates = []

    params = []

    for field in ['real_name', 'phone', 'role', 'status', 'linked_student_id', 'linked_teacher_id']:

        if field in data:

            updates.append(f"{field}=?")

            params.append(data[field])

    if data.get('password'):

        updates.append("password_hash=?")

        params.append(hash_password(data['password']))

    if updates:

        params.append(uid)

        db.execute(f"UPDATE users SET {','.join(updates)} WHERE id=?", params)

        db.commit()

    return api_response(message='更新成功')

@app.route('/api/users/<int:uid>', methods=['DELETE'])

@require_auth(['admin'])

def delete_user(uid):

    db = g.db

    db.execute("DELETE FROM users WHERE id=? AND role!='admin'", (uid,))

    db.commit()

    return api_response(message='已删除')

# ==================== 首页 ====================

@app.route('/')

def index():

    return render_template('index.html')

# ==================== 仪表盘 ====================

@app.route('/api/dashboard', methods=['GET'])

def dashboard():

    db = g.db

    user = get_current_user()

    today = date.today().isoformat()

    # 权限过滤

    student_filter = ""

    teacher_filter = ""

    params = []

    if user and user['role'] == 'teacher' and user.get('linked_teacher_id'):

        teacher_filter = " AND (s.teacher_id = ? OR cr.teacher_id = ?)"

        params = [user['linked_teacher_id'], user['linked_teacher_id']]

    elif user and user['role'] == 'parent' and user.get('linked_student_id'):

        student_filter = " AND e.student_id = ?"

        params = [user['linked_student_id']]

    total_students = db.execute(f"SELECT COUNT(*) as c FROM students WHERE status='active'{student_filter}",

                                params).fetchone()['c']

    total_teachers = db.execute("SELECT COUNT(*) as c FROM teachers WHERE status='active'").fetchone()['c']

    total_courses = db.execute("SELECT COUNT(*) as c FROM courses WHERE status='active'").fetchone()['c']

    today_schedules = db.execute(f"""

        SELECT s.*, st.name as student_name, c.name as course_name, c.subject, t.name as teacher_name

        FROM schedules s

        JOIN students st ON s.student_id = st.id

        JOIN courses c ON s.course_id = c.id

        LEFT JOIN teachers t ON s.teacher_id = t.id

        WHERE s.schedule_date = ?{teacher_filter}

        ORDER BY s.start_time

    """, [today] + params).fetchall()

    today_consumed = db.execute(f"""

        SELECT COALESCE(SUM(hours_consumed), 0) as total

        FROM class_records cr WHERE record_date = ?{teacher_filter}

    """, [today] + params).fetchone()['total']

    total_remaining = db.execute(f"""

        SELECT COALESCE(SUM(remaining_hours), 0) as total

        FROM enrollments e WHERE status = 'active'{student_filter}

    """, params).fetchone()['total']

    daily_stats = db.execute(f"""

        WITH RECURSIVE dates(d) AS (

            SELECT date('now', '-6 days', 'localtime')

            UNION ALL SELECT date(d, '+1 day') FROM dates WHERE d < date('now', 'localtime')

        )

        SELECT dates.d as record_date, COALESCE(SUM(cr.hours_consumed), 0) as total

        FROM dates LEFT JOIN class_records cr ON cr.record_date = dates.d{teacher_filter}

        GROUP BY dates.d ORDER BY dates.d

    """, params).fetchall()

    course_ranking = db.execute(f"""

        SELECT c.name, c.subject, COALESCE(SUM(cr.hours_consumed), 0) as total_hours

        FROM courses c

        LEFT JOIN class_records cr ON c.id = cr.course_id

            AND cr.record_date >= date('now', '-30 days', 'localtime')

        WHERE c.status = 'active' GROUP BY c.id ORDER BY total_hours DESC LIMIT 10

    """).fetchall()

    return api_response(data={

        'total_students': total_students, 'total_teachers': total_teachers,

        'total_courses': total_courses, 'today_count': len(today_schedules),

        'today_consumed': today_consumed, 'total_remaining': total_remaining,

        'today_schedules': [dict(r) for r in today_schedules],

        'daily_stats': [dict(r) for r in daily_stats],

        'course_ranking': [dict(r) for r in course_ranking]

    })

# ==================== 辅助函数 ====================

def get_course_teacher_names(db, course_id):

    rows = db.execute("SELECT t.name FROM course_teachers ct JOIN teachers t ON ct.teacher_id = t.id WHERE ct.course_id = ?", (course_id,)).fetchall()

    return ', '.join(r['name'] for r in rows) if rows else ''

def get_course_teacher_ids(db, course_id):

    return [r['teacher_id'] for r in db.execute("SELECT teacher_id FROM course_teachers WHERE course_id = ?", (course_id,)).fetchall()]

def sync_course_teachers(db, course_id, teacher_ids):

    db.execute("DELETE FROM course_teachers WHERE course_id = ?", (course_id,))

    for tid in (teacher_ids or []):

        if tid:

            db.execute("INSERT OR IGNORE INTO course_teachers (course_id, teacher_id) VALUES (?, ?)", (course_id, int(tid)))

    first = int(teacher_ids[0]) if teacher_ids else None

    db.execute("UPDATE courses SET teacher_id = ? WHERE id = ?", (first, course_id))

# ==================== 学生管理 ====================

@app.route('/api/students', methods=['GET'])

def get_students():

    db = g.db

    user = get_current_user()

    search = request.args.get('search', '')

    status = request.args.get('status', 'active')

    if user and user['role'] == 'parent' and user.get('linked_student_id'):

        students = db.execute("SELECT * FROM students WHERE id=? AND status='active'",

                              (user['linked_student_id'],)).fetchall()

    elif search:

        students = db.execute("""

            SELECT * FROM students WHERE status = ? AND (name LIKE ? OR school LIKE ? OR parent_phone LIKE ?)

            ORDER BY updated_at DESC

        """, (status, f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()

    else:

        students = db.execute("SELECT * FROM students WHERE status = ? ORDER BY updated_at DESC",

                              (status,)).fetchall()

    result = []

    for s in students:

        row = dict(s)

        enrollments = db.execute("""

            SELECT e.*, c.name as course_name, c.subject

            FROM enrollments e JOIN courses c ON e.course_id = c.id

            WHERE e.student_id = ? AND e.status = 'active'

        """, (s['id'],)).fetchall()

        row['enrollments'] = [dict(e) for e in enrollments]

        row['total_remaining'] = sum(e['remaining_hours'] for e in enrollments)

        result.append(row)

    return api_response(data=result)

@app.route('/api/students/<int:sid>', methods=['GET'])

def get_student(sid):

    db = g.db

    s = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    if not s:

        return api_error('学生不存在', 404, 404)

    row = dict(s)

    row['enrollments'] = [dict(e) for e in db.execute("""

        SELECT e.*, c.name as course_name, c.subject FROM enrollments e

        JOIN courses c ON e.course_id = c.id WHERE e.student_id = ?

    """, (sid,)).fetchall()]

    row['recent_records'] = [dict(r) for r in db.execute("""

        SELECT cr.*, c.name as course_name, c.subject, t.name as teacher_name

        FROM class_records cr JOIN courses c ON cr.course_id = c.id

        LEFT JOIN teachers t ON cr.teacher_id = t.id

        WHERE cr.student_id = ? ORDER BY cr.record_date DESC LIMIT 50

    """, (sid,)).fetchall()]

    return api_response(data=row)

@app.route('/api/students', methods=['POST'])

@require_auth(['admin', 'teacher'])

def create_student():

    db = g.db

    data = request.get_json()

    if not data.get('name'):

        return api_error('请填写姓名')

    cursor = db.execute("""INSERT INTO students (name, gender, grade, school, parent_name, parent_phone, address, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",

                        (data['name'], data.get('gender', '男'), data.get('grade', ''), data.get('school', ''),

                         data.get('parent_name', ''), data.get('parent_phone', ''), data.get('address', ''), data.get('notes', '')))

    db.commit()

    return api_response(data={'id': cursor.lastrowid}, message='添加成功')

@app.route('/api/students/<int:sid>', methods=['PUT'])

@require_auth(['admin', 'teacher'])

def update_student(sid):

    db = g.db

    data = request.get_json()

    s = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    if not s: return api_error('学生不存在', 404, 404)

    db.execute("""UPDATE students SET name=?, gender=?, grade=?, school=?, parent_name=?, parent_phone=?, address=?, notes=?, updated_at=datetime('now','localtime') WHERE id=?""",

               (data.get('name', s['name']), data.get('gender', s['gender']), data.get('grade', s['grade']),

                data.get('school', s['school']), data.get('parent_name', s['parent_name']),

                data.get('parent_phone', s['parent_phone']), data.get('address', s['address']),

                data.get('notes', s['notes']), sid))

    db.commit()

    return api_response(message='更新成功')

@app.route('/api/students/<int:sid>', methods=['DELETE'])

@require_auth(['admin', 'teacher'])

def delete_student(sid):

    db = g.db

    db.execute("UPDATE students SET status='inactive', updated_at=datetime('now','localtime') WHERE id=?", (sid,))

    db.commit()

    return api_response(message='已停用')

# ==================== 教师管理 ====================

@app.route('/api/teachers', methods=['GET'])

def get_teachers():

    db = g.db

    search = request.args.get('search', '')

    status = request.args.get('status', 'active')

    if search:

        teachers = db.execute("SELECT * FROM teachers WHERE status = ? AND (name LIKE ? OR phone LIKE ? OR subjects LIKE ?) ORDER BY updated_at DESC",

                              (status, f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()

    else:

        teachers = db.execute("SELECT * FROM teachers WHERE status = ? ORDER BY updated_at DESC", (status,)).fetchall()

    result = []

    for t in teachers:

        row = dict(t)

        row['course_count'] = db.execute("SELECT COUNT(*) as c FROM course_teachers WHERE teacher_id = ?", (t['id'],)).fetchone()['c']

        result.append(row)

    return api_response(data=result)

@app.route('/api/teachers', methods=['POST'])

@require_auth(['admin'])

def create_teacher():

    db = g.db

    data = request.get_json()

    if not data.get('name'): return api_error('请填写姓名')

    cursor = db.execute("INSERT INTO teachers (name, gender, phone, subjects, notes) VALUES (?, ?, ?, ?, ?)",

                        (data['name'], data.get('gender', '男'), data.get('phone', ''), data.get('subjects', ''), data.get('notes', '')))

    db.commit()

    return api_response(data={'id': cursor.lastrowid}, message='添加成功')

@app.route('/api/teachers/<int:tid>', methods=['PUT'])

@require_auth(['admin'])

def update_teacher(tid):

    db = g.db

    data = request.get_json()

    t = db.execute("SELECT * FROM teachers WHERE id = ?", (tid,)).fetchone()

    if not t: return api_error('教师不存在', 404, 404)

    db.execute("UPDATE teachers SET name=?, gender=?, phone=?, subjects=?, notes=?, updated_at=datetime('now','localtime') WHERE id=?",

               (data.get('name', t['name']), data.get('gender', t['gender']), data.get('phone', t['phone']),

                data.get('subjects', t['subjects']), data.get('notes', t['notes']), tid))

    db.commit()

    return api_response(message='更新成功')

@app.route('/api/teachers/<int:tid>', methods=['DELETE'])

@require_auth(['admin'])

def delete_teacher(tid):
    db = g.db
    db.execute("UPDATE teachers SET status='inactive', updated_at=datetime('now','localtime') WHERE id=?", (tid,))
    db.commit()

    return api_response(message='已停用')

# ==================== 课程管理（多教师） ====================

@app.route('/api/courses', methods=['GET'])

def get_courses():

    db = g.db

    user = get_current_user()

    search = request.args.get('search', '')

    # 教师角色：仅显示自己教授的课程

    if user and user['role'] == 'teacher' and user.get('linked_teacher_id'):

        tid = user['linked_teacher_id']

        if search:

            courses = db.execute("""

                SELECT DISTINCT c.* FROM courses c

                LEFT JOIN course_teachers ct ON c.id = ct.course_id

                WHERE c.status='active' AND (c.name LIKE ? OR c.subject LIKE ?)

                AND (c.teacher_id = ? OR ct.teacher_id = ?)

                ORDER BY c.updated_at DESC

            """, (f'%{search}%', f'%{search}%', tid, tid)).fetchall()

        else:

            courses = db.execute("""

                SELECT DISTINCT c.* FROM courses c

                LEFT JOIN course_teachers ct ON c.id = ct.course_id

                WHERE c.status='active' AND (c.teacher_id = ? OR ct.teacher_id = ?)

                ORDER BY c.updated_at DESC

            """, (tid, tid)).fetchall()

    elif search:

        courses = db.execute("SELECT c.* FROM courses c WHERE c.status='active' AND (c.name LIKE ? OR c.subject LIKE ?) ORDER BY c.updated_at DESC",

                             (f'%{search}%', f'%{search}%')).fetchall()

    else:

        courses = db.execute("SELECT c.* FROM courses c WHERE c.status = 'active' ORDER BY c.updated_at DESC").fetchall()

    result = []

    for c in courses:

        row = dict(c)

        row['teacher_names'] = get_course_teacher_names(db, c['id'])

        # 教师角色：隐藏课程单价
        if user and user['role'] == 'teacher':            row.pop('price_per_hour', None)

        row['teacher_ids'] = get_course_teacher_ids(db, c['id'])

        row['student_count'] = db.execute("SELECT COUNT(DISTINCT student_id) as c FROM enrollments WHERE course_id = ? AND status = 'active'", (c['id'],)).fetchone()['c']

        result.append(row)

    return api_response(data=result)

@app.route('/api/courses', methods=['POST'])

@require_auth(['admin'])

def create_course():

    db = g.db

    data = request.get_json()

    if not data.get('name'): return api_error('请填写课程名称')

    cursor = db.execute("INSERT INTO courses (name, subject, price_per_hour, total_hours, notes) VALUES (?, ?, ?, ?, ?)",

                        (data['name'], data.get('subject', ''), data.get('price_per_hour', 0), data.get('total_hours', 0), data.get('notes', '')))

    sync_course_teachers(db, cursor.lastrowid, data.get('teacher_ids', []))

    db.commit()

    return api_response(data={'id': cursor.lastrowid}, message='添加成功')

@app.route('/api/courses/<int:cid>', methods=['PUT'])

@require_auth(['admin'])

def update_course(cid):

    db = g.db

    data = request.get_json()

    c = db.execute("SELECT * FROM courses WHERE id = ?", (cid,)).fetchone()

    if not c: return api_error('课程不存在', 404, 404)

    db.execute("UPDATE courses SET name=?, subject=?, price_per_hour=?, total_hours=?, notes=?, updated_at=datetime('now','localtime') WHERE id=?",

               (data.get('name', c['name']), data.get('subject', c['subject']), data.get('price_per_hour', c['price_per_hour']),

                data.get('total_hours', c['total_hours']), data.get('notes', c['notes']), cid))

    sync_course_teachers(db, cid, data.get('teacher_ids', get_course_teacher_ids(db, cid)))

    db.commit()

    return api_response(message='更新成功')

@app.route('/api/courses/<int:cid>', methods=['DELETE'])

@require_auth(['admin'])

def delete_course(cid):

    g.db.execute("UPDATE courses SET status='inactive', updated_at=datetime('now','localtime') WHERE id=?", (cid,))

    g.db.commit()

    return api_response(message='已停用')

# ==================== 报名管理 ====================

@app.route('/api/enrollments', methods=['GET'])

def get_enrollments():
    try:
        result = []
        db = g.db

        user = get_current_user()

        status = request.args.get('status', 'active')

        if user and user['role'] == 'parent' and user.get('linked_student_id'):

            enrollments = db.execute("""

                SELECT e.*, s.name as student_name, s.grade, s.school, c.name as course_name, c.subject, c.price_per_hour

                FROM enrollments e JOIN students s ON e.student_id = s.id JOIN courses c ON e.course_id = c.id

                WHERE e.student_id = ? AND e.status = ? ORDER BY e.enrolled_date DESC

            """, (user['linked_student_id'], status)).fetchall()

        elif user and user['role'] == 'teacher' and user.get('linked_teacher_id'):

            # 教师仅能看到自己教授的课程的报名

            cids = teacher_course_ids(db, user['linked_teacher_id'])

            if cids:

                placeholders = ','.join('?' * len(cids))

                enrollments = db.execute(f"""

                    SELECT e.*, s.name as student_name, s.grade, s.school, c.name as course_name, c.subject, c.price_per_hour

                    FROM enrollments e JOIN students s ON e.student_id = s.id JOIN courses c ON e.course_id = c.id

                    WHERE e.course_id IN ({placeholders}) AND e.status = ? ORDER BY e.enrolled_date DESC

                """, cids + [status]).fetchall()

            else:

                enrollments = []

        else:

            enrollments = db.execute("""

                SELECT e.*, s.name as student_name, s.grade, s.school, c.name as course_name, c.subject, c.price_per_hour

                FROM enrollments e JOIN students s ON e.student_id = s.id JOIN courses c ON e.course_id = c.id

                WHERE e.status = ? ORDER BY e.enrolled_date DESC

            """, (status,)).fetchall()

        result = []
        for e in enrollments:

            row = dict(e)

            row['teacher_names'] = get_course_teacher_names(db, e['course_id'])

            # 教师角色：隐藏课程单价
            if user and user['role'] == 'teacher':
                row.pop('price_per_hour', None)

                row.pop('amount_paid', None)

            result.append(row)

    except Exception as ex:
        logging.error(f'enrollments error: {ex}')
        return api_response(data=result)
    return api_response(data=result)

@app.route('/api/enrollments', methods=['POST'])

@require_auth(['admin'])

def create_enrollment():

    db = g.db

    data = request.get_json()

    if not data.get('student_id') or not data.get('course_id'):

        return api_error('请选择学生和课程')

    purchased = int(data.get('purchased_hours', 0))

    existing = db.execute("SELECT * FROM enrollments WHERE student_id=? AND course_id=? AND status='active'",

                          (data['student_id'], data['course_id'])).fetchone()

    if existing:

        new_p = existing['purchased_hours'] + purchased

        new_r = existing['remaining_hours'] + purchased

        db.execute("UPDATE enrollments SET purchased_hours=?, remaining_hours=?, amount_paid=amount_paid+?, notes=notes || '; ' || ? WHERE id=?",

                   (new_p, new_r, data.get('amount_paid', 0), f"追加{purchased}课时", existing['id']))

        db.commit()

        return api_response(data={'id': existing['id']}, message='课时追加成功')

    cursor = db.execute("""INSERT INTO enrollments (student_id, course_id, purchased_hours, consumed_hours, remaining_hours, amount_paid, enrolled_date, notes) VALUES (?, ?, ?, 0, ?, ?, ?, ?)""",

                        (data['student_id'], data['course_id'], purchased, purchased, data.get('amount_paid', 0),

                         data.get('enrolled_date', date.today().isoformat()), data.get('notes', '')))

    db.commit()

    return api_response(data={'id': cursor.lastrowid}, message='报名成功')

@app.route('/api/enrollments/<int:eid>', methods=['PUT'])

@require_auth(['admin'])

def update_enrollment(eid):

    db = g.db

    data = request.get_json()

    e = db.execute("SELECT * FROM enrollments WHERE id = ?", (eid,)).fetchone()

    if not e: return api_error('记录不存在', 404, 404)

    new_purchased = data.get('purchased_hours', e['purchased_hours'])

    delta = new_purchased - e['purchased_hours']

    new_remaining = max(e['consumed_hours'], e['remaining_hours'] + delta)

    db.execute("UPDATE enrollments SET purchased_hours=?, remaining_hours=?, amount_paid=?, notes=?, status=? WHERE id=?",

               (new_purchased, new_remaining, data.get('amount_paid', e['amount_paid']),

                data.get('notes', e['notes']), data.get('status', e['status']), eid))

    db.commit()

    return api_response(message='更新成功')

@app.route('/api/enrollments/<int:eid>', methods=['DELETE'])

@require_auth(['admin'])

def delete_enrollment(eid):

    g.db.execute("UPDATE enrollments SET status='inactive' WHERE id=?", (eid,))

    g.db.commit()

    return api_response(message='已取消报名')

# ==================== 排课管理 ====================

@app.route('/api/schedules', methods=['GET'])

def get_schedules():

    db = g.db

    user = get_current_user()

    params = []

    query = """SELECT s.*, st.name as student_name, st.grade, c.name as course_name, c.subject, t.name as teacher_name

               FROM schedules s JOIN students st ON s.student_id = st.id JOIN courses c ON s.course_id = c.id

               LEFT JOIN teachers t ON s.teacher_id = t.id WHERE 1=1"""

    if user and user['role'] == 'teacher' and user.get('linked_teacher_id'):

        query += " AND s.teacher_id = ?"; params.append(user['linked_teacher_id'])

    elif user and user['role'] == 'parent' and user.get('linked_student_id'):

        query += " AND s.student_id = ?"; params.append(user['linked_student_id'])

    for key, col in [('status','s.status'), ('date_from','s.schedule_date'), ('date_to','s.schedule_date'),

                     ('student_id','s.student_id'), ('teacher_id','s.teacher_id')]:

        val = request.args.get(key, '')

        if val:

            if key in ('date_from',): query += f" AND {col} >= ?"; params.append(val)

            elif key in ('date_to',): query += f" AND {col} <= ?"; params.append(val)

            else: query += f" AND {col} = ?"; params.append(val)

    query += " ORDER BY s.schedule_date DESC, s.start_time DESC"

    return api_response(data=[dict(s) for s in db.execute(query, params).fetchall()])

@app.route('/api/schedules', methods=['POST'])

@require_auth(['admin', 'teacher'])

def create_schedule():

    db = g.db

    user = g.current_user

    data = request.get_json()

    # 教师角色需检查是否有排课权限

    if user['role'] == 'teacher':

        perms = get_role_permissions('teacher')

        if not perms.get('can_create_schedules'):

            return api_error('无排课权限，请联系管理员开通', 403, 403)

    if not data.get('student_id') or not data.get('course_id'):

        return api_error('请选择学生和课程')

    enrollment = db.execute("SELECT * FROM enrollments WHERE student_id=? AND course_id=? AND status='active'",

                            (data['student_id'], data['course_id'])).fetchone()

    if not enrollment: return api_error('该学生未报名此课程')

    hours = int(data.get('hours', 1))

    if enrollment['remaining_hours'] < hours: return api_error(f'剩余课时不足({enrollment["remaining_hours"]})')

    course = db.execute("SELECT * FROM courses WHERE id=?", (data['course_id'],)).fetchone()

    teacher_id = data.get('teacher_id') or (user['linked_teacher_id'] if user['role'] == 'teacher' else course['teacher_id'])

    cursor = db.execute("""INSERT INTO schedules (enrollment_id, student_id, course_id, teacher_id, schedule_date, start_time, end_time, hours, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                        (enrollment['id'], data['student_id'], data['course_id'], teacher_id, data['schedule_date'],

                         data['start_time'], data['end_time'], hours, data.get('notes', '')))

    db.commit()

    return api_response(data={'id': cursor.lastrowid}, message='排课成功')

@app.route('/api/schedules/<int:sid>', methods=['PUT'])

@require_auth(['admin', 'teacher'])

def update_schedule(sid):

    db = g.db

    data = request.get_json()

    s = db.execute("SELECT * FROM schedules WHERE id = ?", (sid,)).fetchone()

    if not s: return api_error('排课记录不存在', 404, 404)

    db.execute("UPDATE schedules SET schedule_date=?, start_time=?, end_time=?, hours=?, status=?, notes=? WHERE id=?",

               (data.get('schedule_date', s['schedule_date']), data.get('start_time', s['start_time']),

                data.get('end_time', s['end_time']), data.get('hours', s['hours']),

                data.get('status', s['status']), data.get('notes', s['notes']), sid))

    db.commit()

    return api_response(message='更新成功')

@app.route('/api/schedules/<int:sid>/cancel', methods=['POST'])
@app.route('/api/schedules/<int:sid>', methods=['DELETE'])

@require_auth(['admin', 'teacher'])

def cancel_schedule(sid):

    g.db.execute("UPDATE schedules SET status='cancelled' WHERE id=?", (sid,))

    g.db.commit()

    return api_response(message='已取消排课')

# ==================== 课时记录 ====================

@app.route('/api/records', methods=['GET'])

def get_records():

    db = g.db

    user = get_current_user()

    params = []

    query = """FROM class_records cr JOIN students s ON cr.student_id = s.id JOIN courses c ON cr.course_id = c.id

               LEFT JOIN teachers t ON cr.teacher_id = t.id WHERE 1=1"""

    if user and user['role'] == 'teacher' and user.get('linked_teacher_id'):

        query += " AND cr.teacher_id = ?"; params.append(user['linked_teacher_id'])

    elif user and user['role'] == 'parent' and user.get('linked_student_id'):

        query += " AND cr.student_id = ?"; params.append(user['linked_student_id'])

    for key, col in [('date_from','cr.record_date'), ('date_to','cr.record_date'),

                     ('student_id','cr.student_id'), ('course_id','cr.course_id'), ('teacher_id','cr.teacher_id')]:

        val = request.args.get(key, '')

        if val:

            if key == 'date_from': query += f" AND {col} >= ?"; params.append(val)

            elif key == 'date_to': query += f" AND {col} <= ?"; params.append(val)

            else: query += f" AND {col} = ?"; params.append(val)

    page = int(request.args.get('page', 1))

    per_page = int(request.args.get('per_page', 50))

    count = db.execute(f"SELECT COUNT(*) as c {query}", params).fetchone()['c']

    records = db.execute(f"""SELECT cr.*, s.name as student_name, s.grade, s.school, s.parent_name, s.parent_phone,

               s.gender as student_gender, c.name as course_name, c.subject, t.name as teacher_name,

               (SELECT COUNT(*) FROM class_record_notes WHERE record_id = cr.id) as note_count

               {query} ORDER BY cr.record_date DESC, cr.created_at DESC LIMIT ? OFFSET ?""",

                         params + [per_page, (page - 1) * per_page]).fetchall()

    return api_response(data={'records': [dict(r) for r in records], 'total': count, 'page': page,

                              'per_page': per_page, 'total_pages': (count + per_page - 1) // per_page})

@app.route('/api/records', methods=['POST'])

@require_auth(['admin', 'teacher'])

def create_record():

    db = g.db

    data = request.get_json()

    schedule_id = data.get('schedule_id')

    student_id = data.get('student_id')

    course_id = data.get('course_id')

    hours = int(data.get('hours_consumed', 1))

    if schedule_id:

        schedule = db.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()

        if not schedule: return api_error('排课记录不存在', 404, 404)

        student_id = schedule['student_id']; course_id = schedule['course_id']

        # 如果前端未显式传入 hours_consumed，使用排课中登记的课时数

        if 'hours_consumed' not in data:

            hours = schedule['hours']

    if not student_id or not course_id: return api_error('请选择学生和课程')

    enrollment = db.execute("SELECT * FROM enrollments WHERE student_id=? AND course_id=? AND status='active'",

                            (student_id, course_id)).fetchone()

    if not enrollment: return api_error('该学生未报名此课程')

    if enrollment['remaining_hours'] < hours: return api_error(f'剩余课时不足({enrollment["remaining_hours"]})')

    rb = enrollment['remaining_hours']; ra = rb - hours

    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()

    teacher_id = data.get('teacher_id') or course['teacher_id']

    cursor = db.execute("""INSERT INTO class_records (schedule_id, student_id, course_id, teacher_id, record_date,

               hours_consumed, remaining_before, remaining_after, attendance, notes)

               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                        (schedule_id, student_id, course_id, teacher_id,

                         data.get('record_date', date.today().isoformat()), hours, rb, ra,

                         data.get('attendance', 'present'), data.get('notes', '')))

    db.execute("UPDATE enrollments SET consumed_hours=consumed_hours+?, remaining_hours=remaining_hours-? WHERE id=?",

               (hours, hours, enrollment['id']))

    if schedule_id: db.execute("UPDATE schedules SET status='completed' WHERE id=?", (schedule_id,))

    db.commit()

    return api_response(data={'id': cursor.lastrowid, 'remaining_after': ra}, message='消课成功')

@app.route('/api/records/batch-consume', methods=['POST'])

@require_auth(['admin', 'teacher'])

def batch_consume():

    db = g.db

    data = request.get_json()

    items = data.get('items', [])

    if not items: return api_error('请选择要消课的学生')

    success, failed = [], []

    for item in items:

        sid = item.get('student_id'); cid = item.get('course_id')

        hours = int(item.get('hours', 1)); sname = item.get('student_name', f'#{sid}')

        enrollment = db.execute("SELECT * FROM enrollments WHERE student_id=? AND course_id=? AND status='active'",

                                (sid, cid)).fetchone()

        if not enrollment: failed.append(f'{sname}: 未报名'); continue

        if enrollment['remaining_hours'] < hours: failed.append(f'{sname}: 课时不足'); continue

        rb = enrollment['remaining_hours']; ra = rb - hours

        course = db.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()

        tid = item.get('teacher_id') or course['teacher_id']

        db.execute("""INSERT INTO class_records (student_id, course_id, teacher_id, record_date, hours_consumed, remaining_before, remaining_after, attendance, notes)

                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                   (sid, cid, tid, item.get('record_date', date.today().isoformat()), hours, rb, ra,

                    item.get('attendance', 'present'), item.get('notes', '')))

        db.execute("UPDATE enrollments SET consumed_hours=consumed_hours+?, remaining_hours=remaining_hours-? WHERE id=?",

                   (hours, hours, enrollment['id']))

        success.append(f'{sname}: -{hours}课时, 剩余{ra}')

    db.commit()

    return api_response(data={'success_count': len(success), 'fail_count': len(failed),

                              'success_list': success, 'fail_list': failed},

                        message=f'成功消课 {len(success)} 人' if success else '全部失败')

@app.route('/api/records/<int:rid>', methods=['DELETE'])
@app.route('/api/records/<int:rid>/undo', methods=['POST'])

@require_auth(['admin'])

def delete_record(rid):

    db = g.db

    record = db.execute("SELECT * FROM class_records WHERE id=?", (rid,)).fetchone()

    if not record: return api_error('记录不存在', 404, 404)

    enrollment = db.execute("SELECT * FROM enrollments WHERE student_id=? AND course_id=? AND status='active'",

                            (record['student_id'], record['course_id'])).fetchone()

    if enrollment:

        db.execute("UPDATE enrollments SET consumed_hours=consumed_hours-?, remaining_hours=remaining_hours+? WHERE id=?",

                   (record['hours_consumed'], record['hours_consumed'], enrollment['id']))

    if record['schedule_id']: db.execute("UPDATE schedules SET status='scheduled' WHERE id=?", (record['schedule_id'],))

    db.execute("DELETE FROM class_records WHERE id=?", (rid,))

    db.commit()

    return api_response(message='消课记录已撤销')

@app.route('/api/records/stats', methods=['GET'])

def record_stats():

    db = g.db

    period = request.args.get('period', 'month')

    filters = {'today': "cr.record_date = date('now', 'localtime')",

               'week': "cr.record_date >= date('now', '-7 days', 'localtime')",

               'month': "cr.record_date >= date('now', 'start of month', 'localtime')"}

    df = filters.get(period, filters['month'])

    total = dict(db.execute(f"""SELECT COUNT(*) as record_count, COALESCE(SUM(hours_consumed),0) as total_hours,

               COUNT(DISTINCT student_id) as student_count FROM class_records cr WHERE {df}""").fetchone())

    by_course = [dict(r) for r in db.execute(f"""SELECT c.name, c.subject, COUNT(*) as record_count, SUM(cr.hours_consumed) as total_hours

               FROM class_records cr JOIN courses c ON cr.course_id = c.id WHERE {df} GROUP BY cr.course_id ORDER BY total_hours DESC""").fetchall()]

    return api_response(data={'total': total, 'by_course': by_course})

@app.route('/api/records/batch-checkin', methods=['POST'])

@require_auth(['admin', 'teacher'])

def batch_checkin():

    db = g.db

    schedule_ids = request.get_json().get('schedule_ids', [])

    if not schedule_ids: return api_error('请选择课程')

    success, failed = 0, []

    for sid in schedule_ids:

        s = db.execute("SELECT * FROM schedules WHERE id=? AND status='scheduled'", (sid,)).fetchone()

        if not s: failed.append(f'#{sid} 不可签到'); continue

        e = db.execute("SELECT * FROM enrollments WHERE student_id=? AND course_id=? AND status='active'",

                       (s['student_id'], s['course_id'])).fetchone()

        if not e or e['remaining_hours'] < s['hours']: failed.append(f'{s["student_id"]} 课时不足'); continue

        rb = e['remaining_hours']; ra = rb - s['hours']

        db.execute("""INSERT INTO class_records (schedule_id, student_id, course_id, teacher_id, record_date, hours_consumed, remaining_before, remaining_after, attendance)

                      VALUES (?, ?, ?, ?, date('now','localtime'), ?, ?, ?, 'present')""",

                   (sid, s['student_id'], s['course_id'], s['teacher_id'], s['hours'], rb, ra))

        db.execute("UPDATE enrollments SET consumed_hours=consumed_hours+?, remaining_hours=remaining_hours-? WHERE id=?",

                   (s['hours'], s['hours'], e['id']))

        db.execute("UPDATE schedules SET status='completed' WHERE id=?", (sid,))

        success += 1

    db.commit()

    return api_response(data={'success_count': success, 'fail_count': len(failed), 'fail_list': failed}, message=f'成功 {success} 条')

@app.route('/api/students/active-with-enrollments', methods=['GET'])

def active_students():

    db = g.db

    user = get_current_user()

    if user and user['role'] == 'parent' and user.get('linked_student_id'):

        rows = db.execute("""SELECT e.*, s.name as student_name, s.grade, c.name as course_name, c.subject

               FROM enrollments e JOIN students s ON e.student_id = s.id JOIN courses c ON e.course_id = c.id

               WHERE e.status='active' AND s.status='active' AND e.remaining_hours > 0 AND e.student_id = ?

               ORDER BY s.name""", (user['linked_student_id'],)).fetchall()

    else:

        rows = db.execute("""SELECT e.*, s.name as student_name, s.grade, c.name as course_name, c.subject

               FROM enrollments e JOIN students s ON e.student_id = s.id JOIN courses c ON e.course_id = c.id

               WHERE e.status='active' AND s.status='active' AND e.remaining_hours > 0 ORDER BY s.name""").fetchall()

    return api_response(data=[dict(r) for r in rows])

# ==================== 课时记录备注 ====================

@app.route('/api/records/<int:rid>/notes', methods=['GET'])

@require_auth(['admin', 'teacher'])

def get_record_notes(rid):

    db = g.db

    notes = db.execute("SELECT * FROM class_record_notes WHERE record_id = ? ORDER BY created_at DESC", (rid,)).fetchall()

    return api_response(data=[dict(n) for n in notes])

@app.route('/api/records/<int:rid>/notes', methods=['POST'])

@require_auth(['admin', 'teacher'])

def add_record_note(rid):

    db = g.db

    user = g.current_user

    data = request.get_json()

    content = data.get('content', '').strip()

    if not content:

        return api_error('备注内容不能为空')

    db.execute("INSERT INTO class_record_notes (record_id, content, created_by) VALUES (?, ?, ?)",

               (rid, content, user.get('real_name') or user.get('username')))

    db.commit()

    return api_response(message='备注已添加')

@app.route('/api/records/<int:rid>/notes/<int:nid>', methods=['DELETE'])

@require_auth(['admin'])

def delete_record_note(rid, nid):

    db = g.db

    db.execute("DELETE FROM class_record_notes WHERE id = ? AND record_id = ?", (nid, rid))

    db.commit()

    return api_response(message='备注已删除')

# ==================== 权限管理API ====================
@app.route('/api/auth/permissions', methods=['GET'])

def get_my_permissions():

    """获取当前用户权限（角色权限+个人覆盖）"""
    user = get_current_user()

    if not user:

        return api_response(data={'role': 'anonymous'})

    perms = get_effective_permissions(user)

    return api_response(data=perms)

@app.route('/api/admin/permissions', methods=['GET'])

@require_auth(['admin'])

def admin_get_permissions():

    """获取所有角色权限 + 用户覆盖"""
    db = g.db

    role_rows = db.execute("SELECT * FROM role_permissions ORDER BY role").fetchall()

    user_overrides = db.execute("SELECT up.*, u.username, u.real_name FROM user_permissions up JOIN users u ON up.user_id=u.id WHERE u.status='active'").fetchall()

    return api_response(data={

        'roles': [dict(r) for r in role_rows],

        'overrides': [dict(r) for r in user_overrides]

    })

# 权限字段列表
_PERM_FIELDS = ['can_manage_students','can_manage_teachers','can_manage_courses',

    'can_manage_enrollments','can_create_schedules','can_checkin',

    'can_view_all_data','can_view_prices','can_manage_users','can_backup']

@app.route('/api/admin/permissions/<role>', methods=['PUT'])

@require_auth(['admin'])

def admin_update_permissions(role):

    """更新角色/用户权限"""
    db = g.db

    data = request.get_json()

    sets = []

    params = []

    for f in _PERM_FIELDS:

        if f in data:

            sets.append(f"{f} = ?")

            params.append(int(data[f]))

    if not sets:

        return api_error('无有效字段')
    params.append(role)

    sets.append("updated_at = datetime('now','localtime')")

    db.execute(f"UPDATE role_permissions SET {', '.join(sets)} WHERE role = ?", params)

    if db.rowcount == 0:

        insert_fields = ['role'] + [f for f in _PERM_FIELDS if f in data]

        insert_values = [role] + [int(data[f]) for f in _PERM_FIELDS if f in data]

        db.execute(f"INSERT INTO role_permissions ({', '.join(insert_fields)}) VALUES ({', '.join('?'*len(insert_values))})", insert_values)

    db.commit()

    return api_response(message='角色权限已更新')

# ==================== 权限管理API ====================
@app.route('/api/admin/users-permissions', methods=['GET'])

@require_auth(['admin'])

def admin_get_users_for_permissions():

    """获取有权限配置的所有用户"""
    db = g.db

    users = db.execute("SELECT id, username, role, real_name, phone, status FROM users WHERE status='active' ORDER BY role, username").fetchall()

    return api_response(data=[dict(u) for u in users])

@app.route('/api/admin/user-permissions/<int:uid>', methods=['GET'])

@require_auth(['admin'])

def admin_get_user_permissions(uid):

    """获取指定用户权限详情（角色权限+个人覆盖+实际生效）"""
    db = g.db

    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    if not user:

        return api_error('用户不存在', 404, 404)
    row = db.execute("SELECT * FROM user_permissions WHERE user_id=?", (uid,)).fetchone()

    role_perms = get_role_permissions(user['role'])

    user_override = dict(row) if row else {f: -1 for f in _PERM_FIELDS}

    effective = {}

    for f in _PERM_FIELDS:

        if user_override.get(f, -1) >= 0:

            effective[f] = user_override[f]

        else:

            effective[f] = role_perms.get(f, 0)

    effective['role'] = user['role']

    return api_response(data={

        'user': dict(user),

        'role_permissions': dict(role_perms),

        'user_permissions': user_override,

        'effective_permissions': effective

    })

@app.route('/api/admin/user-permissions/<int:uid>', methods=['PUT'])
@require_auth(['admin'])
def admin_update_user_permissions(uid):
    """更新指定用户的细粒度权限覆盖"""
    db = g.db
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        return api_error('用户不存在', 404, 404)
    data = request.get_json() or {}

    # 构建权限覆盖字典（-1=使用角色默认值）
    override = {}
    for f in _PERM_FIELDS:
        val = data.get(f, -1)
        try:
            override[f] = int(val)
        except (TypeError, ValueError):
            override[f] = -1

    # 先删除旧记录，再插入新记录
    db.execute("DELETE FROM user_permissions WHERE user_id=?", (uid,))
    field_str = ', '.join(_PERM_FIELDS)
    placeholder_str = ', '.join(['?'] * len(_PERM_FIELDS))
    db.execute(
        f"INSERT INTO user_permissions (user_id, {field_str}, updated_at) VALUES (?, {placeholder_str}, datetime('now','localtime'))",
        [uid] + [override[f] for f in _PERM_FIELDS]
    )
    db.commit()
    return api_response(message='权限已更新')

@app.route('/api/admin/user-permissions/<int:uid>', methods=['DELETE'])
@require_auth(['admin'])
def admin_reset_user_permissions(uid):
    """重置用户权限为角色默认值（删除覆盖记录）"""
    db = g.db
    db.execute("DELETE FROM user_permissions WHERE user_id=?", (uid,))
    db.commit()
    return api_response(message='已重置为角色默认权限')

# ==================== 备份恢复 ====================

@app.route('/api/backup/download', methods=['GET'])

@require_auth(['admin'])

def backup_download():

    """下载数据库备份"""

    db = g.db

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    filename = f'tutoring_backup_{timestamp}.db'

    backup_path = os.path.join(get_data_dir(), filename)

    # 使用 SQLite backup API

    import sqlite3

    src = sqlite3.connect(DB_PATH)

    dst = sqlite3.connect(backup_path)

    src.backup(dst)

    src.close(); dst.close()

    file_size = os.path.getsize(backup_path)

    db.execute("INSERT INTO backup_records (filename, file_size) VALUES (?, ?)", (filename, file_size))

    db.commit()

    @after_this_request

    def cleanup(response):

        try: os.remove(backup_path)

        except: pass

        return response

    return send_file(backup_path, as_attachment=True, download_name=filename,

                     mimetype='application/octet-stream')

@app.route("/api/backup/restore", methods=["POST"])

@require_auth(["admin"])

def backup_restore():
    # 接收文件上传
    file = request.files["file"]

    if not file.filename or not file.filename.endswith(".db"):
        return api_error("请上传 .db 数据库文件")
    # 限制文件大小 200MB
    file_size = file.tell()
    file.seek(0)
    MAX_DB_SIZE = 200 * 1024 * 1024
    if file_size > MAX_DB_SIZE:
        return api_error(f"备份文件过大 200MB 限制 ({file_size / 1024 / 1024:.1f}MB)")
    # 检查 SQLite 文件头
    header = file.read(16)
    file.seek(0)
    if not header.startswith(b"SQLite format 3"):
        return api_error("无效文件 不是 SQLite 数据库")
    # 自动备份当前数据库
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_backup = os.path.join(get_data_dir(), f"auto_backup_before_restore_{timestamp}.db")

    import sqlite3
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(safety_backup)
    src.backup(dst)
    src.close(); dst.close()

    # 保存到临时文件
    restore_path = os.path.join(get_data_dir(), f"restore_{timestamp}.db")
    file.save(restore_path)

    # 验证恢复文件完整性
    try:
        test = sqlite3.connect(restore_path)
        tables = test.execute("SELECT name FROM sqlite_master WHERE type=\"table\"").fetchall()
        table_names = [t[0] if isinstance(t, tuple) else t["name"] for t in tables]
        required_tables = ["students", "courses"]
        if not any(t in table_names for t in required_tables):
            os.remove(restore_path)
            test.close()
            return api_error("备份文件不完整 缺少必要表")
    except Exception as e:
        if os.path.exists(restore_path):
            os.remove(restore_path)
        return api_error(f"验证失败: {str(e)}")
    # 替换数据库
    os.replace(restore_path, DB_PATH)

    # 记录日志
    new_size = os.path.getsize(DB_PATH)
    g.db.execute("INSERT INTO backup_records (filename, file_size) VALUES (?, ?)",
                 (f"restore_{timestamp}.db", new_size))
    g.db.commit()

    return api_response(data={"safety_backup": safety_backup}, message="备份恢复成功")

@app.route("/api/backup/history", methods=["GET"])

@require_auth(["admin"])

def backup_history():
    db = g.db

    records = db.execute("SELECT * FROM backup_records ORDER BY created_at DESC LIMIT 50").fetchall()
    return api_response(data=[dict(r) for r in records])

# ==================== 云存储自动同步 ====================

_last_write_time = 0

_backup_lock = threading.Lock()

def trigger_cloud_backup():

    """延迟触发云备份（写操作后30秒）"""

    global _last_write_time

    _last_write_time = time.time()

    def _delayed_backup():

        time.sleep(35)  # 等待35秒，确保没有新的写入

        with _backup_lock:

            if time.time() - _last_write_time >= 30:

                try:

                    from cloud_backup import upload_db

                    db_path = os.path.join(get_data_dir(), 'tutoring.db')

                    if os.path.exists(db_path):

                        upload_db(db_path)

                except Exception:

                    pass

    threading.Thread(target=_delayed_backup, daemon=True).start()

@app.route('/api/backup/cloud-sync', methods=['POST'])

@require_auth(['admin'])

def cloud_sync():

    """手动触发云端备份"""

    try:

        from cloud_backup import upload_db

        db_path = os.path.join(get_data_dir(), 'tutoring.db')

        if not os.path.exists(db_path):

            return api_error('数据库文件不存在', 404)

        success = upload_db(db_path)

        if success:

            return api_response(message='云端备份成功')

        else:

            return api_error('云端备份失败，请检查TCB_API_KEY配置', 500)

    except ImportError:

        return api_error('缺少 requests 库，无法进行云端备份', 500)

    except Exception as e:

        return api_error(str(e), 500)

@app.route('/api/backup/cloud-restore', methods=['POST'])
@require_auth(['admin'])
def cloud_restore():
    """从云存储恢复数据库"""
    import sqlite3
    try:
        from cloud_backup import download_db
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        restore_path = os.path.join(get_data_dir(), f'cloud_restore_{timestamp}.db')
        success = download_db(restore_path)
        if not success:
            return api_error('云端无可用备份，请先执行云端备份（同步到云端）', 404)
        try:
            test = sqlite3.connect(restore_path)
            tables = test.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t['name'] if isinstance(t, sqlite3.Row) else t[0] for t in tables]
            test.close()
            if 'students' not in table_names or 'courses' not in table_names:
                os.remove(restore_path)
                return api_error('云端备份文件不完整，缺少必要表', 500)
        except Exception:
            os.remove(restore_path)
            return api_error('云端备份文件损坏，无法读取', 500)
        safety_backup = os.path.join(get_data_dir(), f'auto_backup_before_cloud_restore_{timestamp}.db')
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(safety_backup)
        src.backup(dst)
        src.close(); dst.close()
        src2 = sqlite3.connect(restore_path)
        dst2 = sqlite3.connect(DB_PATH)
        src2.backup(dst2)
        src2.close(); dst2.close()
        os.remove(restore_path)
        db = g.db
        db.execute("INSERT INTO backup_records (filename, file_size, created_at) VALUES (?, ?, datetime('now','localtime'))",
                   ('cloud_restore_' + timestamp + '.db', os.path.getsize(safety_backup)))
        db.commit()
        return api_response(message='云端恢复成功，系统将在刷新后使用新数据')
    except ImportError:
        return api_error('缺少 requests 库，无法进行云端恢复', 500)
    except Exception as e:
        return api_error(str(e), 500)
