let token=localStorage.getItem('cloudpilot_token')||'';

const drives=['all','quark','115','aliyun','uc','baidu','tianyi','xunlei','mobile','123'];
const configDrives=['quark','115','aliyun','uc','baidu','tianyi','xunlei','mobile','123'];
const driveNames={all:'全部',quark:'夸克','115':'115',aliyun:'阿里',uc:'UC',baidu:'百度',tianyi:'天翼',xunlei:'迅雷',mobile:'移动云盘','123':'123云盘'};
const driveLogo={
  quark:'https://pan.quark.cn/favicon.ico',
  uc:'https://drive.uc.cn/favicon.ico',
  '115':'https://115.com/favicon.ico',
  aliyun:'https://www.alipan.com/favicon.ico',
  baidu:'https://pan.baidu.com/favicon.ico',
  tianyi:'https://cloud.189.cn/favicon.ico',
  xunlei:'https://pan.xunlei.com/favicon.ico',
  mobile:'https://caiyun.139.com/favicon.ico',
  '123':'https://www.123pan.com/favicon.ico'
};

const qualityFilters=['','4K','REMUX','原盘','HDR','DV','蓝光'];

let allResults=[];
let settingsCache={};
let driveQuotaCache={};
let driveStatusCache={};

const defaultWeightOrder=['disc','remux','dv','hdr','atmos','dts','k4','p1080','size','configured'];

const weightLabels={
  disc:'原盘',
  remux:'REMUX',
  dv:'DV / 杜比视界',
  hdr:'HDR',
  atmos:'Atmos / 杜比全景声',
  dts:'DTS',
  k4:'4K',
  p1080:'1080P',
  size:'文件大小',
  configured:'已配置网盘'
};

function getWeightOrder(){
  const raw=settingsCache.weight_order || defaultWeightOrder.join(',');
  const arr=String(raw).split(',').filter(x=>defaultWeightOrder.includes(x));
  const rest=defaultWeightOrder.filter(x=>!arr.includes(x));
  return [...arr,...rest];
}

function getWeight(key){
  const order=getWeightOrder();
  const idx=order.indexOf(key);
  if(idx<0) return 0;

  // 越靠前分越高
  return (order.length-idx)*100;
}

function renderWeightOrder(){
  const el=$('weightOrderList');
  if(!el) return;

  const order=getWeightOrder();
  el.innerHTML=order.map(k=>`
    <div class="weight-item" draggable="true" data-key="${k}">
      <span class="drag-handle">☰</span>
      <span>${weightLabels[k]||k}</span>
    </div>
  `).join('');

  bindWeightDrag();
}

function bindWeightDrag(){
  const list=$('weightOrderList');
  if(!list) return;

  let dragging=null;

  list.querySelectorAll('.weight-item').forEach(item=>{
    item.ondragstart=()=>{
      dragging=item;
      item.classList.add('dragging');
    };

    item.ondragend=()=>{
      item.classList.remove('dragging');
      dragging=null;
      saveWeightOrderToCache();
    };
  });

  list.ondragover=e=>{
    e.preventDefault();
    const after=getDragAfterElement(list,e.clientY);
    if(!dragging) return;
    if(after==null) list.appendChild(dragging);
    else list.insertBefore(dragging,after);
  };
}

function getDragAfterElement(container,y){
  const els=[...container.querySelectorAll('.weight-item:not(.dragging)')];

  return els.reduce((closest,child)=>{
    const box=child.getBoundingClientRect();
    const offset=y-box.top-box.height/2;

    if(offset<0 && offset>closest.offset){
      return {offset,element:child};
    }
    return closest;
  },{offset:Number.NEGATIVE_INFINITY}).element;
}

function saveWeightOrderToCache(){
  const el=$('weightOrderList');
  if(!el) return;
  const order=[...el.querySelectorAll('.weight-item')].map(x=>x.dataset.key);
  settingsCache.weight_order=order.join(',');
}

function $(id){return document.getElementById(id)}
function show(id){$(id).classList.remove('hidden')}
function hide(id){$(id).classList.add('hidden')}
function escapeHtml(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}

async function api(path,opts={}){
  opts.headers=opts.headers||{};
  if(token) opts.headers.Authorization='Bearer '+token;
  if(opts.body&&!(opts.body instanceof FormData)){
    opts.headers['Content-Type']='application/json';
    opts.body=JSON.stringify(opts.body);
  }
  const res=await fetch(path,opts);
  if(!res.ok) throw new Error((await res.text()).slice(0,300));
  return res.json();
}

function setLoggedIn(v){
  if(v){
    hide('loginPage'); show('mainPage'); hide('logout');
    initFilters();
    loadSettings(); loadTasks(); loadSubs(); loadWorkflowOverview(); setTimeout(()=>{ if(typeof loadDriveQuota==='function') loadDriveQuota(); },1000);
  }else{
    show('loginPage'); hide('mainPage'); hide('logout');
  }
}

$('loginBtn').onclick=async()=>{
  const fd=new FormData();
  fd.append('username',$('username').value);
  fd.append('password',$('password').value);
  try{
    const data=await api('/api/auth/login',{method:'POST',body:fd});
    token=data.access_token;
    localStorage.setItem('cloudpilot_token',token);
    setLoggedIn(true);
  }catch(e){$('loginMsg').textContent='登录失败：'+e.message}
};

$('logout').onclick=()=>{
  token='';
  localStorage.removeItem('cloudpilot_token');
  setLoggedIn(true);
};

document.querySelectorAll('.side-nav button').forEach(btn=>{
  btn.onclick=()=>{
    document.querySelectorAll('.side-nav button').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab').forEach(t=>t.classList.add('hidden'));
    show('tab-'+btn.dataset.tab);
  };
});

function configuredDrives(){
  return configDrives.filter(d=>!!(
    settingsCache[d+'_cookie'] ||
    settingsCache[d+'_token'] ||
    settingsCache[d+'_target_dir']
  ));
}

function isDriveConfigured(disk){
  return configuredDrives().includes((disk||'').toLowerCase());
}

function driveState(disk){
  const d=(disk||'').toLowerCase();
  return driveStatusCache[d] || {};
}

