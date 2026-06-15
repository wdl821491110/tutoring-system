import os
import time
import logging

logger = logging.getLogger(__name__)

ENV_ID = os.environ.get('TCB_ENV_ID', 'tutoring-d1g8s1kwf3a000614')
CLOUD_BACKUP_PATH = 'backup/tutoring.db'


def _get_gateway():
    """动态获取 CloudBase 网关地址"""
    env_id = _get_env_id()
    return f'https://{env_id}.api.tcloudbasegateway.com'


def _get_api_key():
    # 优先从环境变量读取（CloudRun 部署时通过 --env 传入）
    key = os.environ.get('TCB_API_KEY', '').strip()
    if key:
        return key
    # 本地 EXE 模式：从数据库 system_config 表读取
    try:
        from database import get_db
        db = get_db()
        row = db.execute("SELECT value FROM system_config WHERE key = 'tcb_api_key'").fetchone()
        db.close()
        if row and row['value']:
            return row['value'].strip()
    except Exception:
        pass
    return ''

def _get_env_id():
    """获取 CloudBase 环境 ID，支持数据库配置"""
    env_id = os.environ.get('TCB_ENV_ID', '').strip()
    if env_id:
        return env_id
    try:
        from database import get_db
        db = get_db()
        row = db.execute("SELECT value FROM system_config WHERE key = 'tcb_env_id'").fetchone()
        db.close()
        if row and row['value']:
            return row['value'].strip()
    except Exception:
        pass
    return 'tutoring-d1g8s1kwf3a000614'


def upload_db(db_path):
    import requests
    try:
        api_key = _get_api_key()
        if not api_key:
            return (False, 'TCB_API_KEY 未配置')
        resp = requests.post(
            f'{_get_gateway()}/v1/storages/get-objects-upload-info',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json=[{'objectId': CLOUD_BACKUP_PATH}],
            timeout=15
        )
        if resp.status_code != 200:
            err_msg = f'获取上传凭证失败: HTTP {resp.status_code}'
            try:
                body = resp.json()
                if 'message' in body:
                    err_msg += f' - {body["message"]}'
            except Exception:
                pass
            logger.warning(err_msg)
            return (False, err_msg.split(' - ')[-1] if ' - ' in err_msg else err_msg)
        result_list = resp.json()
        if not isinstance(result_list, list) or len(result_list) == 0:
            return (False, '上传凭证响应异常')
        item = result_list[0]
        if 'code' in item:
            return (False, item.get('message', '上传凭证获取失败'))
        upload_url = item.get('uploadUrl', '')
        if not upload_url:
            return (False, '上传URL为空')
        with open(db_path, 'rb') as f:
            put_headers = {
                'Authorization': item.get('authorization', ''),
                'X-Cos-Security-Token': item.get('token', ''),
                'X-Cos-Meta-Fileid': item.get('cloudObjectMeta', ''),
            }
            put_resp = requests.put(upload_url, headers=put_headers, data=f, timeout=60)
        if put_resp.status_code in (200, 204):
            logger.info('云存储备份成功')
            return (True, '上线成功')
        else:
            logger.warning(f'云存储备份失败 HTTP {put_resp.status_code}')
            return (False, f'文件上传失败 HTTP {put_resp.status_code}')
    except Exception as e:
        logger.warning(f'云存储备份异常 {e}')
        return (False, str(e))


def download_db(save_path):
    import requests
    api_key = _get_api_key()
    if not api_key:
        return (False, 'TCB_API_KEY 未配置')

    # 使用 objectList 模式获取下载信息（与 upload 对称，不依赖本地缓存）
    try:
        resp = requests.post(
            f'{_get_gateway()}/v1/storages/get-objects-upload-info',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json=[{'objectId': CLOUD_BACKUP_PATH}],
            timeout=15
        )
        if resp.status_code != 200:
            err_msg = f'获取下载凭证失败: HTTP {resp.status_code}'
            try:
                body = resp.json()
                if 'message' in body:
                    err_msg += f' - {body["message"]}'
            except Exception:
                pass
            logger.warning(err_msg)
            return (False, err_msg.split(' - ')[-1] if ' - ' in err_msg else err_msg)
        result_list = resp.json()
        if not isinstance(result_list, list) or len(result_list) == 0:
            return (False, '下载凭证响应异常')
        item = result_list[0]
        if 'code' in item:
            return (False, item.get('message', '下载凭证获取失败'))
        download_url = item.get('downloadUrl', '')
        if not download_url:
            return (False, 'downloadUrl 为空，云端可能无备份')
        dl_resp = requests.get(download_url, timeout=30)
        if dl_resp.status_code == 200 and len(dl_resp.content) >= 1000:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(dl_resp.content)
            logger.info(f'从云存储恢复数据库成功 ({len(dl_resp.content)} bytes)')
            return (True, '下载成功')
        else:
            logger.warning(f'下载数据异常: HTTP {dl_resp.status_code}, size={len(dl_resp.content)}')
            return (False, '云端无可用备份')
    except Exception as e:
        logger.warning(f'云存储下载异常 {e}')
        return (False, str(e))
