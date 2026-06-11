from datetime import datetime
import json
import httpx
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from pydantic import BaseModel
from .auth import admin_user, create_token, current_user, hash_password, verify_password
from .cloud import ADAPTERS, create_adapter
from .classify import classify_resource
from .db import get_session, init_db
from .models import CloudSaveTask, CloudSearchHistory, CloudSubscription, Setting, User
from .notify import send_webhook
from .pansou import PanSouProvider
from .tmdb import TMDBClient
from .settings import get_setting, set_setting
app = FastAPI(title='CloudPilot', version='0.1.0')
class SaveRequest(BaseModel):
    title: str; disk_type: str; share_url: str; share_code: str = ''; target_dir: str = ''; media_type: str = ''; category: str = ''; raw: dict = {}
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

    tmdb_key=get_setting(session,user.id,'tmdb_api_key','')
    if tmdb_key and results:
        tmdb=TMDBClient(tmdb_key)
        cache={}
        for item in results[:20]:
            title=item.get('title') or item.get('raw',{}).get('note') or keyword
            key=keyword
            if key not in cache:
                cache[key]=await tmdb.search_best(keyword)
            if cache[key]:
                item['tmdb']=cache[key]
                item['media_type']=cache[key].get('media_type_cn') or cache[key].get('media_type') or item.get('media_type')
                item['category']=cache[key].get('category') or item.get('category')
                item['confidence']=cache[key].get('confidence') or item.get('confidence')
                item['poster']=cache[key].get('tmdb_poster','')
                item['year']=cache[key].get('tmdb_year','')
                item['rating']=cache[key].get('tmdb_rating',0)
                item['overview']=cache[key].get('tmdb_overview','')
                item['tmdb_title']=cache[key].get('tmdb_title','')

    session.add(CloudSearchHistory(owner_id=user.id,keyword=keyword,result_count=len(results))); session.commit()
    return {'keyword':keyword,'count':len(results),'items':results}
@app.post('/api/save')
async def save_to_cloud(payload: SaveRequest, user: User=Depends(current_user), session: Session=Depends(get_session)):
    disk=(payload.disk_type or 'unknown').lower(); target=payload.target_dir or get_setting(session,user.id,f'{disk}_target_dir','')
    task=CloudSaveTask(owner_id=user.id,title=payload.title,disk_type=disk,share_url=payload.share_url,share_code=payload.share_code,target_dir=target,status='saving',raw_json=json.dumps(payload.raw or {},ensure_ascii=False))
    session.add(task); session.commit(); session.refresh(task)
    adapter=create_adapter(disk, cookie=get_setting(session,user.id,f'{disk}_cookie',''), token=get_setting(session,user.id,f'{disk}_token',''), target_dir=target)
    raw = payload.raw or {}
    cls = classify_resource(
        title=payload.title,
        note=raw.get('note') or raw.get('title') or '',
        source=raw.get('source') or ''
    )
    category = payload.category or raw.get('category') or cls.get('category') or '未分类'
    result=await adapter.save_share(payload.share_url,payload.share_code,target,category=category)
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


async def tmdb_request(path: str, params: dict, session: Session, user: User):
    api_key=get_setting(session,user.id,'tmdb_api_key','')
    if not api_key:
        raise HTTPException(status_code=400, detail='未配置 TMDB API Key')

    base='https://api.themoviedb.org/3'
    params=dict(params or {})
    params['api_key']=api_key
    params.setdefault('language','zh-CN')

    async with httpx.AsyncClient(timeout=15) as client:
        r=await client.get(base+path, params=params)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text[:500])
        return r.json()

def tmdb_image(path: str):
    if not path:
        return ''
    return 'https://image.tmdb.org/t/p/w500' + path

def normalize_tmdb_item(x: dict, media_type: str):
    title=x.get('title') or x.get('name') or x.get('original_title') or x.get('original_name') or ''
    date=x.get('release_date') or x.get('first_air_date') or ''
    year=date[:4] if date else ''
    return {
        'id': x.get('id'),
        'title': title,
        'year': year,
        'media_type': media_type,
        'poster': tmdb_image(x.get('poster_path')),
        'backdrop': tmdb_image(x.get('backdrop_path')),
        'rating': x.get('vote_average') or 0,
        'overview': x.get('overview') or '',
        'popularity': x.get('popularity') or 0
    }

@app.get('/api/tmdb/recommend')
async def tmdb_recommend(user: User=Depends(current_user), session: Session=Depends(get_session)):
    sections=[]

    specs=[
        ('流行趋势','/trending/all/day',{'page':1},'mixed'),
        ('正在热映','/movie/now_playing',{'page':1,'region':'CN'},'movie'),
        ('TMDB热门电影','/movie/popular',{'page':1},'movie'),
        ('TMDB热门电视剧','/tv/popular',{'page':1},'tv'),
    ]

    for title,path,params,media in specs:
        data=await tmdb_request(path,params,session,user)
        items=[]
        for x in data.get('results',[])[:14]:
            mt=x.get('media_type') if media=='mixed' else media
            if mt not in ('movie','tv'):
                continue
            items.append(normalize_tmdb_item(x,mt))
        sections.append({'title':title,'items':items})

    return {'sections':sections}

@app.get('/api/tmdb/discover')
async def tmdb_discover(
    media_type: str='movie',
    sort_by: str='popularity.desc',
    genre: str='',
    language: str='',
    vote_min: float=0,
    page: int=1,
    user: User=Depends(current_user),
    session: Session=Depends(get_session)
):
    media_type='tv' if media_type=='tv' else 'movie'
    params={
        'page':page,
        'sort_by':sort_by,
        'vote_average.gte':vote_min
    }
    if genre:
        params['with_genres']=genre
    if language:
        params['with_original_language']=language

    data=await tmdb_request(f'/discover/{media_type}',params,session,user)
    return {
        'page': data.get('page',1),
        'total_pages': data.get('total_pages',1),
        'items':[normalize_tmdb_item(x,media_type) for x in data.get('results',[])[:40]]
    }