function canSaveItem(item){
  if(Object.prototype.hasOwnProperty.call(item,'can_save')) return !!item.can_save;
  const st=driveState(item.disk_type);
  if(Object.prototype.hasOwnProperty.call(st,'can_save')) return !!st.can_save;
  return isDriveConfigured(item.disk_type);
}

function driveSaveMessage(item){
  if(item.save_message) return item.save_message;
  const st=driveState(item.disk_type);
  return st.message || (isDriveConfigured(item.disk_type) ? '已配置' : '未配置');
}

function initFilters(){
  if(!$('filterDisk') || $('filterDisk').dataset.ready) return;

  $('filterDisk').innerHTML=drives.map(d=>`<option value="${d}">${driveNames[d]||d}</option>`).join('');
  $('filterQuality').innerHTML=qualityFilters.map(q=>`<option value="${q}">${q||'全部质量'}</option>`).join('');
  $('filterSort').innerHTML=`
    <option value="default">默认排序</option>
    <option value="newest">最新优先</option>
    <option value="oldest">最早优先</option>
    <option value="disk">按网盘类型</option>
    <option value="title">按标题</option>
    <option value="password">有提取码优先</option>
  `;

  ['filterDisk','filterQuality','filterSort','filterInclude','filterExclude'].forEach(id=>{
    $(id).oninput=applyFilters;
    $(id).onchange=applyFilters;
  });

  $('configuredTabBtn').onclick=()=>{
    $('configuredTabBtn').classList.add('active');
    $('unconfiguredTabBtn').classList.remove('active');
    show('resultsConfiguredWrap');
    hide('resultsUnconfiguredWrap');
  };

  $('unconfiguredTabBtn').onclick=()=>{
    $('unconfiguredTabBtn').classList.add('active');
    $('configuredTabBtn').classList.remove('active');
    hide('resultsConfiguredWrap');
    show('resultsUnconfiguredWrap');
  };

  $('filterDisk').dataset.ready='1';
}

function itemText(x){
  const raw=x.raw||{};
  return [
    x.title,x.note,x.url,x.password,
    raw.note,raw.title,raw.url,raw.source
  ].filter(v=>v!==undefined&&v!==null).join(' ').toLowerCase();
}

function itemTime(x){
  const t=x.datetime||x.raw?.datetime||'';
  const ms=Date.parse(t);
  return Number.isFinite(ms)?ms:0;
}



function cleanGroupTitle(text){
  let s=String(text||'').toLowerCase();

  s=s.replace(/https?:\/\/\S+/g,' ');
  s=s.replace(/[《》“”"']/g,' ');
  s=s.replace(/【[^】]+】|\[[^\]]+\]|\([^\)]*\)/g,' ');
  s=s.replace(/简介[:：].*$/g,' ');
  s=s.replace(/描述[:：].*$/g,' ');
  s=s.replace(/标签[:：].*$/g,' ');
  s=s.replace(/文件大小.*$/g,' ');
  s=s.replace(/大小[:：]?\s*\d+(?:\.\d+)?\s*(tb|gb|g|mb)/ig,' ');

  s=s.replace(/全\s*\d+\s*部/g,' ');
  s=s.replace(/第\s*\d+\s*季/g,' ');
  s=s.replace(/s\d{1,2}e?\d{0,3}/ig,' ');
  s=s.replace(/\d+(?:\.\d+)?\s*(tb|gb|g|mb)/ig,' ');

  s=s.replace(/\b(4k|8k|uhd|2160p|1080p|720p|hdr10\+?|hdr|dv|remux|bluray|bdrip|web-dl|webrip|x265|h265|h264|imax|web|hq|sdr|atmos|dts|truehd|aac)\b/ig,' ');
  s=s.replace(/蓝光|原盘|高码率|中字|字幕|国英双语|内封|合集|系列|珍藏|收藏|版本|帧|120帧|60帧|枪版|抢先|国语|粤语|英语|双语|简繁|简中|繁中/g,' ');

  s=s.replace(/[^\u4e00-\u9fa5a-z0-9]+/g,' ');
  s=s.replace(/\s+/g,' ').trim();

  if(s.includes('流浪地球2')) return '流浪地球2';
  if(s.includes('流浪地球')) return '流浪地球';

  return s.slice(0,40);
}


