import os
import time
import logging

logger = logging.getLogger(__name__)

ENV_ID = os.environ.get('TCB_ENV_ID', 'tutoring-d1g8s1kwf3a000614')
GATEWAY = f'https://{ENV_ID}.api.tcloudbasegateway.com'
CLOUD_BACKUP_PATH = 'backup/tutoring.db'


def _get_api_key():
    # 从环境变量读取（CloudRun 部署时必须通过 --env 传入）
    key = os.environ.get('TCB_API_KEY', '').strip()
    return key  # 云端无 Key 时返回空字符串，由调用方处理


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

    # 使用 objectList 模式获取下载信息（与 upload 对称，不依赖本地缓存）
    try:
        resp = requests.post(
            f'{GATEWAY}/v1/storages/get-objects-upload-info',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json=[{'objectId': CLOUD_BACKUP_PATH}],
            timeout=15
        )
        if resp.status_code != 200:
            logger.warning(f'获取下载凭证失败: HTTP {resp.status_code} {resp.text[:300]}')
            return False
        result_list = resp.json()
        if not isinstance(result_list, list) or len(result_list) == 0:
            logger.warning('下载凭证响应异常')
            return False
        item = result_list[0]
        if 'code' in item:
            logger.warning(f'获取下载凭证失败: {item.get("code")} {item.get("message")}')
            return False
        download_url = item.get('downloadUrl', '')
        if not download_url:
            logger.warning('downloadUrl 为空')
            return False
        dl_resp = requests.get(download_url, timeout=30)
        if dl_resp.status_code == 200 and len(dl_resp.content) >= 1000:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(dl_resp.content)
            logger.info(f'从云存储恢复数据库成功 ({len(dl_resp.content)} bytes)')
            return True
        else:
            logger.warning(f'下载数据异常: HTTP {dl_resp.status_code}, size={len(dl_resp.content)}')
    except Exception as e:
        logger.warning(f'云存储下载异常 {e}')

    logger.info('从云存储恢复失败，将使用空数据库')
    return False