@app.get('/api/tmdb/genres')
async def tmdb_genres(media_type: str='movie', user: User=Depends(current_user), session: Session=Depends(get_session)):
    media_type='tv' if media_type=='tv' else 'movie'
    data=await tmdb_request(f'/genre/{media_type}/list',{},session,user)
    return {'genres':data.get('genres',[])}




@app.get('/api/tmdb/detail')
async def tmdb_detail(
    media_type: str,
    media_id: int,
    user: User=Depends(current_user),
    session: Session=Depends(get_session)
):
    media_type='tv' if media_type=='tv' else 'movie'

    data=await tmdb_request(
        f'/{media_type}/{media_id}',
        {'append_to_response':'credits,recommendations,external_ids'},
        session,
        user
    )

    title=data.get('title') or data.get('name') or ''
    date=data.get('release_date') or data.get('first_air_date') or ''
    year=date[:4] if date else ''

    credits=data.get('credits') or {}
    cast=[
        {
            'id':x.get('id'),
            'name':x.get('name') or '',
            'role':x.get('character') or '',
            'avatar':tmdb_image(x.get('profile_path'))
        }
        for x in (credits.get('cast') or [])[:12]
    ]

    crew=[
        {
            'id':x.get('id'),
            'name':x.get('name') or '',
            'job':x.get('job') or '',
            'avatar':tmdb_image(x.get('profile_path'))
        }
        for x in (credits.get('crew') or [])
        if x.get('job') in ('Director','Writer','Producer','Editor')
    ][:9]

    rec_items=[]
    for x in ((data.get('recommendations') or {}).get('results') or [])[:14]:
        rec_items.append(normalize_tmdb_item(x,media_type))

    return {
        'id':data.get('id'),
        'title':title,
        'year':year,
        'media_type':media_type,
        'poster':tmdb_image(data.get('poster_path')),
        'backdrop':tmdb_image(data.get('backdrop_path')),
        'rating':data.get('vote_average') or 0,
        'overview':data.get('overview') or '',
        'genres':[x.get('name') for x in data.get('genres',[])],
        'runtime':data.get('runtime') or data.get('episode_run_time') or '',
        'status':data.get('status') or '',
        'original_title':data.get('original_title') or data.get('original_name') or '',
        'original_language':data.get('original_language') or '',
        'release_date':date,
        'countries':[x.get('name') for x in data.get('production_countries',[])],
        'companies':[x.get('name') for x in data.get('production_companies',[])[:4]],
        'cast':cast,
        'crew':crew,
        'recommendations':rec_items,
        'external_ids':data.get('external_ids') or {}
    }




def fmt_bytes(n):
    try:
        n=float(n or 0)
    except Exception:
        n=0
    units=['B','KB','MB','GB','TB','PB']
    i=0
    while n>=1024 and i<len(units)-1:
        n/=1024
        i+=1
    if i==0:
        return f'{int(n)} {units[i]}'
    return f'{n:.2f} {units[i]}'

async def quark_quota(cookie: str):
    if not cookie:
        return {'ok':False,'message':'未配置 Cookie','used':'--','total':'--','percent':0}

    headers={
        'cookie':cookie,
        'user-agent':'Mozilla/5.0',
        'referer':'https://pan.quark.cn/',
        'origin':'https://pan.quark.cn'
    }

    url='https://drive-pc.quark.cn/1/clouddrive/capacity/growth/info'
    params={'pr':'ucpro','fr':'pc'}

    async with httpx.AsyncClient(timeout=15) as client:
        r=await client.get(url,headers=headers,params=params)
        if r.status_code != 200:
            return {'ok':False,'message':f'HTTP {r.status_code}','used':'--','total':'--','percent':0}

        data=r.json()
        if data.get('status') not in (0,200,None) and not data.get('data'):
            return {'ok':False,'message':str(data)[:120],'used':'--','total':'--','percent':0}

        d=data.get('data') or {}

        total=d.get('total_capacity') or d.get('total') or d.get('capacity') or 0
        used=d.get('use_capacity') or d.get('used_capacity') or d.get('used') or 0

        try:
            percent=round(float(used)/float(total)*100,1) if float(total)>0 else 0
        except Exception:
            percent=0

        return {
            'ok':True,
            'message':'ok',
            'used':fmt_bytes(used),
            'total':fmt_bytes(total),
            'percent':percent
        }

@app.get('/api/cloud-drives/quota')
async def cloud_drive_quota(user: User=Depends(current_user), session: Session=Depends(get_session)):
    result={}

    for disk in ['quark','115','aliyun','uc','baidu','tianyi','xunlei','mobile','123']:
        cookie=get_setting(session,user.id,f'{disk}_cookie','')
        token=get_setting(session,user.id,f'{disk}_token','')
        target=get_setting(session,user.id,f'{disk}_target_dir','')

        if not (cookie or token or target):
            continue

        if disk == 'quark':
            result[disk]=await quark_quota(cookie)
        else:
            result[disk]={
                'ok':False,
                'message':'容量接口待接入',
                'used':'--',
                'total':'--',
                'percent':0
            }

    return result


app.mount('/assets', StaticFiles(directory='/app/frontend/assets'), name='assets')
@app.get('/{path:path}')
def index(path: str=''): return FileResponse('/app/frontend/index.html')