function isInvalidResource(item){
  const raw=item.raw||{};
  const title=String(item.title||raw.note||raw.title||'').trim();
  const url=String(item.url||item.share_url||raw.url||'').trim();
  const text=[title,url].filter(Boolean).join(' ');

  if(!url) return true;
  if(title.length < 2) return true;
  if(/^https?:\/\//.test(title)) return true;

  return /失效|已取消|分享不存在|链接不存在|资源不存在|已删除|违规|无法访问|not found|expired|error 404|404/i.test(text);
}

function mediaMergeKey(text){
  const t=String(text||'').toLowerCase();

  if(/流浪地球\s*2|流浪地球2|the wandering earth 2/i.test(t)) return '流浪地球2';
  if(/流浪地球|the wandering earth/i.test(t)) return '流浪地球';

  const kw=($('keyword')?.value||'').trim().toLowerCase();
  if(kw && t.includes(kw)) return kw;

  let c=cleanGroupTitle(t);
  c=c.replace(/剧情简介|简介|描述|标签|电影|电视剧|资源名称|名称/g,' ');
  c=c.replace(/\s+/g,' ').trim();
  return c;
}


function groupResults(items){
  items=items.filter(x=>!isInvalidResource(x));

  const kw=($('keyword')?.value||'').trim();
  const mainKey=kw ? `search:${kw}` : 'search:all';

  let bestTmdb=null;
  for(const item of items){
    const tmdb=item.tmdb||{};
    if(tmdb.tmdb_id){
      bestTmdb=item;
      break;
    }
  }

  const base=bestTmdb||items[0]||{};
  const tmdb=base.tmdb||{};

  const group={
    key:mainKey,
    alias:kw,
    title:base.tmdb_title||tmdb.tmdb_title||kw||base.title||'搜索结果',
    year:base.year||tmdb.tmdb_year||'',
    poster:base.poster||tmdb.tmdb_poster||'',
    overview:base.overview||tmdb.tmdb_overview||'',
    rating:base.rating||tmdb.tmdb_rating||'',
    media_type:base.media_type||'电影',
    category:base.category||'未分类',
    sources:[]
  };

  // 海报、简介、评分共享：任意资源匹配到就补上
  for(const item of items){
    const t=item.tmdb||{};
    if(!group.poster && (item.poster||t.tmdb_poster)) group.poster=item.poster||t.tmdb_poster;
    if(!group.overview && (item.overview||t.tmdb_overview)) group.overview=item.overview||t.tmdb_overview;
    if(!group.rating && (item.rating||t.tmdb_rating)) group.rating=item.rating||t.tmdb_rating;
    if(!group.year && (item.year||t.tmdb_year)) group.year=item.year||t.tmdb_year;
    if((!group.title || group.title===kw) && (item.tmdb_title||t.tmdb_title)) group.title=item.tmdb_title||t.tmdb_title;
    if(group.category==='未分类' && item.category) group.category=item.category;
    if(group.media_type==='电影' && item.media_type) group.media_type=item.media_type;

    group.sources.push(item);
  }

  group.sources.sort((a,b)=>{
    const qa=qualityScore(a);
    const qb=qualityScore(b);
    if(qb!==qa) return qb-qa;
    return itemTime(b)-itemTime(a);
  });

  return group.sources.length ? [group] : [];
}

function parseQuality(item){
  const raw=item.raw||{};
  const text=[
    item.title,
    raw.note,
    raw.title
  ].filter(Boolean).join(' ');

  const tags=[];

  if(/(2160p|4k|uhd)/i.test(text)) tags.push('4K');
  else if(/1080p/i.test(text)) tags.push('1080P');
  else if(/720p/i.test(text)) tags.push('720P');

  if(/remux/i.test(text)) tags.push('REMUX');
  else if(/原盘|bdiso|bdmv/i.test(text)) tags.push('原盘');
  else if(/web[-\s]?dl/i.test(text)) tags.push('WEB-DL');
  else if(/bdrip|bluray|蓝光/i.test(text)) tags.push('蓝光');
  else if(/hdtv/i.test(text)) tags.push('HDTV');

  if(/dolby vision|杜比视界|\bdv\b/i.test(text)) tags.push('DV');
  if(/\bhdr10\+?\b|hdr/i.test(text)) tags.push('HDR');
  if(/imax/i.test(text)) tags.push('IMAX');

  if(/atmos|杜比全景声/i.test(text)) tags.push('Atmos');
  if(/\bdts\b|dts[-\s]?hd|dts[-\s]?x/i.test(text)) tags.push('DTS');

  const sizeMatch=text.match(/(?:大小|size|文件大小)?[:：]?\s*(\d+(?:\.\d+)?)\s*(TB|GB|G|MB)\b/i);
  let size='';
  if(sizeMatch){
    let unit=sizeMatch[2].toUpperCase();
    if(unit==='G') unit='GB';
    size=`${sizeMatch[1]}${unit}`;
  }

  const episodeMatch=text.match(/(全\s*\d+\s*集|第\s*\d+\s*季|S\d{1,2})/i);
  const episode=episodeMatch ? episodeMatch[1].replace(/\s+/g,'') : '';

  return {tags:[...new Set(tags)], size, episode};
}





function qualityScore(item){
  const q=parseQuality(item);
  let score=0;

  const add=(key,hit)=>{
    if(hit) score += getWeight(key);
  };

  add('configured', isDriveConfigured(item.disk_type));

  add('disc', q.tags.includes('原盘'));
  add('remux', q.tags.includes('REMUX'));
  add('dv', q.tags.includes('DV'));
  add('hdr', q.tags.includes('HDR'));
  add('atmos', q.tags.includes('Atmos'));
  add('dts', q.tags.includes('DTS'));
  add('k4', q.tags.includes('4K'));
  add('p1080', q.tags.includes('1080P'));

  if(q.size){
    const m=q.size.match(/(\d+(?:\.\d+)?)(TB|GB|MB)/i);
    if(m){
      let n=parseFloat(m[1]);
      const u=m[2].toUpperCase();
      if(u==='TB') n*=1024;
      if(u==='MB') n/=1024;

      // 文件大小只在“文件大小”优先级位置参与排序，不再无限放大
      score += getWeight('size') * Math.min(n,300) / 300;
    }
  }

  return score;
}

function diskLogoHtml(disk){
  const src=driveLogo[(disk||'').toLowerCase()];
  if(src) return `<img class="disk-logo" src="${src}" onerror="this.style.display='none'"/>`;
  return `<span class="disk-logo-fallback">${escapeHtml(driveNames[disk]||disk||'?')}</span>`;
}



function resourceDedupeKey(item){
  const q=parseQuality(item);
  const disk=(item.disk_type||'').toLowerCase();
  const code=(item.password||item.share_code||'').toLowerCase();
  const title=cleanGroupTitle(sourceTitle(item)).toLowerCase();
  const size=(q.size||'').toLowerCase();
  const tags=q.tags.join('-').toLowerCase();
  return [disk,size,code,title.slice(0,28),tags].join('|');
}

function dedupeSources(items){
  const map=new Map();

  for(const item of items){
    const key=resourceDedupeKey(item);
    if(!map.has(key)){
      map.set(key,item);
    }else{
      const old=map.get(key);
      if(qualityScore(item)>qualityScore(old)) map.set(key,item);
    }
  }

  return Array.from(map.values());
}

function sourceTitle(item){
  const raw = item.raw || {};
  let t = raw.note || raw.title || item.title || '未命名资源';

  t = String(t)
    .replace(/简介[:：].*$/,'')
    .replace(/描述[:：].*$/,'')
    .replace(/标签[:：].*$/,'')
    .replace(/资源名称[:：]/g,'')
    .replace(/名称[:：]/g,'')
    .replace(/\s+/g,' ')
    .trim();

  return t;
}


function applyFilters(){
  initFilters();

  const disk=$('filterDisk').value;
  const quality=$('filterQuality').value;
  const sort=$('filterSort').value;
  const include=$('filterInclude').value.trim().toLowerCase();
  const exclude=$('filterExclude').value.trim().toLowerCase();

  let items=[...allResults];

  if(disk && disk!=='all') items=items.filter(x=>(x.disk_type||'').toLowerCase()===disk);
  if(quality) items=items.filter(x=>itemText(x).includes(quality.toLowerCase()));

  if(include){
    const words=include.split(/\s+/).filter(Boolean);
    items=items.filter(x=>words.every(w=>itemText(x).includes(w)));
  }

  if(exclude){
    const words=exclude.split(/\s+/).filter(Boolean);
    items=items.filter(x=>words.every(w=>!itemText(x).includes(w)));
  }

  if(sort==='newest') items.sort((a,b)=>itemTime(b)-itemTime(a));
  if(sort==='oldest') items.sort((a,b)=>itemTime(a)-itemTime(b));
  if(sort==='disk') items.sort((a,b)=>(a.disk_type||'').localeCompare(b.disk_type||''));
  if(sort==='title') items.sort((a,b)=>(a.title||'').localeCompare(b.title||''));
  if(sort==='password') items.sort((a,b)=>(b.password?1:0)-(a.password?1:0));

  const configured=items.filter(x=>canSaveItem(x));
  const unconfigured=items.filter(x=>!canSaveItem(x));

  $('configuredCount').textContent=configured.length;
  $('unconfiguredCount').textContent=unconfigured.length;

  renderResults(configured,'resultsConfigured',true);
  renderResults(unconfigured,'resultsUnconfigured',false);

  const showingConfigured=$('configuredTabBtn').classList.contains('active');
  if(showingConfigured){
    show('resultsConfiguredWrap');
    hide('resultsUnconfiguredWrap');
  }else{
    hide('resultsConfiguredWrap');
    show('resultsUnconfiguredWrap');
  }

  $('searchMsg').textContent=`共 ${allResults.length} 条，筛选后 ${items.length} 条`;
}


function getSharedMediaMeta(){
  const kw=($('keyword')?.value||'').trim();

  const best=allResults.find(x=>x.tmdb?.tmdb_id && (x.poster||x.tmdb?.tmdb_poster))
    || allResults.find(x=>x.tmdb?.tmdb_id)
    || allResults.find(x=>x.poster||x.tmdb?.tmdb_poster)
    || allResults[0]
    || {};

  const tmdb=best.tmdb||{};

  return {
    title:best.tmdb_title||tmdb.tmdb_title||kw||best.title||'搜索结果',
    year:best.year||tmdb.tmdb_year||'',
    poster:best.poster||tmdb.tmdb_poster||'',
    overview:best.overview||tmdb.tmdb_overview||'',
    rating:best.rating||tmdb.tmdb_rating||'',
    media_type:best.media_type||'电影',
    category:best.category||'未分类'
  };
}

function renderResults(items,targetId,allowSave){
  const groups=groupResults(items);
  const shared=getSharedMediaMeta();
  groups.forEach(g=>{
    g.title=shared.title;
    g.year=shared.year;
    g.poster=shared.poster;
    g.overview=shared.overview;
    g.rating=shared.rating;
    g.media_type=shared.media_type;
    g.category=shared.category;
  });

  $(targetId).innerHTML=groups.map(group=>{
    return `
      <section class="media-section">
        <div class="media-hero-card">
          ${group.poster?`<img class="media-poster-large" src="${escapeHtml(group.poster)}" loading="lazy"/>`:''}
          <div class="media-info">
            <div class="media-title-large">${escapeHtml(group.title)} ${group.year?`(${escapeHtml(group.year)})`:''}</div>
            <div class="media-sub-large">
              ${escapeHtml(group.media_type)} · ${escapeHtml(group.category)}
              ${group.rating?` · ⭐ ${escapeHtml(String(group.rating).slice(0,3))}`:''}
            </div>
            ${group.overview?`<div class="media-overview-large">${escapeHtml(group.overview)}</div>`:''}
          </div>
        </div>

        <div class="resource-grid">
          ${group.sources.map(item=>{
            const link=item.url||item.share_url||'';
            const canSave=allowSave && canSaveItem(item);
            const q=parseQuality(item);
            const statusText=driveSaveMessage(item);
            return `
              <article class="resource-card">
                ${q.size?`<div class="size-badge">${escapeHtml(q.size)}</div>`:''}

                <div class="resource-head compact">
                  <div class="disk-line">
                    ${diskLogoHtml(item.disk_type)}
                    <strong>${escapeHtml(driveNames[item.disk_type]||item.disk_type)}</strong>
                  </div>
                </div>

                <div class="resource-name">${escapeHtml(sourceTitle(item))}</div>

                <div class="quality-tags">
                  ${q.tags.map(t=>`<span>${escapeHtml(t)}</span>`).join('')}
                  ${q.episode?`<span>${escapeHtml(q.episode)}</span>`:''}
                </div>

                <div class="resource-actions">
                  ${canSave?`<button class="primary mini" onclick='saveCloud(${JSON.stringify(item).replaceAll("'","&#39;")})'>立即转存</button>`:''}
                  <button class="secondary mini" onclick="window.open('${escapeHtml(link)}','_blank')">打开链接</button>
                  ${!canSave?`<span class="save-status">${escapeHtml(statusText)}</span>`:''}
                  ${(item.password||item.share_code)?`<span class="share-code">提取码 ${escapeHtml(item.password||item.share_code)}</span>`:''}
                </div>
              </article>            `;
          }).join('')}
        </div>
      </section>
    `;
  }).join('')||'<div class="list-card">没有资源</div>';
}

window.saveCloud=async(item)=>{
  try{
    const task=await api('/api/save',{method:'POST',body:{
      title:item.title,
      disk_type:item.disk_type,
      share_url:item.url||item.share_url,
      share_code:item.password||item.share_code||'',
      media_type:item.media_type||'',
      category:item.category||'',
      raw:Object.assign({},item.raw||{},{category:item.category||'',media_type:item.media_type||''})
    }});
    alert('转存结果：'+task.status+'\n'+task.message);
    loadTasks();
    loadWorkflowOverview();
  }catch(e){alert('转存失败：'+e.message)}
};

$('searchBtn').onclick=async()=>{
  $('searchMsg').textContent='搜索中...';
  show('filterCard');
  try{
    const data=await api('/api/search?keyword='+encodeURIComponent($('keyword').value));
    if(data.drive_status){
      driveStatusCache=data.drive_status;
    }
    allResults=data.items||[];
    applyFilters();
    loadWorkflowOverview();
  }catch(e){
    $('searchMsg').textContent='搜索失败：'+e.message;
  }
};

function driveCardHtml(d){
  return `
    <div class="drive-card" data-drive-card="${d}">
      <div class="drive-head">
        <strong>${escapeHtml(driveNames[d]||d)}</strong>
        <button class="plain" onclick="removeDrive('${d}')">移除</button>
      </div>
      <label>Cookie<input id="${d}_cookie" placeholder="${driveNames[d]||d} Cookie"/></label>
      <label>Token<input id="${d}_token" placeholder="可留空"/></label>
      <label>目标目录<input id="${d}_target_dir" placeholder="目录ID/FID"/></label>
    </div>
  `;
}


function driveUsageMock(d){
  const usage=driveQuotaCache[d] || {};
  const normalize=value=>{
    if(value === '0 B' || value === '0B') return '--';
    return value || '--';
  };
  return {
    ok: !!usage.ok,
    message: usage.message || '',
    used: normalize(usage.used),
    total: normalize(usage.total),
    percent: Number(usage.percent || 0)
  };
}

async function loadDriveQuota(){
  try{
    console.log('loading drive quota...');
    driveQuotaCache=await api('/api/cloud-drives/quota');
    console.log('drive quota result',driveQuotaCache);
    renderDriveSettings();
  }catch(e){
    console.error('drive quota load failed',e);
  }
}

async function loadDriveStatus(){
  try{
    const data=await api('/api/cloud-drives/status');
    driveStatusCache={};
    (data.items||[]).forEach(item=>{
      driveStatusCache[item.disk_type]=item;
    });
    renderDriveSettings();
    return data;
  }catch(e){
    console.error('drive status load failed',e);
    return null;
  }
}

async function loadWorkflowOverview(){
  try{
    const data=await api('/api/workflow/overview');
    if($('dashSearchCount')) $('dashSearchCount').textContent=String(data.search_count ?? 0);
    if($('dashSaveSuccessCount')) $('dashSaveSuccessCount').textContent=String(data.save_success_count ?? 0);
    if($('dashSubCount')) $('dashSubCount').textContent=String(data.subscription_count ?? 0);
    if($('dashSavableDriveCount')) $('dashSavableDriveCount').textContent=`${data.savable_drive_count ?? 0}/${data.configured_drive_count ?? 0}`;
  }catch(e){
    console.error('workflow overview load failed',e);
  }
}

function renderDriveSettings(){
  const wrap=$('driveCards') || $('driveSettings');
  if(!wrap) return;

  const existing=configuredDrives();

  wrap.className='drive-cards';

  wrap.innerHTML=existing.map((d,i)=>{
    const usage=driveUsageMock(d);
    const state=driveState(d);
    const logo=driveLogo?.[d] || '';
    const quotaMessage=usage.ok ? '' : usage.message;
    const sub=quotaMessage || state.message || (state.can_save ? '可一键转存' : '已配置');
    const readyClass=state.can_save && usage.ok ? 'ready' : 'pending';

    return `
      <div class="drive-card-v2">
        <details class="drive-actions-menu">
          <summary>⋯</summary>
          <div class="drive-dropdown show">
            <button onclick="editDrive('${d}')">编辑配置</button>
            <button onclick="testDrive('${d}')">测试连接</button>
            <button onclick="removeDrive('${d}')">删除网盘</button>
          </div>
        </details>

        <div class="drive-card-head">
          <div class="drive-logo-box">
            ${logo?`<img src="${escapeHtml(logo)}" onerror="this.style.display='none'"/>`:''}
          </div>
          <div>
            <div class="drive-card-name">${escapeHtml(driveNames[d]||d)}</div>
            <div class="drive-card-sub ${readyClass}">${escapeHtml(sub)}</div>
          </div>
        </div>

        <div class="drive-space">
          <div class="drive-space-row">
            <span>已用空间</span>
            <strong>${usage.used || '--'}</strong>
          </div>
          <div class="drive-progress-v2">
            <div style="width:${usage.percent || 0}%"></div>
          </div>
          <div class="drive-space-row">
            <span>总空间</span>
            <strong>${usage.total || '--'}</strong>
          </div>
        </div>
      </div>
    `;
  }).join('') || '<div class="list-card">还没有添加网盘配置</div>';
}

function ensureDriveModal(){
  if($('driveEditModal')) return;

  const div=document.createElement('div');
  div.id='driveEditModal';
  div.className='modal-mask hidden';
  div.innerHTML=`
    <div class="modal-card">
      <div class="modal-head">
        <h3 id="driveEditTitle">编辑网盘</h3>
        <button class="plain" onclick="closeDriveModal()">×</button>
      </div>

      <input type="hidden" id="edit_drive_type"/>

      <label>Cookie
        <textarea id="edit_drive_cookie" placeholder="Cookie"></textarea>
      </label>

      <label>Token
        <input id="edit_drive_token" placeholder="可留空"/>
      </label>

      <label>目标目录 ID / FID
        <input id="edit_drive_target_dir" placeholder="目录ID/FID"/>
      </label>

      <div class="modal-actions">
        <button class="secondary" onclick="closeDriveModal()">取消</button>
        <button class="primary" onclick="saveDriveModal()">保存</button>
      </div>
    </div>
  `;
  document.body.appendChild(div);
}

window.editDrive=function(d){
  ensureDriveModal();

  $('edit_drive_type').value=d;
  $('driveEditTitle').textContent='编辑 '+(driveNames[d]||d);
  $('edit_drive_cookie').value=settingsCache[d+'_cookie']||'';
  $('edit_drive_token').value=settingsCache[d+'_token']||'';
  $('edit_drive_target_dir').value=(settingsCache[d+'_target_dir']||'').trim();

  $('driveEditModal').classList.remove('hidden');
};

window.closeDriveModal=function(){
  if($('driveEditModal')) $('driveEditModal').classList.add('hidden');
};

window.saveDriveModal=function(){
  const d=$('edit_drive_type').value;
  settingsCache[d+'_cookie']=$('edit_drive_cookie').value;
  settingsCache[d+'_token']=$('edit_drive_token').value;
  settingsCache[d+'_target_dir']=$('edit_drive_target_dir').value;

  closeDriveModal();
  renderDriveSettings();
  saveAllSettings();
  setTimeout(()=>{ loadDriveStatus(); if(typeof loadDriveQuota==='function') loadDriveQuota(); },800);
};

window.testDrive=async function(d){
  try{
    const r=await api('/api/cloud-drives/test/'+encodeURIComponent(d),{method:'POST'});
    const quota=r.quota || {};
    const usageText=quota.ok ? `\n已用：${quota.used || '--'}\n总量：${quota.total || '--'}` : '';
    const warningText=r.warning ? `\n提示：${r.warning}` : '';
    alert((driveNames[d]||d)+'：'+(r.message||JSON.stringify(r))+usageText+warningText);
    await loadDriveStatus();
    await loadDriveQuota();
  }catch(e){
    alert((driveNames[d]||d)+' 测试失败：'+e.message);
  }
};

window.removeDrive=(d)=>{
  settingsCache[d+'_cookie']='';
  settingsCache[d+'_token']='';
  settingsCache[d+'_target_dir']='';
  renderDriveSettings();
  saveAllSettings();
};

$('addDriveBtn').onclick=()=>{
  const d=$('addDriveType').value;
  if(!configuredDrives().includes(d)){
    settingsCache[d+'_target_dir']=' ';
  }
  renderDriveSettings();
};

async function loadSettings(){
  try{
    const s=await api('/api/settings');
    settingsCache=s||{};
    $('pansou_base_url').value=s.pansou_base_url||'';
    $('notify_webhook').value=s.notify_webhook||'';
    $('tmdb_api_key').value=s.tmdb_api_key||'';

    renderWeightOrder();
    renderDriveSettings();
    loadDriveStatus();
    setTimeout(()=>{ if(typeof loadDriveQuota==='function') loadDriveQuota(); },500);
  }catch(e){}
}

$('saveSettings').onclick=async()=>{
  saveWeightOrderToCache();

  const body={
    pansou_base_url:$('pansou_base_url').value,
    notify_webhook:$('notify_webhook').value,
    tmdb_api_key:$('tmdb_api_key').value,
    weight_order:settingsCache.weight_order || defaultWeightOrder.join(',')
  };

  configDrives.forEach(d=>{
    const c=$(d+'_cookie');
    const t=$(d+'_token');
    const f=$(d+'_target_dir');
    body[d+'_cookie']=c?c.value:(settingsCache[d+'_cookie']||'');
    body[d+'_token']=t?t.value:(settingsCache[d+'_token']||'');
    body[d+'_target_dir']=f?f.value.trim():(settingsCache[d+'_target_dir']||'');
  });

  try{
    await api('/api/settings',{method:'POST',body});
    settingsCache=Object.assign({},settingsCache,body);
    renderDriveSettings();
    $('settingsMsg').textContent='已保存';
  }catch(e){
    $('settingsMsg').textContent='保存失败：'+e.message;
  }
};

$('testNotify').onclick=async()=>{
  try{
    const r=await api('/api/notify/test',{method:'POST'});
    $('settingsMsg').textContent=JSON.stringify(r);
  }catch(e){$('settingsMsg').textContent=e.message}
};

async function loadTasks(){
  try{
    const items=await api('/api/save-tasks');
    $('tasks').innerHTML=items.map(t=>`
      <div class="result">
        <div class="title">${escapeHtml(t.title)}</div>
        <div class="meta">${escapeHtml(driveNames[t.disk_type]||t.disk_type)} · ${escapeHtml(t.status)}<br/>${escapeHtml(t.message||'')}</div>
      </div>
    `).join('')||'<div>暂无转存任务</div>';
  }catch(e){}
}
$('reloadTasks').onclick=loadTasks;

$('addSubBtn').onclick=async()=>{
  try{
    await api('/api/subscriptions',{method:'POST',body:{
      keyword:$('subKeyword').value,
      disk_type:$('subDisk').value,
      include_words:'',
      exclude_words:'',
      target_dir:$('subTarget').value
    }});
    loadSubs();
  }catch(e){alert(e.message)}
};

async function loadSubs(){
  try{
    const items=await api('/api/subscriptions');
    $('subs').innerHTML=items.map(s=>`
      <div class="result">
        <div class="title">${escapeHtml(s.keyword)}</div>
        <div class="meta">网盘：${escapeHtml(driveNames[s.disk_type]||s.disk_type)} · ${s.enabled?'启用':'停用'}<br/>目标：${escapeHtml(s.target_dir||'-')}</div>
      </div>
    `).join('')||'<div>暂无订阅</div>';
  }catch(e){}
}

setLoggedIn(true);


/* Recommend / Explore */
let discoverState={
  media:'movie',
  sort:'popularity.desc',
  genre:'',
  lang:'',
  page:1
};

function mediaTypeLabel(t){
  return t==='tv'?'电视剧':'电影';
}


function posterCard(item){
  const title=escapeHtml(item.title);
  return `
    <div class="poster-card" onclick="openMediaDetail('${item.media_type}',${item.id})">
      <div class="poster-wrap">
        ${item.poster?`<img src="${escapeHtml(item.poster)}" loading="lazy"/>`:`<div class="poster-empty">无海报</div>`}
        <span class="poster-type">${mediaTypeLabel(item.media_type)}</span>
        <span class="poster-score">${Number(item.rating||0).toFixed(1)}</span>

        <div class="poster-hover">
          <button onclick="event.stopPropagation();searchFromMedia('${title}')">搜索资源</button>
          <button onclick="event.stopPropagation();quickSubscribe('${title}','${item.media_type}')">订阅</button>
        </div>
      </div>
      <div class="poster-title">${title}</div>
      <div class="poster-year">${escapeHtml(item.year||'')}</div>
    </div>
  `;
}


window.openMediaDetail=async(mediaType,id)=>{
  document.querySelectorAll('.side-nav button').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.add('hidden'));
  show('tab-media');

  $('mediaDetail').innerHTML='<div class="list-card">正在加载媒体详情...</div>';

  try{
    const data=await api(`/api/tmdb/detail?media_type=${encodeURIComponent(mediaType)}&media_id=${encodeURIComponent(id)}`);
    renderMediaDetail(data);
  }catch(e){
    $('mediaDetail').innerHTML=`<div class="list-card">详情加载失败：${escapeHtml(e.message)}</div>`;
  }
};

