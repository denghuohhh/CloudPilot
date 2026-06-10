import httpx
async def send_webhook(url, title, content):
    if not url: return False, 'Webhook 未配置'
    payloads=[{'msgtype':'text','text':{'content':f'{title}\n{content}'}},{'msg_type':'text','content':{'text':f'{title}\n{content}'}},{'title':title,'content':content},{'text':f'{title}\n{content}'}]
    last=''
    async with httpx.AsyncClient(timeout=15) as client:
        for p in payloads:
            try:
                r=await client.post(url,json=p)
                if r.status_code<400: return True, r.text[:200]
                last=f'{r.status_code}: {r.text[:200]}'
            except Exception as e: last=str(e)
    return False,last
