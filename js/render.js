function el(tag, className){
  const node=document.createElement(tag);
  if(className) node.className=className;
  return node;
}

function renderCard(card){
  const root=el('div','card');
  const h2=el('h2');
  h2.innerHTML=card.titleHtml;
  root.appendChild(h2);
  const src=el('div','src');
  src.innerHTML=card.sourceHtml;
  root.appendChild(src);
  const stats=el('div','stats');
  (card.stats||[]).forEach((s)=>{
    const stat=el('div','stat');
    const k=el('span','k');
    k.textContent=s.k;
    const v=el('span', s.tone ? 'v '+s.tone : 'v');
    v.textContent=s.v;
    stat.appendChild(k);
    stat.appendChild(v);
    stats.appendChild(stat);
  });
  root.appendChild(stats);
  const box=el('div','chartbox');
  const canvas=document.createElement('canvas');
  canvas.id=card.chart.id;
  box.appendChild(canvas);
  root.appendChild(box);
  const a=document.createElement('a');
  a.className='viewsrc';
  a.href=card.primary.href;
  if(card.primary.target) a.target=card.primary.target;
  if(card.primary.rel) a.rel=card.primary.rel;
  a.innerHTML=card.primary.html;
  root.appendChild(a);
  const cite=el('div','cite');
  cite.innerHTML=card.citeHtml;
  root.appendChild(cite);
  const take=el('div','take');
  take.innerHTML=card.takeHtml;
  root.appendChild(take);
  const why=el('div','why');
  why.innerHTML=card.whyHtml;
  root.appendChild(why);
  return root;
}

function renderEdition(edition){
  window.DashboardCharts.destroyCharts();
  if(edition.documentTitle) document.title=edition.documentTitle;
  document.getElementById('page-title').textContent=edition.title;
  document.getElementById('period').innerHTML=edition.periodHtml;
  document.getElementById('thesis').innerHTML=edition.thesisHtml;
  const grid=document.getElementById('grid');
  grid.replaceChildren(...(edition.cards||[]).map(renderCard));
  const closing=document.getElementById('closing');
  const h3=el('h3');
  h3.textContent=(edition.closing&&edition.closing.title)||'';
  const p=el('p');
  p.innerHTML=(edition.closing&&edition.closing.html)||'';
  closing.replaceChildren(h3, p);
  const footer=document.getElementById('footer');
  footer.replaceChildren();
  const h4=el('h4');
  h4.textContent=(edition.footer&&edition.footer.heading)||'';
  footer.appendChild(h4);
  const srcgrid=el('div','srcgrid');
  ((edition.footer&&edition.footer.links)||[]).forEach((link)=>{
    const a=document.createElement('a');
    a.href=link.href;
    if(link.target) a.target=link.target;
    if(link.rel) a.rel=link.rel;
    a.textContent=link.text;
    srcgrid.appendChild(a);
  });
  footer.appendChild(srcgrid);
  const disc=el('div','disc');
  disc.innerHTML=(edition.footer&&edition.footer.disclaimerHtml)||'';
  footer.appendChild(disc);
  (edition.cards||[]).forEach((card)=>{
    const canvas=document.getElementById(card.chart.id);
    window.DashboardCharts.mountChart(canvas, card.chart);
  });
}

function clearEdition(){
  window.DashboardCharts.destroyCharts();
  const grid=document.getElementById('grid');
  if(grid) grid.replaceChildren();
  ['thesis','closing','footer'].forEach((id)=>{
    const node=document.getElementById(id);
    if(node) node.replaceChildren();
  });
}

window.DashboardRender={renderEdition, clearEdition, renderCard};
