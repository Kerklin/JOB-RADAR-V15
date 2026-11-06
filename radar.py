"""V15 Job Radar: python radar.py [test]. Playwright for Oracle portals; no AI or user secrets."""
import concurrent.futures as cf
import datetime as dt
import html,json,os,re,sys,unittest,urllib.request,urllib.error,urllib.parse,urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
NOW=lambda:dt.datetime.now(dt.timezone.utc)
ORACLE={'UNDP':'https://estm.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs','IOM':'https://fa-evlj-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs'}
MAX_BYTES=32_000_000
SOURCES={
 'IOM':[ORACLE['IOM']],
 'UNDP':['https://estm.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs'],
 'UNICEF':['https://careers.pageuppeople.com/671/cw/en/rss'],
 'UNOPS':['https://careers.unops.org/careersmarketplace/SearchJobs/feed/?listFilterMode=1&jobRecordsPerPage=6','https://rss.careers.unops.org/'],
 'UN Careers':['https://careers.un.org/jobfeed?language=en','https://careers.un.org/jobfeed?isPage=true'],

 'Impactpool':['https://www.impactpool.org/search?occupational_groups%5B%5D=Engineering'],
}
# HTML anchors must have a vacancy-specific URL. Navigation is never a vacancy.
PATTERNS={
 'IOM':r'/hcmUI/CandidateExperience/en/sites/CX_1001/(?:jobs/preview|job)/[0-9]+',
 'UNDP':r'/hcmUI/CandidateExperience/en/sites/CX_1/(?:jobs/preview|job)/[0-9]+',
 'UNICEF':r'/job/\d+', 'UNOPS':r'/(?:JobDetail|vacancies|ViewVacancy|job)/[^/?#]+',
 'UN Careers':r'/(?:jobSearchDescription|jobOpening)/\d+',
 'UNjobs':r'/vacancies/\d+', 'Impactpool':r'/jobs/\d+',
 'UNJobsFeed':r'/(?:jobs|job)/[^/?#]+'}
TRACKS={
 'Construction':['project manager infrastructure','project manager construction','construction engineer','construction','construction supervisor','construction project manager','construction management engineer','construction officer','construction manager','construction specialist','site engineer','resident engineer','engineering officer','engineering associate','clerk of works','construction supervision','civil works','rehabilitation'],
 'Infrastructure':['civil engineer','structural engineer','road engineer','bridge engineer','infrastructure engineer','infrastructure field engineer','field engineer','engineering assistant','engineering technician','project engineer','infrastructure specialist','building services engineer','geotechnical engineer','energy efficiency engineer','reinforced concrete','pavement'],
 'WASH':['wash engineer','wash officer','wash specialist','wash consultant','water engineer','sanitation engineer','water supply','water treatment','sewerage','wastewater','boreholes'],
 'Contracts':['quantity surveyor','fidic','contract manager','contracts manager','cost engineer','works contracts','procurement specialist','procurement officer','bill of quantities','bills of quantities','boq'],
 'Facilities':['facilities manager','facility manager','common premises','building maintenance','refurbishment','property management'],
 'Architecture':['architect','heritage conservation','restoration','urban planner','urban planning','architectural','housing reconstruction','architectural design']}

