let publishedIndex=null;
let routeToken=0;

function asset(path){
  return new URL(path, document.baseURI).href;
}

async function loadJson(path){
  const res=await fetch(asset(path), {cache:'no-store'});
  if(!res.ok) throw new Error(path+' '+res.status);
  return res.json();
}

function editionByDate(date){
  return (publishedIndex.editions||[]).find((item)=>item.date===date);
}

function fillSelect(selected){
  const select=document.getElementById('edition-date');
  const dates=(publishedIndex.editions||[]).map((item)=>item.date).sort().reverse();
  select.replaceChildren();
  dates.forEach((date)=>{
    const item=editionByDate(date);
    const opt=document.createElement('option');
    opt.value=date;
    const cov=item&&item.coverage;
    opt.textContent=cov ? date+'　覆盖 '+cov.start+' – '+cov.end : date;
    select.appendChild(opt);
  });
  if(selected) select.value=selected;
}

function setMeta(edition){
  const meta=document.getElementById('edition-meta');
  const cov=edition.coverage||{};
  meta.textContent='发布日期 '+edition.publishDate+' · 覆盖 '+cov.start+' – '+cov.end;
}

function hideNotice(){
  const box=document.getElementById('notice');
  box.hidden=true;
  box.replaceChildren();
}

function showNotice(message, withReturn){
  const box=document.getElementById('notice');
  box.hidden=false;
  box.replaceChildren();
  box.appendChild(document.createTextNode(message));
  if(withReturn){
    const btn=document.createElement('button');
    btn.type='button';
    btn.dataset.latest='1';
    btn.textContent='回到最新一期';
    box.appendChild(btn);
  }
}

function pushDate(date){
  const url=new URL(location.href);
  url.searchParams.set('date', date);
  history.pushState({date}, '', url.pathname+url.search+url.hash);
}

async function route(){
  const token=++routeToken;
  let index;
  try{
    index=await loadJson('data/index.json');
  }catch(err){
    if(token!==routeToken) return;
    window.DashboardRender.clearEdition();
    const period=document.getElementById('period');
    if(period) period.textContent='已发布列表没有载入。';
    showNotice('已发布列表没有载入。页面不会留下空白图表，也不会另造一期。', false);
    return;
  }
  if(token!==routeToken) return;
  publishedIndex=index;
  const known=new Set((index.editions||[]).filter((item)=>item.status==='published').map((item)=>item.date));
  const requested=new URLSearchParams(location.search).get('date');
  const latest=index.latest;
  let date=latest;
  let invalid=false;
  if(requested){
    if(known.has(requested)) date=requested;
    else invalid=true;
  }
  if(!date||!known.has(date)){
    window.DashboardRender.clearEdition();
    showNotice('已发布列表里没有可显示的期次。', false);
    return;
  }
  const entry=editionByDate(date);
  let edition;
  try{
    edition=await loadJson(entry.file);
  }catch(err){
    if(token!==routeToken) return;
    window.DashboardRender.clearEdition();
    showNotice('这一期的文件没有载入。线上仍应停留在上一份已发布版本，这里不会用空图或估出来的数字填上。', false);
    return;
  }
  if(token!==routeToken) return;
  window.DashboardRender.renderEdition(edition);
  fillSelect(date);
  setMeta(edition);
  if(invalid){
    showNotice('没有已发布的 '+requested+'。期次列表里只有已发布的日期，不会另造一版。当前图表是最新一期 '+latest+'。', true);
  }else{
    hideNotice();
  }
}

document.getElementById('edition-date').addEventListener('change', ()=>{
  const date=document.getElementById('edition-date').value;
  if(!date) return;
  const current=new URLSearchParams(location.search).get('date');
  if(current===date && document.getElementById('notice').hidden) return;
  pushDate(date);
  route();
});

document.getElementById('notice').addEventListener('click', (event)=>{
  const btn=event.target.closest('button[data-latest]');
  if(!btn||!publishedIndex) return;
  document.getElementById('edition-date').value=publishedIndex.latest;
  document.getElementById('edition-date').dispatchEvent(new Event('change'));
});

window.addEventListener('popstate', ()=>{ route(); });
route();
