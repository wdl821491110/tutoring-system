"""
课消管理系统 - 程序入口
支持本地 Windows 和 CloudBase CloudRun 部署
CloudRun 部署时自动使用云存储备份恢复数据库
"""
import os
import sys
import threading
import time
import signal
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('cloud_backup.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 确保可以找到模块
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    os.chdir(base_dir)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_dir)

from database import init_db, get_data_dir
from waitress import serve
from app import app


def _should_use_cloud():
    """检测是否在 CloudRun/Docker 环境中"""
    return bool(os.environ.get('TCB_API_KEY'))


def restore_from_cloud():
    """从云存储恢复数据库"""
    try:
        from cloud_backup import download_db
        import os as _os
        db_path = _os.path.join(get_data_dir(), 'tutoring.db')
        logger.info('尝试从云存储恢复数据库...')
        success = download_db(db_path)
        if success:
            logger.info('数据库从云存储恢复成功')
            init_db()
        else:
            logger.info('云端无备份或恢复失败，使用本地/新建数据库')
    except ImportError:
        logger.warning('cloud_backup 模块不可用（缺少 requests 库）')
    except Exception as e:
        logger.warning(f'从云存储恢复失败: {e}')


def backup_to_cloud():
    """备份数据库到云存储"""
    try:
        from cloud_backup import upload_db
        import os as _os
        db_path = _os.path.join(get_data_dir(), 'tutoring.db')
        if _os.path.exists(db_path):
            upload_db(db_path)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f'备份到云存储失败: {e}')


def cloud_backup_loop(interval=300):
    """定期备份循环（默认5分钟）"""
    while True:
        time.sleep(interval)
        try:
            backup_to_cloud()
        except Exception:
            pass


def main():
    if _should_use_cloud():
        restore_from_cloud()

    init_db()

    is_docker = os.path.exists('/.dockerenv') or os.environ.get('KUBERNETES_SERVICE_HOST')
    cloud_port = os.environ.get('PORT', '')

    if cloud_port:
        port = int(cloud_port)
        host = '0.0.0.0'
    elif is_docker:
        port = 80
        host = '0.0.0.0'
    else:
        port = 8899
        host = '127.0.0.1'

    print(f"课消管理系统 v3.1 启动: {host}:{port}")
    from app import IS_CLOUD as _is_cloud
    if _is_cloud:
        print("运行模式: 云端 CloudRun（直接读写本地 SQLite + 云备份）")
    else:
        print("运行模式: 本地 exe（直接读写本地 SQLite，独立运行）")
    print(f"数据目录: {get_data_dir()}")
    if _should_use_cloud():
        print("云备份: 已启用（自动备份到CloudBase云存储）")

    if _should_use_cloud():
        t = threading.Thread(target=cloud_backup_loop, args=(300,), daemon=True)
        t.start()

    # 仅本地模式自动打开浏览器
    if not cloud_port and not is_docker:
        time.sleep(1)
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{port}')

    # 启动服务
    serve(app, host=host, port=port)


if __name__ == '__main__':
    main()