def norm(s):return re.sub(r'[^a-z0-9]+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s or '')).lower()).strip()
def has(s,p):return ' '+norm(p)+' ' in ' '+norm(s)+' '
def safe_url(u):
 try:return urllib.parse.urlsplit(u).scheme in ('https','http') and bool(urllib.parse.urlsplit(u).hostname) and not urllib.parse.urlsplit(u).username
 except ValueError:return False

def rank(title,desc):
 t,d=norm(title),norm(desc)
 if any(has(t,x) for x in ['intern','internship','driver','finance officer','communications officer','human resources','software','cloud','data engineer','solutions architect','enterprise architect','digital infrastructure','digital public infrastructure']):return 0,''
 if any(has(t+' '+d,x) for x in ['internal candidates only','internal applicants only']):return 0,''
 tier=re.search(r'open to tiers? ([0-9 ,and]+) applicants',t)
 if tier and '3' not in tier[1] and not has(t,'external'):return 0,''
 if any(has(t,x) for x in ['procurement specialist','procurement officer']) and not any(has(t+' '+d,x) for x in ['construction','infrastructure','civil works','works contract','boq']):return 0,''
 scores={k:sum(24 if has(t,p) else 8 if has(d,p) else 0 for p in terms) for k,terms in TRACKS.items()}
 track=max(scores,key=scores.get);s=scores[track]
 if s<16:return 0,''
 return s+(10 if any(has(t+' '+d,x) for x in ['sarajevo','bosnia','western balkans']) else 0),track

def canonical(u):
 p=urllib.parse.urlsplit(u);q=urllib.parse.parse_qsl(p.query,keep_blank_values=True)
 q=[(k,v) for k,v in q if not k.lower().startswith('utm_')]
 return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path,urllib.parse.urlencode(q),''))

def deadline(text):
 # Only labelled, unambiguous dates. Unknown dates are never guessed.
 m=re.search(r'(?:deadline|closing date|application deadline|apply by)\s*:?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})',text,re.I)
 if not m:return None
 for fmt in ('%Y-%m-%d','%d %B %Y','%d %b %Y','%B %d, %Y','%B %d %Y','%b %d, %Y'):
  try:return dt.datetime.strptime(m[1],fmt).date().isoformat()
  except ValueError:pass
 return None

class Links(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.href=None;self.text=[];self.rows=[];self.feeds=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a':self.href=a.get('href');self.text=[]
  if tag=='link' and 'alternate' in a.get('rel','') and any(x in a.get('type','') for x in ('rss','atom')):self.feeds.append(a.get('href',''))
 def handle_data(self,s):
  if self.href is not None:self.text.append(s)
 def handle_endtag(self,tag):
  if tag=='a' and self.href is not None:self.rows.append((self.href,' '.join(self.text).strip()));self.href=None

def decode(raw,content_type):
 m=re.search(r'charset=([\w-]+)',content_type,re.I)
 return raw.decode(m[1] if m else 'utf-8',errors='replace').lstrip('\ufeff').strip()

def parse(raw,ctype,base,source):
 text=decode(raw,ctype)
 if not text:raise ValueError('Empty response')
 if re.search(r'captcha|verify you are human|just a moment|access denied',text[:4000],re.I):raise ValueError('Access challenge; not bypassed')
 xml_feed=bool(re.search(r'<(?:rss|feed|rdf:RDF)\b',text[:1000],re.I))
 is_html=not xml_feed and ('text/html' in ctype.lower() or bool(re.search(r'<!doctype\s+html|<html\b',text[:1000],re.I)))
 rows=[];feeds=[];mode='HTML'
 if is_html:
  p=Links();p.feed(text);feeds=[urllib.parse.urljoin(base,u) for u in p.feeds]
  for href,title in p.rows:
   url=urllib.parse.urljoin(base,href)
   if re.search(PATTERNS[source],urllib.parse.urlsplit(url).path,re.I) and len(title)>8:rows.append((title,url,''))
 else:
  mode='XML'
  try:root=ET.fromstring(text)
  except ET.ParseError:
   # Limited repair, not arbitrary recovery: bare ampersands and illegal XML controls.
   repaired=re.sub(r'&(?!#\d+;|#x[0-9a-fA-F]+;|[A-Za-z][A-Za-z0-9]+;)','&amp;',text)
   repaired=re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f]','',repaired)
   root=ET.fromstring(repaired);mode='XML (limited repair)'
  if root.tag.split('}')[-1].lower() not in ('rss','feed','rdf'):raise ValueError('Response is not a supported feed')
  for item in root.iter():
   if item.tag.split('}')[-1] not in ('item','entry'):continue
   fields={c.tag.split('}')[-1]:c for c in item}
   def val(k):
    e=fields.get(k);return ''.join(e.itertext()).strip() if e is not None else ''
   link=val('link');le=fields.get('link')
   if not link and le is not None:link=le.get('href','')
   rows.append((val('title'),urllib.parse.urljoin(base,link),val('description') or val('summary') or val('content')))
 jobs=[];expired=0;rejected=[]
 for title,url,desc in rows:
  if not safe_url(url):continue
  end=deadline(desc)
  if end and end<NOW().date().isoformat():expired+=1;continue
  s,tr=rank(title,desc)
  if not s:rejected.append(title)
  if s:jobs.append(dict(title=html.unescape(title),url=canonical(url),source=source,score=s,track=tr,deadline=end,description=desc,last_seen=NOW().isoformat(),retained=False))
 return jobs,dict(format=mode,parsed=len(rows),expired=expired,rejected=rejected[:10]),feeds