window.quickSubscribe=async(title,mediaType)=>{
  try{
    await api('/api/subscriptions',{method:'POST',body:{
      keyword:title,
      disk_type:'all',
      include_words:'',
      exclude_words:'',
      target_dir:''
    }});
    alert('已添加订阅：'+title);
    loadSubs();
  }catch(e){
    alert('订阅失败：'+e.message);
  }
};

function renderPeople(items,roleKey){
  return (items||[]).map(x=>`
    <div class="person-card">
      ${x.avatar?`<img src="${escapeHtml(x.avatar)}" loading="lazy"/>`:`<div class="avatar-empty"></div>`}
      <strong>${escapeHtml(x.name)}</strong>
      <span>${escapeHtml(x[roleKey]||'')}</span>
    </div>
  `).join('');
}

function renderMediaDetail(data){
  const searchTitle=data.title||'';
  const bg=data.backdrop||data.poster||'';

  $('mediaDetail').innerHTML=`
    <div class="detail-hero" style="${bg?`background-image:linear-gradient(90deg,rgba(248,247,255,.98),rgba(248,247,255,.75),rgba(248,247,255,.96)),url('${escapeHtml(bg)}')`:''}">
      <div class="detail-poster">
        ${data.poster?`<img src="${escapeHtml(data.poster)}" loading="lazy"/>`:''}
      </div>

      <div class="detail-main">
        <h1>${escapeHtml(data.title)} ${data.year?`(${escapeHtml(data.year)})`:''}</h1>
        <div class="detail-meta">
          ${mediaTypeLabel(data.media_type)} · ${(data.genres||[]).map(escapeHtml).join(' / ')}
          ${data.rating?` · ⭐ ${Number(data.rating).toFixed(1)}`:''}
        </div>
        <p>${escapeHtml(data.overview||'暂无简介')}</p>

        <div class="detail-actions">
          <button class="primary" onclick="searchFromMedia('${escapeHtml(searchTitle)}')">搜索资源</button>
          <button class="secondary" onclick="quickSubscribe('${escapeHtml(searchTitle)}','${data.media_type}')">订阅</button>
        </div>
      </div>

      <div class="detail-side">
        <div><b>ID</b><span>${escapeHtml(data.id||'')}</span></div>
        <div><b>原始标题</b><span>${escapeHtml(data.original_title||'-')}</span></div>
        <div><b>状态</b><span>${escapeHtml(data.status||'-')}</span></div>
        <div><b>上映日期</b><span>${escapeHtml(data.release_date||'-')}</span></div>
        <div><b>原始语言</b><span>${escapeHtml(data.original_language||'-')}</span></div>
        <div><b>国家</b><span>${escapeHtml((data.countries||[]).join(', ')||'-')}</span></div>
      </div>
    </div>

    <section class="detail-section">
      <h3>主创</h3>
      <div class="people-grid">${renderPeople(data.crew,'job')}</div>
    </section>

    <section class="detail-section">
      <h3>演员阵容</h3>
      <div class="people-grid">${renderPeople(data.cast,'role')}</div>
    </section>

    <section class="detail-section">
      <h3>推荐</h3>
      <div class="poster-scroll">${(data.recommendations||[]).map(posterCard).join('')}</div>
    </section>
  `;
}

