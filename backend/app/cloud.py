from dataclasses import dataclass
from urllib.parse import urlparse
import httpx

@dataclass
class CloudSaveResult:
    ok: bool
    message: str
    saved_id: str = ''

class CloudDriveAdapter:
    disk_type = 'unknown'
    def __init__(self, cookie='', token='', target_dir=''):
        self.cookie = cookie
        self.token = token
        self.target_dir = target_dir

    async def test(self):
        if not (self.cookie or self.token):
            return CloudSaveResult(False, '未配置 Cookie/Token')
        return CloudSaveResult(True, '配置已填写')

    async def save_share(self, share_url, share_code='', target_dir='', category='未分类'):
        return CloudSaveResult(False, f'{self.disk_type} 真实转存接口尚未接入')

class QuarkAdapter(CloudDriveAdapter):
    disk_type='quark'
    api_base='https://drive-pc.quark.cn/1/clouddrive'

    def headers(self):
        return {
            'cookie': self.cookie,
            'content-type': 'application/json',
            'referer': 'https://pan.quark.cn/',
            'user-agent': 'Mozilla/5.0'
        }

    def parse_pwd_id(self, share_url):
        path=urlparse(share_url).path.rstrip('/')
        return path.split('/')[-1]

    async def _post(self, client, path, json):
        url=f'{self.api_base}{path}'
        r=await client.post(url, params={'pr':'ucpro','fr':'pc'}, json=json, headers=self.headers())
        return r.json()

    async def _get(self, client, path, params):
        url=f'{self.api_base}{path}'
        base={'pr':'ucpro','fr':'pc'}
        base.update(params)
        r=await client.get(url, params=base, headers=self.headers())
        return r.json()

    async def ensure_folder(self, client, parent_fid, name):
        data=await self._get(client, '/file/sort', {
            'pdir_fid': parent_fid,
            '_page': 1,
            '_size': 200,
            '_fetch_total': 1,
            '_fetch_sub_dirs': 0,
            '_sort': 'file_type:asc,updated_at:desc'
        })
        for item in data.get('data',{}).get('list',[]) or []:
            if item.get('file_name') == name and item.get('dir') is True:
                return item.get('fid')

        data=await self._post(client, '/file', {
            'pdir_fid': parent_fid,
            'file_name': name,
            'dir_path': '',
            'dir_init_lock': False
        })
        fid=data.get('data',{}).get('fid')
        if not fid:
            raise RuntimeError(f'创建分类目录失败：{data}')
        return fid

    async def save_share(self, share_url, share_code='', target_dir='', category='未分类'):
        if not self.cookie:
            return CloudSaveResult(False, '未配置夸克 Cookie')
        root_fid=target_dir or self.target_dir
        if not root_fid:
            return CloudSaveResult(False, '未配置夸克总目录 FID')

        pwd_id=self.parse_pwd_id(share_url)

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                token_data=await self._post(client, '/share/sharepage/token', {
                    'pwd_id': pwd_id,
                    'passcode': share_code or ''
                })
                stoken=token_data.get('data',{}).get('stoken')
                if not stoken:
                    return CloudSaveResult(False, f'获取分享 token 失败：{token_data}')

                category_fid=await self.ensure_folder(client, root_fid, category)

                detail=await self._get(client, '/share/sharepage/detail', {
                    'pwd_id': pwd_id,
                    'stoken': stoken,
                    'pdir_fid': 0,
                    '_page': 1,
                    '_size': 50,
                    '_fetch_banner': 0,
                    '_fetch_share': 0,
                    '_fetch_total': 1
                })

                file_list=detail.get('data',{}).get('list',[]) or []
                if not file_list:
                    return CloudSaveResult(False, f'分享文件列表为空：{detail}')

                fid_list=[x.get('fid') for x in file_list if x.get('fid')]
                fid_token_list=[x.get('share_fid_token') for x in file_list if x.get('share_fid_token')]

                save_data=await self._post(client, '/share/sharepage/save', {
                    'fid_list': fid_list,
                    'fid_token_list': fid_token_list,
                    'to_pdir_fid': category_fid,
                    'pwd_id': pwd_id,
                    'stoken': stoken,
                    'pdir_fid': 0,
                    'scene': 'link'
                })

                if save_data.get('code') not in (0, '0', None):
                    return CloudSaveResult(False, f'夸克转存失败：{save_data}')

                task_id=save_data.get('data',{}).get('task_id','')
                return CloudSaveResult(True, f'已转存到分类目录：{category}', str(task_id))

            except Exception as e:
                return CloudSaveResult(False, f'夸克转存异常：{e}')

class OneOneFiveAdapter(CloudDriveAdapter): disk_type='115'
class AliyunAdapter(CloudDriveAdapter): disk_type='aliyun'
class UCAdapter(CloudDriveAdapter): disk_type='uc'
class BaiduAdapter(CloudDriveAdapter): disk_type='baidu'
class TianyiAdapter(CloudDriveAdapter): disk_type='tianyi'
class PikPakAdapter(CloudDriveAdapter): disk_type='pikpak'
class XunleiAdapter(CloudDriveAdapter): disk_type='xunlei'
class MobileAdapter(CloudDriveAdapter): disk_type='mobile'
class Cloud123Adapter(CloudDriveAdapter): disk_type='123'

ADAPTERS={'quark':QuarkAdapter,'115':OneOneFiveAdapter,'aliyun':AliyunAdapter,'alipan':AliyunAdapter,'uc':UCAdapter,'baidu':BaiduAdapter,'tianyi':TianyiAdapter,'pikpak':PikPakAdapter,'xunlei':XunleiAdapter,'mobile':MobileAdapter,'123':Cloud123Adapter}

def create_adapter(disk_type, cookie='', token='', target_dir=''):
    key=(disk_type or '').lower()
    cls=ADAPTERS.get(key, CloudDriveAdapter)
    obj=cls(cookie=cookie, token=token, target_dir=target_dir)
    if cls is CloudDriveAdapter:
        obj.disk_type=key or 'unknown'
    return obj