def request(url):
 req=urllib.request.Request(url,headers={'User-Agent':'DamirJobRadar/15 public vacancy reader','Accept':'application/rss+xml,application/atom+xml,text/html;q=0.8,*/*;q=0.5'})
 with urllib.request.urlopen(req,timeout=15) as r:
  raw=r.read(MAX_BYTES+1)
  if len(raw)>MAX_BYTES:raise ValueError(f'Response exceeds {MAX_BYTES} byte safety limit')
  return raw,r.headers.get('Content-Type',''),r.geturl()

def permitted(url):
 p=urllib.parse.urlsplit(url);robots=urllib.parse.urlunsplit((p.scheme,p.netloc,'/robots.txt','',''))
 try:
  raw,_,_=request(robots);rp=urllib.robotparser.RobotFileParser();rp.parse(raw.decode('utf-8','replace').splitlines())
  if not rp.can_fetch('DamirJobRadar',url):raise PermissionError('robots.txt disallows automated collection')
 except urllib.error.HTTPError as e:
  if e.code!=404:raise

def oracle_payload(payload,name,base):
 # Read only JSON responses emitted by the public career page itself.
 rows=[]
 def walk(obj):
  if isinstance(obj,dict):
   title=obj.get('Title') or obj.get('title')
   ident=obj.get('Id') or obj.get('RequisitionId')
   if isinstance(title,str) and ident is not None and str(ident).isdigit():
    prefix=base.split('/jobs')[0]
    link=obj.get('ExternalUrl') or obj.get('JobUrl') or prefix+'/job/'+str(ident)
    if safe_url(link):
     desc=' '.join(str(obj.get(k) or '') for k in ['ShortDescriptionStr','ExternalQualificationsStr','ExternalResponsibilitiesStr','PrimaryLocation'])
     end=str(obj.get('PostingEndDate') or '')[:10]
     if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',end):end=deadline(desc)
     score,track=rank(title,desc)
     if score and (not end or end>=NOW().date().isoformat()):rows.append(dict(title=title,url=canonical(link),source=name,score=score,track=track,deadline=end,description=desc,last_seen=NOW().isoformat(),retained=False))
   for v in obj.values():walk(v)
  elif isinstance(obj,list):
   for v in obj:walk(v)
 walk(payload)
 return rows