window.searchFromMedia=(title)=>{
  document.querySelector('[data-tab="search"]').click();
  $('keyword').value=title;
  $('searchBtn').click();
};

async function loadRecommend(){
  if(!$('recommendSections')) return;

  try{
    const data=await api('/api/tmdb/recommend');
    $('recommendSections').innerHTML=(data.sections||[]).map(sec=>`
      <section class="recommend-section">
        <div class="section-head">
          <h3>${escapeHtml(sec.title)}</h3>
          <button class="ghost-link">更多 ›</button>
        </div>
        <div class="poster-scroll">
          ${(sec.items||[]).map(posterCard).join('')}
        </div>
      </section>
    `).join('');
  }catch(e){
    $('recommendSections').innerHTML=`<div class="list-card">推荐加载失败：${escapeHtml(e.message)}</div>`;
  }
}

async function loadGenres(){
  if(!$('genreChips')) return;

  try{
    const data=await api('/api/tmdb/genres?media_type='+encodeURIComponent(discoverState.media));
    const genres=data.genres||[];
    $('genreChips').innerHTML=`
      <button class="filter-chip active" data-genre="">全部</button>
      ${genres.map(g=>`<button class="filter-chip" data-genre="${g.id}">${escapeHtml(g.name)}</button>`).join('')}
    `;

    $('genreChips').querySelectorAll('[data-genre]').forEach(btn=>{
      btn.onclick=()=>{
        discoverState.genre=btn.dataset.genre;
        $('genreChips').querySelectorAll('[data-genre]').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        loadDiscover();
      };
    });
  }catch(e){
    $('genreChips').innerHTML='<span class="msg">分类加载失败</span>';
  }
}

