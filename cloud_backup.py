import os
import time
import logging

logger = logging.getLogger(__name__)

ENV_ID = os.environ.get('TCB_ENV_ID', 'wdl1110-d1g8w3lcf657b61fd')
GATEWAY = f'https://{ENV_ID}.api.tcloudbasegateway.com'
CLOUD_BACKUP_PATH = 'backup/tutoring.db'
_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.tcb_cloud_object_id')


def _get_api_key():
    key = os.environ.get('TCB_API_KEY', '').strip()
    if key:
        return key
    for key_file in ['/app/tcb_api_key', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tcb_api_key')]:
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    k = f.read().strip()
                    if k:
                        return k
            except Exception:
                pass
    return ''


def _get_cloud_object_id():
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, 'r') as f:
                return f.read().strip()
    except Exception:
        pass
    return ''


def _save_cloud_object_id(cloud_object_id):
    try:
        with open(_CACHE_FILE, 'w') as f:
            f.write(cloud_object_id)
    except Exception:
        pass


def upload_db(db_path):
    import requests
    try:
        api_key = _get_api_key()
        if not api_key:
            logger.warning('TCB_API_KEY 未配置，跳过云端备份')
            return False
        resp = requests.post(
            f'{GATEWAY}/v1/storages/get-objects-upload-info',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json=[{'objectId': CLOUD_BACKUP_PATH}],
            timeout=15
        )
        if resp.status_code != 200:
            logger.warning(f'获取上传凭证失败: HTTP {resp.status_code} {resp.text[:300]}')
            return False
        result_list = resp.json()
        if not isinstance(result_list, list) or len(result_list) == 0:
            logger.warning('上传凭证响应异常')
            return False
        item = result_list[0]
        if 'code' in item:
            logger.warning(f'获取上传凭证失败: {item.get("code")} {item.get("message")}')
            return False
        upload_url = item.get('uploadUrl', '')
        if not upload_url:
            logger.warning('上传URL为空')
            return False
        with open(db_path, 'rb') as f:
            put_headers = {
                'Authorization': item.get('authorization', ''),
                'X-Cos-Security-Token': item.get('token', ''),
                'X-Cos-Meta-Fileid': item.get('cloudObjectMeta', ''),
            }
            put_resp = requests.put(upload_url, headers=put_headers, data=f, timeout=60)
        if put_resp.status_code in (200, 204):
            cloud_id = item.get('cloudObjectId', '')
            if cloud_id:
                _save_cloud_object_id(cloud_id)
            logger.info('云存储备份成功')
            return True
        else:
            logger.warning(f'云存储备份失败 HTTP {put_resp.status_code}')
            return False
    except Exception as e:
        logger.warning(f'云存储备份异常 {e}')
        return False


def download_db(save_path):
    import requests
    api_key = _get_api_key()
    if not api_key:
        return False
    cloud_id = _get_cloud_object_id()
    if not cloud_id:
        logger.info('无 cloudObjectId 缓存，跳过云端恢复')
        return False
    try:
        resp = requests.post(
            f'{GATEWAY}/v1/storages/get-objects-download-info',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json=[{'cloudObjectId': cloud_id}],
            timeout=15
        )
        if resp.status_code != 200:
            logger.warning(f'获取下载链接失败: HTTP {resp.status_code}')
            return False
        result_list = resp.json()
        if not isinstance(result_list, list) or len(result_list) == 0:
            return False
        item = result_list[0]
        if 'code' in item:
            return False
        download_url = item.get('downloadUrl', '')
        if not download_url:
            return False
        dl_resp = requests.get(download_url, timeout=30)
        if dl_resp.status_code != 200 or len(dl_resp.content) < 1000:
            return False
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(dl_resp.content)
        logger.info(f'从云存储恢复数据库成功 ({len(dl_resp.content)} bytes)')
        return True
    except Exception as e:
        logger.warning(f'云存储下载异常 {e}')
        return False