def oracle_run(name,url):
 diagnostic=Path('site/diagnostics');diagnostic.mkdir(parents=True,exist_ok=True)
 notes=[];captured=[]
 try:
  permitted(url)
  from playwright.sync_api import sync_playwright
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   try:
    page=browser.new_page()  # standard browser UA, not an invented crawler UA
    def observe(response):
     if urllib.parse.urlsplit(response.url).netloc!=urllib.parse.urlsplit(url).netloc:return
     if 'recruitingCEJobRequisitions' not in response.url:return
     try:
      if response.ok:captured.extend(oracle_payload(response.json(),name,url))
     except Exception as e:notes.append(type(e).__name__)
    page.on('response',observe)
    response=page.goto(url,wait_until='domcontentloaded',timeout=60000)
    if response and response.status>=400:raise ValueError(f'Career page HTTP {response.status}')
    page.wait_for_timeout(8000)
    # Inspect links in every frame. No fixed site-ID path assumption.
    found={};previous=-1
    for _ in range(8):
     for frame in page.frames:
      try:
       content=frame.content()
       if re.search(r'captcha|verify you are human|access denied',content[:6000],re.I):raise PermissionError('Access challenge; not bypassed')
       links=frame.locator('a[href]').evaluate_all('(xs)=>xs.map(a=>({href:a.href,title:a.innerText||a.getAttribute("aria-label")||""}))')
       for link in links:
        u=link['href'];title=link['title'].strip()
        if not safe_url(u) or not re.search(r'/(?:jobs/preview|job)/\d+',urllib.parse.urlsplit(u).path):continue
        score,track=rank(title,'')
        if score:found[u]=dict(title=title,url=canonical(u),source=name,score=score,track=track,deadline=None,description='',last_seen=NOW().isoformat(),retained=False)
      except PermissionError:raise
      except Exception as e:notes.append(type(e).__name__)
     for job in captured:found[job['url']]=job
     if len(found)==previous:break
     previous=len(found)
     buttons=page.get_by_role('button',name=re.compile(r'show more|load more',re.I))
     if buttons.count() and buttons.first.is_visible():buttons.first.click(timeout=5000)
     else:page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
     page.wait_for_timeout(2500)
    # Public listing diagnostics only; no cookies, tokens, headers or network bodies saved.
    report=dict(final_url=page.url,title=page.title(),frames=len(page.frames),captured_matches=len(captured),matched_links=len(found),public_links=page.locator('a[href]').evaluate_all('(xs)=>xs.slice(0,30).map(a=>({href:a.href,title:a.innerText}))'),notes=notes[:10])
    (diagnostic/(name+'.json')).write_text(json.dumps(report,indent=2))
    try:page.screenshot(path=str(diagnostic/(name+'.png')),full_page=False)
    except Exception as e:notes.append('screenshot: '+type(e).__name__)
    if not found:raise ValueError('No relevant records extracted; see diagnostics/'+name+'.json and .png. Not proof of no vacancies.')
    return name,list(found.values()),dict(ok=True,message=f'Public page: {len(found)} matching records; bounded coverage; diagnostics saved')
   finally:browser.close()
 except Exception as e:
  (diagnostic/(name+'-error.txt')).write_text(type(e).__name__+': '+str(e)[:500])
  return name,[],dict(ok=False,message=f'{type(e).__name__}: {str(e)[:220]}')

def source_run(pair):
 name,urls=pair;attempts=[]
 if name in ORACLE:return oracle_run(name,urls[0])
 for url in urls:
  try:
   permitted(url);raw,ctype,final=request(url);jobs,info,feeds=parse(raw,ctype,final,name)
   if info['format']=='HTML' and not info['parsed']:
    for feed in feeds[:1]:
     if urllib.parse.urlsplit(feed).netloc!=urllib.parse.urlsplit(final).netloc:continue
     permitted(feed);r,c,f=request(feed);jobs,info,_=parse(r,c,f,name)
   if not info['parsed']:raise ValueError('No recognized vacancy records; page may require JavaScript or adapter update')
   return name,jobs,dict(ok=True,message=f"{info['format']}: {info['parsed']} records, {len(jobs)} matches, {info['expired']} expired removed",endpoint=final,rejected_examples=info.get('rejected',[]))
  except Exception as e:attempts.append(f'{url}: {type(e).__name__}: {str(e)[:160]}')
 return name,[],dict(ok=False,message=' | '.join(attempts))