async function loadDiscover(){
  if(!$('discoverGrid')) return;

  $('discoverGrid').innerHTML='<div class="list-card">正在加载...</div>';

  const qs=new URLSearchParams({
    media_type:discoverState.media,
    sort_by:discoverState.sort,
    genre:discoverState.genre,
    language:discoverState.lang,
    page:String(discoverState.page)
  });

  try{
    const data=await api('/api/tmdb/discover?'+qs.toString());
    $('discoverGrid').innerHTML=(data.items||[]).map(posterCard).join('') || '<div class="list-card">没有内容</div>';
  }catch(e){
    $('discoverGrid').innerHTML=`<div class="list-card">探索加载失败：${escapeHtml(e.message)}</div>`;
  }
}

function bindRecommendExplore(){
  if($('globalSearchBtn') && !$('globalSearchBtn').dataset.ready){
    $('globalSearchBtn').onclick=()=>{
      const q=$('globalSearchKeyword').value.trim();
      if(!q) return;
      searchFromMedia(q);
    };
    $('globalSearchBtn').dataset.ready='1';
  }

  if($('exploreSearchBtn') && !$('exploreSearchBtn').dataset.ready){
    $('exploreSearchBtn').onclick=()=>{
      const q=$('exploreSearchKeyword').value.trim();
      if(!q) return;
      searchFromMedia(q);
    };
    $('exploreSearchBtn').dataset.ready='1';
  }

  document.querySelectorAll('[data-media]').forEach(btn=>{
    if(btn.dataset.ready) return;
    btn.onclick=()=>{
      discoverState.media=btn.dataset.media;
      discoverState.genre='';
      document.querySelectorAll('[data-media]').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      loadGenres();
      loadDiscover();
    };
    btn.dataset.ready='1';
  });

  document.querySelectorAll('[data-sort]').forEach(btn=>{
    if(btn.dataset.ready) return;
    btn.onclick=()=>{
      discoverState.sort=btn.dataset.sort;
      document.querySelectorAll('[data-sort]').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      loadDiscover();
    };
    btn.dataset.ready='1';
  });

  document.querySelectorAll('[data-lang]').forEach(btn=>{
    if(btn.dataset.ready) return;
    btn.onclick=()=>{
      discoverState.lang=btn.dataset.lang;
      document.querySelectorAll('[data-lang]').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      loadDiscover();
    };
    btn.dataset.ready='1';
  });
}

