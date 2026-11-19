import React,{useEffect,useRef,useState} from 'react';
import {X,Lock,Mail,User,Loader2,ShieldCheck} from 'lucide-react';
import {fetchServer,setTokenProvider} from './api.js';

export function useAccountGate(){
 const [config,setConfig]=useState(null),[user,setUser]=useState(null),[open,setOpen]=useState(['/signin','/signup'].includes(window.location.pathname)),[error,setError]=useState('');
 const state=useRef({config:null,user:null}),client=useRef(null),pending=useRef(null);
 const accept=user=>{state.current.user=user;setUser(user);setOpen(false);if(['/signin','/signup'].includes(window.location.pathname))window.history.replaceState(null,'','/');setError('');const action=pending.current;pending.current=null;if(action)action()};
 useEffect(()=>{let alive=true,subscription;
  fetchServer('/api/auth/status').then(r=>r.json()).then(async cfg=>{
   if(!alive)return;state.current.config=cfg;if(cfg.mode!=='supabase')setConfig(cfg);
   if(cfg.mode==='supabase'){
    const {createClient}=await import('@supabase/supabase-js');if(!alive)return;
    const supabase=createClient(cfg.url,cfg.key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});client.current=supabase;setConfig(cfg);
    setTokenProvider(async()=>{const {data}=await supabase.auth.getSession();return data.session?.access_token||null});
    const {data}=await supabase.auth.getSession();if(alive&&data.session)accept(data.session.user);
    subscription=supabase.auth.onAuthStateChange((event,session)=>{if(alive){state.current.user=session?.user||null;setUser(session?.user||null);if(event==='SIGNED_IN'){setOpen(false);setTimeout(()=>{const action=pending.current;pending.current=null;action?.()},0)}}}).data.subscription;
   }else if(cfg.mode==='local')accept({id:'local',name:'Local user'});else if(cfg.user)accept(cfg.user);
  }).catch(e=>{if(alive)setError(e.message)});
  return()=>{alive=false;subscription?.unsubscribe();setTokenProvider(null)};
 },[]);
 const canUse=()=>state.current.config?.mode==='local'||!!state.current.user;
 const require=action=>{if(canUse()){action?.();return true}pending.current=action||null;window.history.pushState(null,'','/signin');setOpen(true);return false};
 const signIn=async({username,password,remember})=>{
  if(state.current.config?.mode==='supabase'){
   const {data,error}=await client.current.auth.signInWithPassword({email:username,password});if(error)throw error;accept(data.user);
  }else{
   const response=await fetchServer('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,remember})});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Could not sign in.');accept(body.user);
  }
 };
 const signUp=async({name,email,password})=>{
  if(!client.current)throw new Error('Public account registration has not been configured yet.');
  const {data,error}=await client.current.auth.signUp({email,password,options:{data:{display_name:name},emailRedirectTo:window.location.origin}});if(error)throw error;
  if(data.session)accept(data.user);return !!data.session;
 };
 const signOut=async()=>{if(client.current)await client.current.auth.signOut();await fetchServer('/api/auth/logout',{method:'POST'});state.current.user=null;setUser(null);pending.current=null};
 return {config,user,open,error,canUse,require,signIn,signUp,signOut,close:()=>{setOpen(false);pending.current=null;if(['/signin','/signup'].includes(window.location.pathname))window.history.replaceState(null,'','/')}};
}

export function AccountDialog({model:m}){
 const [signup,setSignup]=useState(false),[name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[remember,setRemember]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{if(m.open)setSignup(!!m.config?.signup_available&&window.location.pathname==='/signup');else{setPassword('');setConfirm('');setError('')}},[m.open,m.config?.signup_available]);
 if(!m.open)return null;
 const submit=async e=>{e.preventDefault();setError('');setMessage('');if(signup&&(password.length<12||password!==confirm)){setError('Use at least 12 characters and make sure both passwords match.');return}setBusy(true);try{if(signup){const logged=await m.signUp({name,email,password});if(!logged)setMessage('Check your email to confirm your account, then return here to sign in.')}else await m.signIn({username:email,password,remember});setPassword('');setConfirm('')}catch(e){setError(e.message)}finally{setBusy(false)}};
 return <div className="modal-backdrop"><section className="modal account-dialog" role="dialog" aria-modal="true" aria-labelledby="account-title" onKeyDown={e=>{if(e.key==='Escape'){m.close();return}if(e.key!=='Tab')return;const controls=[...e.currentTarget.querySelectorAll('button:not([disabled]),input:not([disabled]),a[href]')],first=controls[0],last=controls[controls.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}}><button className="account-close icon-btn" onClick={m.close} aria-label="Close sign in"><X size={20}/></button><div className="account-mark"><Lock size={26}/></div><h2 id="account-title">{signup?'Create your account':'Sign in to edit your PDFs'}</h2><p className="modal-description">{signup?'Your account is free. Your PDFs stay on the document server.':'Sign in once, then pick up your document.'}</p>
 {!m.config?<p>{m.error||'Loading sign-in options…'}</p>:<form onSubmit={submit}>
 {signup&&<label className="field">Display name<input autoComplete="name" value={name} required maxLength={80} onChange={e=>setName(e.target.value)}/></label>}
 <label className="field">{m.config.mode==='supabase'?'Email address':'Username'}<input aria-label={m.config.mode==='supabase'?'Email address':'Username'} autoComplete="username" autoFocus type={m.config.mode==='supabase'?'email':'text'} value={email} placeholder={m.config.mode==='supabase'?'you@example.com':'Your workspace username'} required onChange={e=>setEmail(e.target.value)}/></label>
 <label className="field">Password<input autoComplete={signup?'new-password':'current-password'} type="password" value={password} required minLength={signup?12:1} onChange={e=>setPassword(e.target.value)}/></label>
 {signup?<label className="field">Confirm password<input aria-label="Confirm password" autoComplete="new-password" type="password" value={confirm} required onChange={e=>setConfirm(e.target.value)}/></label>:m.config.mode==='private'&&<label className="remember-me"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/> Keep me signed in for 30 days</label>}
 {error&&<p role="alert" className="account-error">{error}</p>}{message&&<p role="status">{message}</p>}
 <button className="button primary full" type="submit" disabled={busy}>{busy?<><Loader2 className="spin" size={16}/>Please wait…</>:signup?'Create free account':'Sign in'}</button>
 {m.config.signup_available?<button type="button" className="account-switch" onClick={()=>{setSignup(v=>{window.history.replaceState(null,'',v?'/signin':'/signup');return !v});setError('');setMessage('')}}>{signup?'Already have an account? Sign in':'New here? Create a free account'}</button>:<p className="help-note">This workspace uses private sign-in. Public registration is not enabled yet.</p>}
 </form>}<p className="account-privacy"><ShieldCheck size={13}/> Account details are used for sign-in. Documents are processed separately.</p></section></div>;
}
