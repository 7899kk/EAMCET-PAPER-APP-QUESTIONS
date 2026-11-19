import os
async def sign_in(context,base):
    """Use the same real sign-in endpoint as the browser UI."""
    status=await context.request.get(base+'/api/auth/status');data=await status.json()
    if data.get('mode')=='private' and not data.get('user'):
        result=await context.request.post(base+'/api/auth/login',data={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only'),'remember':True})
        assert result.status==200,await result.text()
