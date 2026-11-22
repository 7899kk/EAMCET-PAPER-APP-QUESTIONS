"""Supabase account verification and private workspace sign-in helpers."""
import contextvars,hashlib,json,os,re,threading,time,urllib.request,urllib.error,base64
from collections import OrderedDict

identity=contextvars.ContextVar('folio_user',default=None)
_cache=OrderedDict();_lock=threading.Lock();_attempts={}

def config():
    if os.environ.get('EDIT_KARO_PUBLIC_ACCESS')=='1':
        return {'mode':'public','signup_available':False}
    url=os.environ.get('SUPABASE_URL','').rstrip('/')
    key=os.environ.get('SUPABASE_PUBLISHABLE_KEY') or os.environ.get('SUPABASE_ANON_KEY','')
    if url and key:
        if not re.fullmatch(r'https://[a-zA-Z0-9.-]+(?::[0-9]+)?',url):raise ValueError('Use the HTTPS Supabase project origin without a path.')
        if not (key.startswith('sb_publishable_') or key.startswith('eyJ')):raise ValueError('Use a Supabase publishable/anon key, not a secret key.')
        if key.startswith('eyJ'):
            import base64
            try:role=json.loads(base64.urlsafe_b64decode(key.split('.')[1]+'==='))['role']
            except Exception:raise ValueError('Invalid Supabase public key.')
            if role!='anon':raise ValueError('Do not use a service-role key for public sign-up.')
        return {'mode':'supabase','url':url,'key':key,'signup_available':True}
    return {'mode':'private' if os.environ.get('FOLIO_PREVIEW_PASSWORD') else 'local','signup_available':False}

def verify(token):
    if not token or len(token)>12000:return None
    cfg=config()
    if cfg['mode']!='supabase':return None
    digest=hashlib.sha256(token.encode()).hexdigest();now=time.time()
    with _lock:
        hit=_cache.get(digest)
        if hit and hit[0]>now:_cache.move_to_end(digest);return hit[1]
    req=urllib.request.Request(cfg['url']+'/auth/v1/user',headers={'apikey':cfg['key'],'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=12) as r:user=json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code in (400,401,403):return None
        raise ValueError('Account verification is temporarily unavailable. Retry shortly.')
    except (urllib.error.URLError,TimeoutError):raise ValueError('Account verification took too long. Retry shortly.')
    if not user.get('id'):return None
    safe={'id':user['id'],'email':user.get('email',''),'name':user.get('user_metadata',{}).get('display_name') or user.get('email','')}
    try:expires=float(json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))['exp'])
    except Exception:expires=now
    if expires<now:return None
    with _lock:
        _cache[digest]=(min(now+45,expires),safe)
        while len(_cache)>512:_cache.popitem(last=False)
    return safe

def login_allowed(ip):
    now=time.time()
    with _lock:
        values=[v for v in _attempts.get(ip,[]) if v>now-300]
        _attempts[ip]=values
        if len(values)>=8:return False
        values.append(now)
        if len(_attempts)>2048:_attempts.clear()
    return True

def login_succeeded(ip):
    with _lock:_attempts.pop(ip,None)
