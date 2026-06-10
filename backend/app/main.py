from datetime import datetime
import json
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from pydantic import BaseModel
from .auth import admin_user, create_token, current_user, hash_password, verify_password
from .cloud import ADAPTERS, create_adapter
from .db import get_session, init_db
from .models import CloudSaveTask, CloudSearchHistory, CloudSubscription, Setting, User
from .notify import send_webhook
from .pansou import PanSouProvider
from .settings import get_setting, set_setting
app = FastAPI(title='CloudPilot', version='0.1.0')
class SaveRequest(BaseModel):
    title: str; disk_type: str; share_url: str; share_code: str = ''; target_dir: str = ''; raw: dict = {}
class SubscriptionCreate(BaseModel):
    keyword: str; disk_type: str = 'all'; include_words: str = ''; exclude_words: str = ''; target_dir: str = ''; interval_minutes: int = 360; enabled: bool = True
@app.on_event('startup')
def startup(): init_db()
@app.post('/api/auth/login')
def login(username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    user=session.exec(select(User).where(User.username==username)).first()
    if not user or not verify_password(password,user.password_hash): raise HTTPException(status_code=401, detail='用户名或密码错误')
    return {'access_token':create_token(user.username),'token_type':'bearer','user':{'id':user.id,'username':user.username,'is_admin':user.is_admin}}
@app.get('/api/me')
def me(user: User = Depends(current_user)): return {'id':user.id,'username':user.username,'is_admin':user.is_admin}
@app.get('/api/users')
def list_users(_: User = Depends(admin_user), session: Session = Depends(get_session)): return session.exec(select(User)).all()
@app.post('/api/users')
def create_user(username: str, password: str, is_admin: bool=False, _: User=Depends(admin_user), session: Session=Depends(get_session)):
    if session.exec(select(User).where(User.username==username)).first(): raise HTTPException(status_code=400, detail='用户已存在')
    session.add(User(username=username,password_hash=hash_password(password),is_admin=is_admin)); session.commit(); return {'ok':True}
@app.get('/api/settings')
def read_settings(user: User=Depends(current_user), session: Session=Depends(get_session)): return {r.key:r.value for r in session.exec(select(Setting).where(Setting.owner_id==user.id)).all()}
@app.post('/api/settings')
def write_settings(data: dict, user: User=Depends(current_user), session: Session=Depends(get_session)):
    for k,v in data.items(): set_setting(session,user.id,k,str(v or ''))
    return {'ok':True}
@app.get('/api/cloud-drives')
def cloud_drives(): return {'supported': sorted(set(ADAPTERS.keys()))}
@app.get('/api/search')
async def search(keyword: str, user: User=Depends(current_user), session: Session=Depends(get_session)):
    provider=PanSouProvider(get_setting(session,user.id,'pansou_base_url',''))
    results=await provider.search(keyword)
    session.add(CloudSearchHistory(owner_id=user.id,keyword=keyword,result_count=len(results))); session.commit()
    return {'keyword':keyword,'count':len(results),'items':results}
@app.post('/api/save')
async def save_to_cloud(payload: SaveRequest, user: User=Depends(current_user), session: Session=Depends(get_session)):
    disk=(payload.disk_type or 'unknown').lower(); target=payload.target_dir or get_setting(session,user.id,f'{disk}_target_dir','')
    task=CloudSaveTask(owner_id=user.id,title=payload.title,disk_type=disk,share_url=payload.share_url,share_code=payload.share_code,target_dir=target,status='saving',raw_json=json.dumps(payload.raw or {},ensure_ascii=False))
    session.add(task); session.commit(); session.refresh(task)
    adapter=create_adapter(disk, cookie=get_setting(session,user.id,f'{disk}_cookie',''), token=get_setting(session,user.id,f'{disk}_token',''), target_dir=target)
    result=await adapter.save_share(payload.share_url,payload.share_code,target)
    task.status='success' if result.ok else 'failed'; task.message=result.message; task.updated_at=datetime.utcnow(); session.add(task); session.commit(); session.refresh(task)
    webhook=get_setting(session,user.id,'notify_webhook','')
    if webhook: await send_webhook(webhook,'CloudPilot 转存结果',f'{task.title}\n{task.disk_type}\n{task.status}\n{task.message}')
    return task
@app.get('/api/save-tasks')
def save_tasks(user: User=Depends(current_user), session: Session=Depends(get_session)): return session.exec(select(CloudSaveTask).where(CloudSaveTask.owner_id==user.id).order_by(CloudSaveTask.id.desc())).all()
@app.get('/api/subscriptions')
def subscriptions(user: User=Depends(current_user), session: Session=Depends(get_session)): return session.exec(select(CloudSubscription).where(CloudSubscription.owner_id==user.id).order_by(CloudSubscription.id.desc())).all()
@app.post('/api/subscriptions')
def create_subscription(payload: SubscriptionCreate, user: User=Depends(current_user), session: Session=Depends(get_session)):
    sub=CloudSubscription(owner_id=user.id, **payload.model_dump()); session.add(sub); session.commit(); session.refresh(sub); return sub
@app.delete('/api/subscriptions/{sub_id}')
def delete_subscription(sub_id: int, user: User=Depends(current_user), session: Session=Depends(get_session)):
    sub=session.get(CloudSubscription, sub_id)
    if not sub or sub.owner_id != user.id: raise HTTPException(status_code=404, detail='订阅不存在')
    session.delete(sub); session.commit(); return {'ok':True}
@app.post('/api/notify/test')
async def notify_test(user: User=Depends(current_user), session: Session=Depends(get_session)):
    ok,msg=await send_webhook(get_setting(session,user.id,'notify_webhook',''),'CloudPilot 测试通知','这是一条测试消息')
    return {'ok':ok,'message':msg}
app.mount('/assets', StaticFiles(directory='/app/frontend/assets'), name='assets')
@app.get('/{path:path}')
def index(path: str=''): return FileResponse('/app/frontend/index.html')
