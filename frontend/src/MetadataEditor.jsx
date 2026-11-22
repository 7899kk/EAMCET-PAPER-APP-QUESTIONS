import React,{useState} from 'react';
import {Plus,Trash2,Save} from 'lucide-react';
const basic=[['title','Title'],['author','Author'],['subject','Subject'],['keywords','Keywords']];
const advanced=[['creator','Creator'],['producer','Producer'],['creationDate','Creation date'],['modDate','Modified date']];
export function MetadataEditor({values,setValues,custom,setCustom,xmpPackets,busy,onSave,onClear}){
 const [name,setName]=useState(''),[value,setValue]=useState(''),[error,setError]=useState('');
 const field=([key,label])=><label className="field" key={key}>{label}<input aria-label={'Metadata '+label.toLowerCase()} value={values[key]||''} maxLength={2000} placeholder={key.endsWith('Date')?'2024-01-02T12:00:00Z':''} onChange={e=>setValues({...values,[key]:e.target.value})}/></label>;
 const add=()=>{if(!/^[A-Za-z][A-Za-z0-9 _.-]{0,79}$/.test(name)||[...basic,...advanced].some(([key])=>key.toLowerCase()===name.toLowerCase())||name.toLowerCase()==='trapped'){setError('Use a unique custom name starting with a letter.');return}if(name in custom){setError('That custom property already exists.');return}setCustom({...custom,[name]:value});setName('');setValue('');setError('')};
 return <form onSubmit={e=>{e.preventDefault();onSave()}}>
  <p className="modal-description">Edit the document properties saved inside your PDF. Standard fields are synchronized with its XMP metadata.</p>
  {basic.map(field)}
  <details className="metadata-advanced"><summary>Advanced properties</summary>{advanced.map(field)}<p className="help-note">Dates accept ISO 8601 with a timezone, for example 2024-01-02T12:00:00Z. Empty fields are removed.</p></details>
  <details className="metadata-advanced"><summary>Custom properties ({Object.keys(custom).length})</summary>{Object.entries(custom).map(([key,val])=><div className="metadata-custom-row" key={key}><label className="field">{key}<input aria-label={'Custom metadata '+key} maxLength={2000} value={val} onChange={e=>setCustom({...custom,[key]:e.target.value})}/></label><button type="button" className="icon-btn" aria-label={'Remove custom property '+key} onClick={()=>{const next={...custom};delete next[key];setCustom(next)}}><Trash2 size={16}/></button></div>)}<div className="field-row"><label className="field">New property name<input aria-label="Custom property name" value={name} maxLength={80} onChange={e=>setName(e.target.value)}/></label><label className="field">Value<input aria-label="Custom property value" value={value} maxLength={2000} onChange={e=>setValue(e.target.value)}/></label></div><button type="button" className="button subtle" disabled={busy||Object.keys(custom).length>=50} onClick={add}><Plus size={14}/>Add custom property</button>{error&&<p role="alert">{error}</p>}</details>
  <p className="help-note">{xmpPackets?'Embedded XMP metadata detected.':'No embedded XMP metadata detected.'} Page content, comments and editable objects stay in place.</p>
  <div className="modal-actions"><button type="button" className="button subtle" disabled={busy} onClick={onClear}><Trash2 size={15}/>Clear Metadata</button><button type="submit" className="button primary" disabled={busy}><Save size={15}/>Save metadata</button></div>
 </form>;
}
