from dataclasses import dataclass
@dataclass
class CloudSaveResult:
    ok: bool
    message: str
    saved_id: str = ''
class CloudDriveAdapter:
    disk_type = 'unknown'
    def __init__(self, cookie='', token='', target_dir=''):
        self.cookie = cookie; self.token = token; self.target_dir = target_dir
    async def test(self):
        if not (self.cookie or self.token): return CloudSaveResult(False, '未配置 Cookie/Token')
        return CloudSaveResult(True, '配置已填写，真实连通性测试待接入')
    async def save_share(self, share_url, share_code='', target_dir=''):
        return CloudSaveResult(False, f'{self.disk_type} 真实转存接口尚未接入')
class QuarkAdapter(CloudDriveAdapter): disk_type='quark'
class OneOneFiveAdapter(CloudDriveAdapter): disk_type='115'
class AliyunAdapter(CloudDriveAdapter): disk_type='aliyun'
class UCAdapter(CloudDriveAdapter): disk_type='uc'
class BaiduAdapter(CloudDriveAdapter): disk_type='baidu'
class TianyiAdapter(CloudDriveAdapter): disk_type='tianyi'
class PikPakAdapter(CloudDriveAdapter): disk_type='pikpak'
class XunleiAdapter(CloudDriveAdapter): disk_type='xunlei'
class MobileAdapter(CloudDriveAdapter): disk_type='mobile'
class Cloud123Adapter(CloudDriveAdapter): disk_type='123'
ADAPTERS = {'quark':QuarkAdapter,'115':OneOneFiveAdapter,'aliyun':AliyunAdapter,'alipan':AliyunAdapter,'uc':UCAdapter,'baidu':BaiduAdapter,'tianyi':TianyiAdapter,'pikpak':PikPakAdapter,'xunlei':XunleiAdapter,'mobile':MobileAdapter,'123':Cloud123Adapter}
def create_adapter(disk_type, cookie='', token='', target_dir=''):
    key=(disk_type or '').lower(); cls=ADAPTERS.get(key, CloudDriveAdapter); obj=cls(cookie=cookie, token=token, target_dir=target_dir)
    if cls is CloudDriveAdapter: obj.disk_type = key or 'unknown'
    return obj