ELIGIBILITY_WEIGHTS={'deadline':20,'external_access':20,'education':20,'experience':20,'work_rights':15,'language':5}
def assess(job):
 title=job.get('title','');desc=job.get('description','');text=norm(title+' '+desc)
 checks={k:dict(status='UNKNOWN',evidence='Not established from available vacancy/profile evidence') for k in ELIGIBILITY_WEIGHTS}
 def setcheck(k,status,evidence):checks[k]=dict(status=status,evidence=evidence)
 end=job.get('deadline')
 if end:setcheck('deadline','PASS' if end>=NOW().date().isoformat() else 'FAIL','Explicit closing date: '+end)
 if any(has(title,x) for x in ['open to all applicants','open to internal and external applicants','open to internal and external candidates','open to external applicants']):setcheck('external_access','PASS','External applicants explicitly included in title')
 if any(has(title,x) for x in ['internal candidates only','internal applicants only']) or re.search(r'open to tiers? [012 and]+ applicants',norm(title)) and not has(title,'external'):setcheck('external_access','FAIL','Internal-only restriction in title')
 # Only narrowly matched mandatory requirements, not inferred from job title.
 if re.search(r'(?:bachelor|master|degree).{0,60}(?:architecture|architectural engineering)',text):setcheck('education','PASS','Architecture/architectural-engineering degree wording; confirmed profile degrees. Check equivalence and additional conditions.')
 years=re.search(r'(?:minimum of|at least) (\d+) years? (?:of )?(?:relevant |professional )?experience',text)
 if years and int(years[1])<=2:setcheck('experience','PASS','Explicit minimum <=2 years; confirmed construction assignment September 2024-September 2026. Relevance still requires review.')
 # Native language is confirmed; English/French/Italian proficiency levels are not.
 if re.search(r'(?:fluency|fluent|native).{0,35}(?:bosnian|croatian|serbian)',text):setcheck('language','PASS','Bosnian/Croatian/Serbian: Native confirmed')
 if job.get('retained'):setcheck('deadline','UNKNOWN','Retained listing: current availability not rechecked')
 passed=sum(ELIGIBILITY_WEIGHTS[k] for k,v in checks.items() if v['status']=='PASS')
 failed=any(v['status']=='FAIL' for v in checks.values())
 unknown=any(v['status']=='UNKNOWN' for v in checks.values())
 return dict(score=passed,status='INELIGIBLE' if failed else 'NEEDS VERIFICATION' if unknown else 'CHECKED CRITERIA PASS',checks=checks)

def merge(old,results):
 previous={j['url']:j for j in old.get('jobs',[]) if safe_url(j.get('url',''))};out={};health={}
 for name,jobs,status in results:
  health[name]=status
  if not status['ok']:
   jobs=[]
   for j in previous.values():
    if j['source']!=name:continue
    try:age=NOW()-dt.datetime.fromisoformat(j['last_seen'])
    except (KeyError,ValueError,TypeError):continue
    if age>dt.timedelta(days=7) or (j.get('deadline') and j['deadline']<NOW().date().isoformat()):continue
    jobs.append(dict(j,retained=True))
  for j in jobs:out.setdefault(j['url'],dict(j,new=j['url'] not in previous))
 for j in out.values():j['eligibility']=assess(j)
 return dict(updated=NOW().isoformat(),jobs=sorted(out.values(),key=lambda j:(j['eligibility']['status']=='INELIGIBLE',-j['eligibility']['score'],-j['score'],j['title'])),sources=health)

