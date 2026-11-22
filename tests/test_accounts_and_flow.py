import io,time
import pytest,pymupdf as fitz
from fastapi.testclient import TestClient
from backend.app import app
from backend import accounts,blocks,layers
from backend.auth import COOKIE_NAME,valid_cookie

def document():
    with fitz.open() as d:
        d.new_page().insert_text((45,90),'Account private document.',fontsize=16);return d.tobytes()

def test_public_landing_web_signin_and_logout_without_browser_password_popup(monkeypatch):
    monkeypatch.setenv('FOLIO_PREVIEW_PASSWORD','private-test-password');accounts._attempts.clear()
    with TestClient(app,base_url='https://testserver') as c:
        r=c.get('/');assert r.status_code==200 and 'www-authenticate' not in r.headers
        assert c.get('/api/auth/status').json()['mode']=='private'
        assert c.post('/api/documents',files={'file':('d.pdf',document())}).status_code==401
        assert c.post('/api/auth/login',json={'username':'folio','password':'wrong'}).status_code==401
        r=c.post('/api/auth/login',json={'username':'folio','password':'private-test-password','remember':True});assert r.status_code==200
        assert 'Max-Age=2592000' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
        assert valid_cookie(c.cookies.get(COOKIE_NAME),'private-test-password')
        assert c.post('/api/documents',files={'file':('d.pdf',document())}).status_code==200
        c.post('/api/auth/logout')
        assert c.post('/api/documents',auth=('folio','private-test-password'),files={'file':('d.pdf',document())}).status_code==401
        assert c.post('/api/auth/login',json={'username':'folio','password':'private-test-password'}).status_code==200
        assert c.post('/api/documents',files={'file':('d.pdf',document())}).status_code==200

def test_account_owned_documents_cannot_be_accessed_by_another_signed_in_user(monkeypatch):
    monkeypatch.setattr(accounts,'config',lambda:{'mode':'supabase','url':'https://example.supabase.co','key':'sb_publishable_test','signup_available':True})
    monkeypatch.setattr(accounts,'verify',lambda t:{'id':t,'email':t+'@example.com'})
    with TestClient(app) as c:
        a={'Authorization':'Bearer user-a'};b={'Authorization':'Bearer user-b'}
        r=c.post('/api/documents',headers=a,files={'file':('d.pdf',document())});assert r.status_code==200
        token={'X-Session':r.json()['token']}
        assert c.get('/api/document/pdf',headers={**a,**token}).status_code==200
        assert c.get('/api/document/pdf',headers={**b,**token}).status_code==404
        assert c.delete('/api/document',headers={**b,**token}).status_code==404
        assert c.get('/api/document/pdf',headers={**a,**token}).status_code==200
        assert 'https://example.supabase.co' in c.get('/').headers['content-security-policy']

def test_mixed_font_line_is_one_editable_line_and_longer_text_wraps():
    with fitz.open() as d:
        p=d.new_page();x=45
        for text,font in [("I'm feeling ",'helv'),('happy','hebo'),(' Today','helv')]:
            p.insert_text((x,90),text,fontname=font,fontsize=18);x+=fitz.get_text_length(text,fontname=font,fontsize=18)
        source=d.tobytes()
    b=blocks.inspect_blocks(source,0)[0];assert b['text']=="I'm feeling happy Today" and b['editable'] and b['font_notice']
    text="I'm feeling enthusiastic and happy Today. This longer sentence should wrap naturally onto another line."
    changed,u=blocks.replace_block(source,0,{'id':b['id'],'original':b['text'],'text':text})
    assert u['size']==18 and u['rect'][3]>b['rect'][3]
    with fitz.open(stream=changed,filetype='pdf') as d:assert text in ' '.join(d[0].get_text().split())

def test_legacy_narrow_managed_text_widens_instead_of_becoming_a_column():
    data=document();data=layers.add(data,0,{'type':'text','font':'helv','text':'Ashok','rect':[45,160,95,190],'size':16,'max_size':16,'fixed_frame':True})
    b=next(b for b in blocks.inspect_blocks(data,0) if b['kind']=='layer')
    assert b['flow_rect'][2]>300
    result,u=blocks.replace_block(data,0,{'id':b['id'],'original':b['text'],'text':'Ashok one two three four five six seven eight.'})
    assert u['size']==16 and u['rect'][2]>300
    with fitz.open(stream=result,filetype='pdf') as d:assert 'one two three' in ' '.join(d[0].get_text().split())


def test_supabase_public_key_checks_and_cached_provider_verification(monkeypatch):
    import base64,json
    monkeypatch.setenv('SUPABASE_URL','https://example.supabase.co');monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_test')
    accounts._cache.clear();calls=[]
    token='header.'+base64.urlsafe_b64encode(json.dumps({'exp':time.time()+120}).encode()).decode().rstrip('=')+'.signature'
    def provider(request,timeout):
        calls.append(request.full_url);return io.BytesIO(json.dumps({'id':'verified-user','email':'user@example.com','user_metadata':{'display_name':'User'}}).encode())
    monkeypatch.setattr(accounts.urllib.request,'urlopen',provider)
    assert accounts.verify(token)['id']=='verified-user' and accounts.verify(token)['id']=='verified-user'
    assert len(calls)==1
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_secret_not_allowed')
    with pytest.raises(ValueError,match='publishable/anon'):accounts.config()


def test_public_access_ignores_old_login_configuration_and_edits_without_cookies(monkeypatch):
    monkeypatch.setenv('EDIT_KARO_PUBLIC_ACCESS','1')
    monkeypatch.setenv('FOLIO_PREVIEW_PASSWORD','old-password')
    monkeypatch.setenv('SUPABASE_URL','invalid-unused-config')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','unused')
    with TestClient(app) as c:
        status=c.get('/api/auth/status').json();assert status=={'mode':'public','signup_available':False,'user':None}
        assert c.get('/api/health').json()['sign_in_required'] is False
        assert c.post('/api/documents/blank').status_code==200
        r=c.post('/api/documents',files={'file':('sample.pdf',document())});assert r.status_code==200
        h={'X-Session':r.json()['token']}
        b=c.get('/api/document/page/0/blocks',headers=h).json()['blocks'][0]
        r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,'id':b['id'],'original':b['text'],'text':'Edited with no sign in.'}});assert r.status_code==200,r.text
        result=c.post('/api/document/export',headers=h,json={'kind':'pdf'});assert result.status_code==200 and not result.headers.get('www-authenticate')
        with fitz.open(stream=result.content,filetype='pdf') as d:assert 'Edited with no sign in.' in d[0].get_text()
        assert not c.cookies
