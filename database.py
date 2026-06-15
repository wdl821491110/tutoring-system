"""
课消管理系统 - 数据库初始化模块
SQLite 数据库，自动建表
数据目录：优先 DATA_DIR 环境变量 → exe 同级 data/ → 脚本同级 data/
"""
import sqlite3
import os
import sys


def get_data_dir():
    """获取数据存储目录 — 优先使用环境变量 DATA_DIR（CloudRun/CFS），否则用本地目录"""
    env_data_dir = os.environ.get('DATA_DIR', '').strip()
    if env_data_dir:
        data_dir = env_data_dir
    elif getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        data_dir = os.path.join(base, 'data')
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base, 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


DB_PATH = os.path.join(get_data_dir(), 'tutoring.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化所有数据表，自动创建或升级"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        -- 学生表
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT DEFAULT '男',
            grade TEXT,
            school TEXT,
            parent_name TEXT,
            parent_phone TEXT,
            address TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        -- 教师表
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT DEFAULT '男',
            phone TEXT,
            subjects TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        -- 课程表 (teacher_id 字段保留向后兼容)
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            teacher_id INTEGER,
            price_per_hour REAL DEFAULT 0,
            total_hours INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        );

        -- 课程-教师关联表（支持多教师）
        CREATE TABLE IF NOT EXISTS course_teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            UNIQUE(course_id, teacher_id)
        );

        -- 学生-教师关联表（支持多对多）
        CREATE TABLE IF NOT EXISTS student_teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            UNIQUE(student_id, teacher_id)
        );
        CREATE INDEX IF NOT EXISTS idx_student_teachers_student ON student_teachers(student_id);
        CREATE INDEX IF NOT EXISTS idx_student_teachers_teacher ON student_teachers(teacher_id);

        -- 用户表（登录鉴权）
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'parent',
            real_name TEXT,
            phone TEXT,
            linked_student_id INTEGER,
            linked_teacher_id INTEGER,
            force_password_change INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (linked_student_id) REFERENCES students(id) ON DELETE SET NULL,
            FOREIGN KEY (linked_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        );

        -- 备份记录表
        CREATE TABLE IF NOT EXISTS backup_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        -- 报名表（学生-课程关联）
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            purchased_hours INTEGER DEFAULT 0,
            consumed_hours INTEGER DEFAULT 0,
            remaining_hours INTEGER DEFAULT 0,
            amount_paid REAL DEFAULT 0,
            enrolled_date DATE DEFAULT (date('now', 'localtime')),
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        -- 排课表
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER,
            schedule_date DATE NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            hours INTEGER DEFAULT 1,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE SET NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        );

        -- 课消记录表
        CREATE TABLE IF NOT EXISTS class_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER,
            record_date DATE NOT NULL,
            hours_consumed INTEGER DEFAULT 1,
            remaining_before INTEGER DEFAULT 0,
            remaining_after INTEGER DEFAULT 0,
            attendance TEXT DEFAULT 'present',
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE SET NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_class_records_date ON class_records(record_date);
        CREATE INDEX IF NOT EXISTS idx_class_records_student ON class_records(student_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(schedule_date);
        CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
        CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id);
        CREATE INDEX IF NOT EXISTS idx_course_teachers_course ON course_teachers(course_id);

        -- 课时记录备注表
        CREATE TABLE IF NOT EXISTS class_record_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            created_by TEXT,
            FOREIGN KEY (record_id) REFERENCES class_records(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_notes_record ON class_record_notes(record_id);

        -- 角色权限表
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL UNIQUE,
            can_manage_students INTEGER DEFAULT 1,
            can_manage_teachers INTEGER DEFAULT 0,
            can_manage_courses INTEGER DEFAULT 0,
            can_manage_enrollments INTEGER DEFAULT 0,
            can_create_schedules INTEGER DEFAULT 0,
            can_checkin INTEGER DEFAULT 1,
            can_view_all_data INTEGER DEFAULT 0,
            can_view_prices INTEGER DEFAULT 0,
            can_manage_users INTEGER DEFAULT 0,
            can_backup INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        -- 默认权限：教师
        INSERT OR IGNORE INTO role_permissions (role, can_manage_students, can_manage_teachers, can_manage_courses, can_manage_enrollments, can_create_schedules, can_checkin, can_view_all_data, can_view_prices, can_manage_users, can_backup)
        VALUES ('teacher', 0, 0, 0, 0, 0, 1, 0, 0, 0, 0);
        -- 默认权限：管理员（全部开启）
        INSERT OR IGNORE INTO role_permissions (role, can_manage_students, can_manage_teachers, can_manage_courses, can_manage_enrollments, can_create_schedules, can_checkin, can_view_all_data, can_view_prices, can_manage_users, can_backup)
        VALUES ('admin', 1, 1, 1, 1, 1, 1, 1, 1, 1, 1);

        -- 用户权限覆盖表
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            can_manage_students INTEGER DEFAULT -1,
            can_manage_teachers INTEGER DEFAULT -1,
            can_manage_courses INTEGER DEFAULT -1,
            can_manage_enrollments INTEGER DEFAULT -1,
            can_create_schedules INTEGER DEFAULT -1,
            can_checkin INTEGER DEFAULT -1,
            can_view_all_data INTEGER DEFAULT -1,
            can_view_prices INTEGER DEFAULT -1,
            can_manage_users INTEGER DEFAULT -1,
            can_backup INTEGER DEFAULT -1,
            updated_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);

        -- 系统配置表（键值对存储）
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

    ''')

    conn.commit()

    # 创建默认管理员（首次运行）/ 重置密码
    from werkzeug.security import generate_password_hash
    admin = cursor.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    reset_flag = os.environ.get('RESET_ADMIN', '').strip().lower() in ('1', 'true', 'yes')
    force_change_flag = os.environ.get('FORCE_CHANGE_PASS', '').strip().lower() in ('1', 'true', 'yes')

    if not admin:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, real_name, force_password_change) VALUES (?, ?, ?, ?, ?)",
            ('admin', generate_password_hash('admin123', method='pbkdf2:sha256', salt_length=16), 'admin', '系统管理员', 1)
        )
        conn.commit()
        print("已创建默认管理员: admin / admin123 (首次登录需修改密码)")
        print("如需修改初始密码，设置环境变量 FORCE_CHANGE_PASS=1")
    elif reset_flag:
        cursor.execute(
            "UPDATE users SET password_hash = ?, force_password_change = 0 WHERE username = 'admin'",
            (generate_password_hash('admin123', method='pbkdf2:sha256', salt_length=16),)
        )
        conn.commit()
        print("管理员密码已重置为: admin123")
    elif force_change_flag:
        cursor.execute(
            "UPDATE users SET force_password_change = 1 WHERE username = 'admin'",
            ()
        )
        conn.commit()
        print("管理员强制改密标记已设置（下次登录需修改密码）")

    # 确保 force_password_change 列存在（数据库升级兼容）
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [row['name'] if isinstance(row, dict) else row[1] for row in cursor.fetchall()]
        if 'force_password_change' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
            conn.commit()
            print("已添加 force_password_change 列到 users 表")
    except Exception:
        pass

    # 确保 class_records.teacher_id 列存在（数据库升级兼容）
    try:
        cursor.execute("PRAGMA table_info(class_records)")
        columns = [row['name'] if isinstance(row, dict) else row[1] for row in cursor.fetchall()]
        if 'teacher_id' not in columns:
            cursor.execute("ALTER TABLE class_records ADD COLUMN teacher_id INTEGER")
            conn.commit()
            print("已添加 teacher_id 列到 class_records 表")
    except Exception:
        pass

    conn.close()
    print(f"数据库就绪: {DB_PATH}")

    print(f"数据库就绪: {DB_PATH}")


if __name__ == '__main__':
    init_db()
