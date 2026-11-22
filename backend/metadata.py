"""Document properties and XMP editing, without rewriting page content."""
import io,re
from datetime import datetime,timezone
import pikepdf
from pikepdf.models.metadata import decode_pdf_date,encode_pdf_date

FIELDS={
 'title':('Title','dc:title'),'author':('Author','dc:creator'),
 'subject':('Subject','dc:description'),'keywords':('Keywords','pdf:Keywords'),
 'creator':('Creator','xmp:CreatorTool'),'producer':('Producer','pdf:Producer'),
 'creationDate':('CreationDate','xmp:CreateDate'),'modDate':('ModDate','xmp:ModifyDate'),
}
RESERVED={v[0].lower() for v in FIELDS.values()}|{'trapped'}

def display_date(value):
 try:return decode_pdf_date(value).isoformat().replace('+00:00','Z')
 except (ValueError,TypeError):return value

def date_value(value):
 try:
  parsed=decode_pdf_date(value) if value.startswith('D:') else datetime.fromisoformat(value.replace('Z','+00:00'))
  if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
  return encode_pdf_date(parsed),parsed.isoformat().replace('+00:00','Z')
 except (ValueError,TypeError,OverflowError):raise ValueError('Use a valid date such as 2024-01-02T12:00:00Z.')

def value_text(value):
 if not isinstance(value,str) or len(value)>2000:raise ValueError('Metadata values must be text, up to 2000 characters.')
 if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value):raise ValueError('Metadata contains an unsupported control character.')
 return value

def inspect(data):
 with pikepdf.open(io.BytesIO(data)) as pdf:
  info=pdf.trailer.get('/Info',{})
  fields={key:str(info.get('/'+names[0],'')) for key,names in FIELDS.items()}
  if '/Metadata' in pdf.Root:
   try:
    xmp=pdf.open_metadata(set_pikepdf_as_editor=False,update_docinfo=False)
    for key,(_,xmp_name) in FIELDS.items():
     if not fields[key] and xmp_name in xmp:
      value=xmp[xmp_name];fields[key]='; '.join(map(str,value)) if isinstance(value,(list,tuple)) else str(value)
   except (ValueError,pikepdf.PdfError):pass
  for key in ('creationDate','modDate'):fields[key]=display_date(fields[key])
  custom={str(key)[1:]:str(value) for key,value in info.items() if str(key)[1:].lower() not in RESERVED and isinstance(value,pikepdf.String)}
  count=sum(1 for obj in pdf.objects if isinstance(obj,(pikepdf.Dictionary,pikepdf.Stream)) and '/Metadata' in obj)
  return {'fields':fields,'custom':custom,'xmp_packets':count,'scope':'Document properties and XMP; visible content, comments and editing layers are preserved.'}

def edit(data,values,custom=None):
 if not isinstance(values,dict) or any(key not in FIELDS for key in values):raise ValueError('Choose supported document metadata fields.')
 if custom is not None:
  if not isinstance(custom,dict) or len(custom)>50:raise ValueError('Use at most 50 custom metadata fields.')
  for key,value in custom.items():
   if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9 _.-]{0,79}',key) or key.lower() in RESERVED:raise ValueError('Custom names must start with a letter, use letters/numbers/spaces/dots/hyphens/underscores, and not duplicate a standard field.')
   value_text(value)
 current=inspect(data)['fields']
 with pikepdf.open(io.BytesIO(data)) as pdf:
  with pdf.open_metadata(set_pikepdf_as_editor=False,update_docinfo=False) as xmp:
   for key,value in values.items():
    value=value_text(value);info_name,xmp_name=FIELDS[key]
    pdf_value=value;xmp_value=value
    if key in ('creationDate','modDate') and value:
     if value==current[key]:
      # Preserve an existing malformed legacy date unless the user changes it.
      try:pdf_value,xmp_value=date_value(value)
      except ValueError:continue
     else:pdf_value,xmp_value=date_value(value)
    if value:
     pdf.docinfo['/'+info_name]=pikepdf.String(pdf_value)
     xmp[xmp_name]=[xmp_value] if key=='author' else xmp_value
    else:
     if '/'+info_name in pdf.docinfo:del pdf.docinfo['/'+info_name]
     if xmp_name in xmp:del xmp[xmp_name]
  if custom is not None:
   for key in list(pdf.docinfo.keys()):
    if str(key)[1:].lower() not in RESERVED and isinstance(pdf.docinfo[key],pikepdf.String):del pdf.docinfo[key]
   for key,value in custom.items():pdf.docinfo[pikepdf.Name('/'+key)]=pikepdf.String(value)
  output=io.BytesIO();pdf.save(output);return output.getvalue()

def clear(data):
 with pikepdf.open(io.BytesIO(data)) as pdf:
  if '/Info' in pdf.trailer:del pdf.trailer['/Info']
  # Remove document-, page- and object-level XMP associations. Saving rewrites
  # the file and discards unreachable metadata streams; no incremental history.
  for obj in pdf.objects:
   if isinstance(obj,(pikepdf.Dictionary,pikepdf.Stream)) and '/Metadata' in obj:del obj['/Metadata']
  output=io.BytesIO();pdf.save(output);return output.getvalue()