document.querySelectorAll('.side-nav button').forEach(btn=>{
  btn.addEventListener('click',()=>{
    bindRecommendExplore();
    if(btn.dataset.tab==='recommend') loadRecommend();
    if(btn.dataset.tab==='explore'){
      loadGenres();
      loadDiscover();
    }
  });
});


/* Settings v2 tabs */
function bindSettingsTabs(){
  document.querySelectorAll('.settings-tab').forEach(btn=>{
    if(btn.dataset.ready) return;

    btn.onclick=()=>{
      document.querySelectorAll('.settings-tab').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');

      document.querySelectorAll('.settings-panel').forEach(p=>p.classList.add('hidden'));
      show('settings-'+btn.dataset.settingTab);
    };

    btn.dataset.ready='1';
  });
}


function saveAllSettings(){
  const body={
    pansou_base_url:$('pansou_base_url')?.value||settingsCache.pansou_base_url||'',
    notify_webhook:$('notify_webhook')?.value||settingsCache.notify_webhook||'',
    tmdb_api_key:$('tmdb_api_key')?.value||settingsCache.tmdb_api_key||'',
  };

  configDrives.forEach(d=>{
    body[d+'_cookie'] = $(d+'_cookie')?.value ?? settingsCache[d+'_cookie'] ?? '';
    body[d+'_token'] = $(d+'_token')?.value ?? settingsCache[d+'_token'] ?? '';
    body[d+'_target_dir'] = $(d+'_target_dir')?.value ?? settingsCache[d+'_target_dir'] ?? '';
  });

  api('/api/settings',{method:'POST',body})
    .then(()=>{
      settingsCache=Object.assign({},settingsCache,body);
      if($('settingsMsg')) $('settingsMsg').textContent='已保存';
      renderDriveSettings();
      loadDriveStatus();
      loadWorkflowOverview();
      if(typeof loadDriveQuota==='function') loadDriveQuota();
    })
    .catch(e=>{
      if($('settingsMsg')) $('settingsMsg').textContent='保存失败：'+e.message;
    });
}