PAGE=r"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Damir Job Radar V15</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto;padding:16px;background:#eef3f6;color:#123}header{background:#153b50;color:white;padding:24px;border-radius:14px}article,details{background:white;padding:18px;margin:12px 0;border-radius:10px}input,select,button{padding:12px;margin:10px 6px 10px 0}a{color:#075b9b}.warning{background:#fff0bf;padding:16px}</style><header><h1>Damir's Job Radar</h1><p>Construction · Infrastructure · WASH · Contracts · Facilities · Architecture</p></header><p id=status>Waiting for results...</p><input id=q placeholder="Search title or source" aria-label=Search><select id=track aria-label=Track><option value="">All tracks</option></select><button id=refresh>Refresh</button><main id=jobs></main><details open><summary>Source health</summary><ul id=health></ul></details><details><summary>Other ways to find jobs</summary><p>These are manual search links, NOT automatically collected results.</p><ul id=manual></ul></details><p>Ranked by confirmed eligibility evidence, not a hiring probability. Unknown criteria earn no points and remain visible. Nationality/work rights are not assumed. Expired known dates are removed; retained results are marked unverified. No AI, email or paid API.</p><script>
const data=__DATA__,el=id=>document.getElementById(id);
function render(){el('jobs').replaceChildren();let n=0;for(const j of data.jobs){if(el('track').value&&j.track!==el('track').value)continue;if(![j.title,j.source,j.track].join(' ').toLowerCase().includes(el('q').value.toLowerCase()))continue;let u;try{u=new URL(j.url);if(!['http:','https:'].includes(u.protocol))continue}catch{continue}const a=document.createElement('a'),h=document.createElement('h2'),p=document.createElement('p'),card=document.createElement('article');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent=j.title;h.append(a);p.textContent=`${j.source} | ${j.track} | Eligibility evidence ${j.eligibility?j.eligibility.score:0}/100 (${j.eligibility?j.eligibility.status:'NEEDS VERIFICATION'}) | ${j.retained?'RETAINED, source unavailable':j.new?'NEW':'Seen before'} | Deadline: ${j.deadline||'not verified'}`;card.append(h,p);if(j.eligibility){const details=document.createElement('details'),sum=document.createElement('summary');sum.textContent='Eligibility checks and evidence';details.append(sum);for(const [key,c]of Object.entries(j.eligibility.checks)){const line=document.createElement('p');line.textContent=key+': '+c.status+' — '+c.evidence;details.append(line)}card.append(details)}el('jobs').append(card);n++}if(!n){const p=document.createElement('p');p.className='warning';p.textContent='No matching jobs. Check source health and manual search links. This is not proof that no vacancies exist.';el('jobs').append(p)}}
el('status').textContent=`Updated ${data.updated} | ${data.jobs.length} results | ${Object.values(data.sources).filter(s=>s.ok).length}/${Object.keys(data.sources).length} sources responding`;
for(const [name,s]of Object.entries(data.sources)){const li=document.createElement('li');li.textContent=`${name}: ${s.ok?'OK':'UNAVAILABLE'} - ${s.message}${s.rejected_examples&&s.rejected_examples.length?' | Rejected examples: '+s.rejected_examples.join('; '):''}`;el('health').append(li)}
for(const t of [...new Set(data.jobs.map(j=>j.track))].sort())el('track').add(new Option(t,t));
for(const [name,url]of data.manual){const li=document.createElement('li'),a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=name;li.append(a);el('manual').append(li)}
el('q').oninput=render;el('track').onchange=render;el('refresh').onclick=()=>location.reload();render();</script></html>"""
MANUAL=[('IOM official careers',ORACLE['IOM']),('UNDP official careers','https://estm.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs'),('UNICEF official alerts','https://jobs.unicef.org/cw/en-us/subscribe/'),('UNOPS','https://careers.unops.org/'),('UN Careers','https://careers.un.org/'),('UNjobs civil engineering','https://unjobs.org/skills/civil-engineer'),('Impactpool engineering','https://www.impactpool.org/search?occupational_groups%5B%5D=Engineering'),('UNJobsFeed','https://unjobsfeed.org/'),('ReliefWeb API approval required','https://apidoc.reliefweb.int/')]

def build_page(data):
 payload=json.dumps(dict(data,manual=MANUAL),ensure_ascii=True).replace('<',r'\u003c').replace('>',r'\u003e').replace('&',r'\u0026')
 return PAGE.replace('__DATA__',payload)

def run():
 old={}
 try:
  raw,_,_=request(os.environ.get('PREVIOUS_DATA_URL',''));old=json.loads(raw)
 except Exception:pass
 with cf.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(source_run,SOURCES.items()))
 data=merge(old,results);Path('site').mkdir(exist_ok=True)
 Path('site/index.html').write_text(build_page(data),encoding='utf-8');Path('site/jobs.json').write_text(json.dumps(data),encoding='utf-8')
 summary='# Job Radar V15\n\n'+f"{len(data['jobs'])} matches; {sum(s['ok'] for s in data['sources'].values())}/{len(SOURCES)} sources responding.\n\n"+'\n'.join(f"- {n}: {s['message']}" for n,s in data['sources'].items())
 if os.environ.get('GITHUB_STEP_SUMMARY'):Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary,encoding='utf-8')
 print(summary)

class Tests(unittest.TestCase):
 def test_eligibility_unknown(self):
  a=assess({'title':'Civil Engineer'});self.assertEqual(a['score'],0);self.assertEqual(a['status'],'NEEDS VERIFICATION')
 def test_no_work_rights_inference(self):self.assertEqual(assess({'title':'Civil Engineer Sarajevo'})['checks']['work_rights']['status'],'UNKNOWN')
 def test_eligibility_deadline(self):self.assertEqual(assess({'deadline':'2001-01-01'})['status'],'INELIGIBLE')
 def test_external_evidence(self):self.assertEqual(assess({'title':'Civil Engineer Open to internal and external applicants'})['score'],20)
 def test_retained_unknown(self):self.assertEqual(assess({'deadline':'2099-01-01','retained':True})['checks']['deadline']['status'],'UNKNOWN')
 def test_oracle_payload(self):
  x={'items':[{'requisitionList':[{'Id':'123','Title':'Civil Engineer','PostingEndDate':'2099-01-01'}]}]}
  self.assertEqual(len(oracle_payload(x,'UNDP',ORACLE['UNDP'])),1)
 def test_oracle_expired(self):
  self.assertEqual(oracle_payload({'Id':'123','Title':'Civil Engineer','PostingEndDate':'2001-01-01'},'UNDP',ORACLE['UNDP']),[])

 def test_procurement_nonworks(self):self.assertEqual(rank('Procurement Officer','vaccines')[0],0)
 def test_procurement_works(self):self.assertGreater(rank('Procurement Officer','civil works')[0],0)
 def test_tier3_allowed(self):self.assertGreater(rank('Civil Engineer Open to Tier 1 2 3 applicants','')[0],0)

 def test_iom_html(self):
  raw=b'<html><a href="/hcmUI/CandidateExperience/en/sites/CX_1001/jobs/preview/123">Infrastructure Field Engineer (Consultant)</a></html>'
  self.assertEqual(len(parse(raw,'text/html',ORACLE['IOM'],'IOM')[0]),1)
 def test_unicef_limit(self):self.assertGreater(MAX_BYTES,3_000_000)
 def test_rejected_diagnostics(self):
  _,info,_=parse(b'<rss><item><title>Finance Analyst</title><link>https://x/1</link></item></rss>','text/xml','https://x','UNOPS')
  self.assertEqual(info['rejected'],['Finance Analyst'])
 def test_construction_officer(self):self.assertGreater(rank('Construction Officer (NO-2)','')[0],0)
 def test_field_engineer(self):self.assertGreater(rank('Infrastructure Field Engineer (Consultant)','')[0],0)

 def test_undp_html(self):
  raw=b'<html><a href="/hcmUI/CandidateExperience/en/sites/CX_1/jobs/preview/12345">Civil Engineer</a><a href="/help">Construction Engineer</a></html>'
  jobs,info,_=parse(raw,'text/html','https://estm.fa.em2.oraclecloud.com','UNDP')
  self.assertEqual(len(jobs),1);self.assertEqual(jobs[0]['source'],'UNDP')
 def test_undp_js_shell(self):
  self.assertEqual(parse(b'<html><div id="app"></div></html>','text/html','https://estm.fa.em2.oraclecloud.com','UNDP')[1]['parsed'],0)
 def test_undp_tier(self):
  self.assertEqual(rank('Civil Engineer Open to Tier 1 & 2 applicants','')[0],0)
 def test_undp_external(self):
  self.assertGreater(rank('Civil Engineer Open to internal and external applicants','')[0],0)

 def test_xml(self):self.assertEqual(len(parse(b'<rss><item><title>Construction Engineer</title><link>https://x/1</link></item></rss>','application/xml','https://x','UNOPS')[0]),1)
 def test_bare_amp(self):self.assertEqual(len(parse(b'<rss><item><title>Construction Engineer & Supervisor</title><link>https://x/1?a=1&b=2</link></item></rss>','text/xml','https://x','UNOPS')[0]),1)
 def test_control(self):self.assertEqual(len(parse(b'<rss><item><title>Construction\x01 Engineer</title><link>https://x/1</link></item></rss>','text/xml','https://x','UNOPS')[0]),1)
 def test_html(self):self.assertEqual(len(parse(b'<html><a href="/vacancies/123">Civil Engineer</a></html>','text/html','https://unjobs.org','UNjobs')[0]),1)
 def test_html_not_xml(self):self.assertEqual(parse(b'<html><p>JavaScript required</p></html>','text/html','https://x','UN Careers')[1]['parsed'],0)
 def test_challenge(self):
  with self.assertRaises(ValueError):parse(b'<html>Verify you are human</html>','text/html','https://x','UNOPS')
 def test_malformed(self):
  with self.assertRaises(ET.ParseError):parse(b'<rss><item>','text/xml','https://x','UNOPS')
 def test_atom(self):self.assertEqual(len(parse(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Site Engineer</title><link href="https://x/2"/></entry></feed>','text/xml','https://x','UNOPS')[0]),1)
 def test_nav(self):self.assertEqual(parse(b'<html><a href="/about">Construction Engineer</a></html>','text/html','https://unjobs.org','UNjobs')[1]['parsed'],0)
 def test_bad_url(self):self.assertFalse(safe_url('javascript:alert(1)'))
 def test_canonical(self):self.assertEqual(canonical('https://x/a?utm_source=z&id=1#top'),'https://x/a?id=1')
 def test_deadline(self):self.assertEqual(deadline('Deadline: November 12, 2026'),'2026-11-12')
 def test_expired(self):self.assertEqual(parse(b'<rss><item><title>Civil Engineer</title><link>https://x/1</link><description>Deadline: 2001-01-01</description></item></rss>','text/xml','https://x','UNOPS')[0],[])
 def test_internal(self):self.assertEqual(rank('Construction Engineer','For internal candidates only')[0],0)
 def test_international(self):self.assertGreater(rank('International Construction Engineer','')[0],0)
 def test_digital(self):self.assertEqual(rank('Cloud Infrastructure Engineer','construction')[0],0)
 def test_wash_soft(self):self.assertEqual(rank('WASH Programme Officer','hygiene promotion')[0],0)
 def test_title_tracks(self):
  for track,terms in TRACKS.items():
   for t in terms:self.assertGreater(rank(t,'civil works' if t in ('procurement specialist','procurement officer') else '')[0],0,t)
 def test_retention(self):
  j=dict(url='https://x/1',title='Civil Engineer',source='UNOPS',score=24,last_seen=NOW().isoformat())
  self.assertTrue(merge({'jobs':[j]},[('UNOPS',[],{'ok':False})])['jobs'][0]['retained'])
 def test_stale(self):
  j=dict(url='https://x/1',title='Civil Engineer',source='UNOPS',score=24,last_seen=(NOW()-dt.timedelta(days=8)).isoformat())
  self.assertEqual(merge({'jobs':[j]},[('UNOPS',[],{'ok':False})])['jobs'],[])
 def test_dedupe(self):
  j=dict(url='https://x/1',title='Civil Engineer',source='UNOPS',score=24)
  self.assertEqual(len(merge({},[('UNOPS',[j,j],{'ok':True})])['jobs']),1)
 def test_script_escape(self):
  p=build_page({'jobs':[{'title':'</script><script>alert(1)</script>'}],'sources':{}})
  self.assertNotIn('</script><script>alert',p)
 def test_discovery(self):self.assertEqual(parse(b'<html><link rel="alternate" type="application/rss+xml" href="/feed"></html>','text/html','https://x','UNOPS')[2],['https://x/feed'])
 def test_utf8_bom(self):self.assertEqual(decode(b'\xef\xbb\xbf<rss/>','text/xml'),'<rss/>')

if __name__=='__main__':
 if sys.argv[1:]==['test']:unittest.main(argv=[sys.argv[0]])
 else:run()
