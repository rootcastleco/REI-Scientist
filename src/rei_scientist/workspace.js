'use strict';
// The workspace is local-only. No telemetry, third-party scripts, code execution or external calls.
const $ = id => document.getElementById(id);
let token = '';
let templates = {};
let records = [];
let current = null;
let revision = 0;
let draft = null;
let activeTab = 'protocol';
let noticeTimer = null;
const esc = value => (value === null || value === undefined ? '—' : String(value));

function notice(message, error=false) {
  const el = $('notice');
  el.textContent = message;
  el.classList.toggle('error', error);
  el.hidden = false;
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { el.hidden = true; }, 8000);
}
async function api(path, method='GET', payload=null) {
  const opts = {method, cache:'no-store', headers:{}};
  if (payload !== null) {
    opts.headers['Content-Type'] = 'application/json';
    opts.headers['X-REI-Token'] = token;
    opts.body = JSON.stringify(payload);
  }
  const response = await fetch(path, opts);
  let body;
  try { body = await response.json(); } catch { throw Error('Beklenmeyen sunucu cevabı.'); }
  if (!response.ok) throw Error(body.error || `HTTP ${response.status}`);
  return body;
}
function make(tag, className='', text=null) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== null) e.textContent = text;
  return e;
}
function nested(object, path) {return path.split('.').reduce((value,key) => value?.[key], object);}
function setNested(object, path, value) {
  const parts = path.split('.'); let dest = object;
  for (const part of parts.slice(0,-1)) dest = dest[part];
  dest[parts[parts.length-1]] = value;
}
function collect() {
  if (!draft) return;
  const next = structuredClone(draft);
  for (const input of document.querySelectorAll('#editor [data-field]')) {
    next[input.dataset.field] = input.value;
  }
  for (const input of document.querySelectorAll('#editor [data-number]')) {
    const value = input.value.trim();
    if (!value) throw Error(`${input.dataset.number}: sayısal değer gerekli`);
    next[input.dataset.number] = Number(value);
  }
  for (const input of document.querySelectorAll('#editor [data-nested]')) {
    setNested(next, input.dataset.nested, input.value);
  }
  for (const input of document.querySelectorAll('#editor [data-json]')) {
    try { setNested(next, input.dataset.json, JSON.parse(input.value)); }
    catch { input.focus(); throw Error(`${input.dataset.json}: geçerli JSON gerekli`); }
  }
  draft = next;
  updateHeader();
  return next;
}
function renderFields() {
  if (!draft) return;
  for (const input of document.querySelectorAll('#editor [data-field]')) input.value = draft[input.dataset.field];
  for (const input of document.querySelectorAll('#editor [data-number]')) input.value = draft[input.dataset.number];
  for (const input of document.querySelectorAll('#editor [data-nested]')) input.value = nested(draft, input.dataset.nested);
  for (const input of document.querySelectorAll('#editor [data-json]')) {
    input.value = JSON.stringify(nested(draft, input.dataset.json), null, 2);
  }
  updateHeader();
  renderFormula();
  renderResults();
}
function updateHeader() {
  if (!draft) return;
  $('pageTitle').textContent = draft.title;
  $('pageSubtitle').textContent = draft.research_question;
  $('statusPill').textContent = draft.status;
  $('verifyPill').textContent = draft.verification_status;
  $('revisionLabel').textContent = current ? `REVISION ${revision}` : 'Yeni, henüz kaydedilmedi';
  $('saveBtn').disabled = false;
}
function renderFormula() {
  const formula = $('formula');
  if (!draft) return;
  const terms = draft.objective.terms;
  formula.textContent = `${draft.objective.sense.toUpperCase()} J(x) = ` + (
    terms.length ? terms.map(t=> `${t.weight} × (${t.variable} / (${t.scale} ${t.scale_unit}))²`).join(' + ') : 'NOT VERIFIED');
}
function renderResults() {
  $('resultsBody').replaceChildren();
  if (!draft) return;
  const units = Object.fromEntries(draft.variables.map(v => [v.symbol, v.unit]));
  for (const result of draft.results) {
    const tr = make('tr');
    const diff = Number.isFinite(result.baseline) && Number.isFinite(result.candidate) ? result.candidate - result.baseline : null;
    const vals = [result.variable, units[result.variable] || '?', result.baseline, result.candidate, diff, result.verification];
    for (let i=0;i<vals.length;i++) tr.append(make('td', i>1 && i<5 ? 'num':'', esc(vals[i])));
    $('resultsBody').append(tr);
  }
  if (!draft.results.length) {
    const tr=make('tr'); const td=make('td','', 'NOT VERIFIED — ölçüm kaydı yok');td.colSpan=6;tr.append(td);$('resultsBody').append(tr);
  }
}
function setTab(tab) {
  if (draft && activeTab !== tab) {
    try { collect(); } catch (error) { notice(error.message,true); return; }
  }
  activeTab = tab;
  for (const name of ['protocol','model','plan','results','history']) {
    $('tab'+name[0].toUpperCase()+name.slice(1)).hidden = name !== tab;
  }
  for (const button of document.querySelectorAll('.tab')) button.classList.toggle('active',button.dataset.tab===tab);
  if (tab==='plan') loadPlan();
  if (tab==='history') loadHistory();
  if (tab==='results') loadFigure();
  if (tab==='model') renderFormula();
}
function showEditor() {
  $('welcome').hidden = true; $('editor').hidden = false;
  activeTab = 'protocol';
  for (const name of ['protocol','model','plan','results','history']) {
    $('tab'+name[0].toUpperCase()+name.slice(1)).hidden = name !== 'protocol';
  }
  for (const b of document.querySelectorAll('.tab')) b.classList.toggle('active',b.dataset.tab==='protocol');
  renderFields();
}
function showWelcome() {
  draft=null;current=null;revision=0;
  $('welcome').hidden = false; $('editor').hidden = true;
  $('pageTitle').textContent = 'Ar-Ge çalışma merkezi';
  $('pageSubtitle').textContent = 'Kanıta dayalı araştırma, boyutsal doğrulama ve izlenebilir deney kayıtları.';
  $('revisionLabel').textContent = 'Kayıt seçilmedi';
  $('saveBtn').disabled = true;
  renderList();
}
function newFrom(project) {
  current=null;revision=0;draft=structuredClone(templates[project]);showEditor();renderList();
}
async function loadRecord(id) {
  try {
    const record=await api('/api/studies/'+encodeURIComponent(id));
    current=record.id;revision=record.revision;draft=record.study;showEditor();renderList();
  } catch (error) { notice(error.message,true); }
}
async function save() {
  if (!draft) return;
  let value;
  try { value=collect(); } catch(error) { notice(error.message,true);return; }
  $('saveBtn').disabled=true;
  try {
    const record = current
      ? await api('/api/studies/'+current, 'PUT', {revision,study:value})
      : await api('/api/studies','POST',{study:value});
    current=record.id;revision=record.revision;draft=record.study;
    renderFields(); await refreshList();notice(`Kayıt saklandı. Revision ${revision}.`);
    if (activeTab === 'results') loadFigure();
  } catch(error) {notice(`Kaydetme başarısız: ${error.message}`,true);}
  finally { $('saveBtn').disabled=false; }
}
async function refreshList() {
  try {
    const params = new URLSearchParams({q:$('search').value,project:$('filterProject').value,status:$('filterStatus').value});
    records = await api('/api/studies?'+params.toString());
    renderList();
  } catch(error) {notice(error.message,true);}
}
function renderList() {
  const list=$('recordList');list.replaceChildren();$('recordCount').textContent=String(records.length);
  for (const r of records) {
    const b=make('button','record'+(current===r.id?' selected':''));
    b.type='button';b.append(make('strong','',r.title),make('small','',`${r.project} · r${r.revision} · ${r.status}`));
    b.addEventListener('click',()=>loadRecord(r.id));list.append(b);
  }
  if (!records.length) list.append(make('div','hint','Henüz kayıt yok veya filtreyle eşleşmedi.'));
}
async function loadPlan() {
  if (!current) { $('planText').textContent='Planı üretmek için çalışma kaydını kaydet.';return; }
  try {
    const r = await fetch('/api/studies/'+current+'/plan.md',{cache:'no-store'});
    if (!r.ok) throw Error(`HTTP ${r.status}`);
    $('planText').textContent=await r.text();
  } catch(error) {notice(error.message,true);}
}
async function loadHistory() {
  const out=$('historyList');out.replaceChildren();
  if (!current) {out.textContent='Önce çalışma kaydet.';return;}
  try {
    const versions=await api('/api/studies/'+current+'/versions');
    for (const v of versions) {
      const row=make('div','history-entry');const meta=make('div');
      meta.append(make('strong','',`Revision ${v.revision}`),make('div','hint',v.created_at));row.append(meta);
      if (v.revision!==revision) {
        const button=make('button','button','Bu sürüme dön');
        button.addEventListener('click',()=>restore(v.revision));row.append(button);
      } else row.append(make('span','pill','CURRENT'));
      out.append(row);
    }
  } catch(error) {notice(error.message,true);}
}
async function restore(sourceRevision) {
  if (!confirm(`Revision ${sourceRevision} içeriği yeni revizyon olarak geri yüklensin mi?`)) return;
  try {
    const r=await api('/api/studies/'+current+'/restore','POST',{revision,source_revision:sourceRevision});
    revision=r.revision;draft=r.study;renderFields();await refreshList();await loadHistory();notice(`Geri yükleme yeni revision ${revision} olarak kaydedildi.`);
  } catch(error) {notice(error.message,true);}
}
function loadFigure() {
  const target=$('figureWrap');target.replaceChildren();
  if (!current) {target.textContent='Şekil üretmek için kaydedilmiş ölçüm gerekir.';return;}
  const img=make('img');img.alt='Baseline ve aday yöntem: kaydedilmiş ölçümler; bilimsel doğrulama ayrıca gereklidir.';
  img.src='/api/studies/'+current+'/figure.svg';img.style.cssText='width:100%;height:auto;max-width:900px';
  target.append(img);
}
function exportFile(suffix) {
  if (!current) {notice('Dışa aktarma için önce kaydet.',true);return;}
  const a=make('a');a.href='/api/studies/'+current+'/'+suffix;
  a.download=suffix==='export.json'?'study-record.json':suffix==='plan.md'?'study-plan.md':suffix==='figure.svg'?'study-figure.svg':'study-results.csv';
  document.body.append(a);a.click();a.remove();
}
function buildTemplates() {
  const grid=$('templateGrid');grid.replaceChildren();
  for (const [name,stud] of Object.entries(templates)) {
    const b=make('button','template');b.type='button';b.append(make('strong','',name),make('span','',stud.research_question));
    b.addEventListener('click',()=>newFrom(name));grid.append(b);
  }
}
async function start() {
  try {
    const info=await api('/api/bootstrap');token=info.token;
    for(const project of info.projects) {
      for (const sel of [$('filterProject'),$('project')]) {
        const opt=make('option','',project);opt.value=project;sel.append(opt);
      }
    }
    templates=await api('/api/templates');buildTemplates();
    $('newBtn').addEventListener('click',showWelcome);
    $('saveBtn').addEventListener('click',save);
    for (const tab of document.querySelectorAll('.tab')) tab.addEventListener('click',()=>setTab(tab.dataset.tab));
    for (const id of ['filterProject','filterStatus']) $(id).addEventListener('change',refreshList);
    let searchTimer;
    $('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(refreshList,180);});
    $('exportPlan').addEventListener('click',()=>exportFile('plan.md'));
    $('exportCsv').addEventListener('click',()=>exportFile('results.csv'));
    $('exportSvg').addEventListener('click',()=>exportFile('figure.svg'));
    $('exportJson').addEventListener('click',()=>exportFile('export.json'));
    for (const el of document.querySelectorAll('textarea[data-json="results"]')) el.addEventListener('change',()=>{
      try {collect();renderResults();} catch(error) {notice(error.message,true);}
    });
    for (const el of document.querySelectorAll('textarea[data-json="objective.terms"]')) el.addEventListener('change',()=>{
      try {collect();renderFormula();} catch(error) {notice(error.message,true);}
    });
    await refreshList();$('connection').textContent='127.0.0.1 · Local only';
  } catch(error) {$('connection').textContent='Bağlantı yok';notice(`Başlatılamadı: ${error.message}`,true);}
}
start();