function bindSettingsV2Buttons(){
  ['saveSystemSettings','saveInterfaceSettings','saveDriveSettings','saveNotifySettings'].forEach(id=>{
    const btn=$(id);
    if(!btn || btn.dataset.ready) return;
    btn.onclick=saveAllSettings;
    btn.dataset.ready='1';
  });
}

document.querySelectorAll('.side-nav button').forEach(btn=>{
  btn.addEventListener('click',()=>{
    if(btn.dataset.tab==='settings'){
      bindSettingsTabs();
      bindSettingsV2Buttons();
    }
  });
});


/* Settings tab click fix */
document.addEventListener('click', function(e){
  const btn=e.target.closest('.settings-tab');
  if(!btn) return;

  e.preventDefault();

  const tab=btn.dataset.settingTab;
  if(!tab) return;

  document.querySelectorAll('.settings-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');

  document.querySelectorAll('.settings-panel').forEach(p=>p.classList.add('hidden'));

  const panel=document.getElementById('settings-'+tab);
  if(panel) panel.classList.remove('hidden');
});

window.switchSettingsTab=function(tab){
  document.querySelectorAll('.settings-tab').forEach(b=>b.classList.remove('active'));

  const btn=document.querySelector(`.settings-tab[data-setting-tab="${tab}"]`);
  if(btn) btn.classList.add('active');

  document.querySelectorAll('.settings-panel').forEach(p=>p.classList.add('hidden'));

  const panel=document.getElementById('settings-'+tab);
  if(panel) panel.classList.remove('hidden');
};

window.toggleDriveMenu=function(index,event){
  if(event) event.stopPropagation();

  document
    .querySelectorAll(".drive-dropdown")
    .forEach(x=>x.classList.remove("show"));

  const el=document.getElementById(
    "drive-menu-"+index
  );

  if(el){
    el.classList.add("show");
  }
};

window.addEventListener("click",e=>{

  if(!e.target.closest(".drive-more") && !e.target.closest(".drive-dropdown")){

    document
      .querySelectorAll(".drive-dropdown")
      .forEach(x=>x.classList.remove("show"));
  }
});


/* drive menu hard fix */
document.addEventListener('click', function(e){
  const more=e.target.closest('.drive-more');
  if(more){
    e.preventDefault();
    e.stopPropagation();

    document.querySelectorAll('.drive-dropdown').forEach(x=>{
      if(x !== more.parentElement.querySelector('.drive-dropdown')){
        x.classList.remove('show');
      }
    });

    const menu=more.parentElement.querySelector('.drive-dropdown');
    if(menu){
      menu.classList.toggle('show');
    }
    return;
  }

  if(!e.target.closest('.drive-dropdown')){
    document.querySelectorAll('.drive-dropdown').forEach(x=>x.classList.remove('show'));
  }
}, true);


/* quota force final */
document.addEventListener('click', function(e){
  const btn=e.target.closest('.settings-tab');
  if(btn && btn.dataset.settingTab === 'drives'){
    setTimeout(()=>{
      if(typeof loadDriveQuota === 'function') loadDriveQuota();
      if(typeof renderDriveSettings === 'function') renderDriveSettings();
    },300);
  }
});
