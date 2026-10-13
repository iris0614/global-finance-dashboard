(function(){
  const KEY='speech-lang';
  const UI={
    zh:{
      guide:'导读',
      background:'背景',
      points:'要点',
      notes:'脚注',
      missingGuide:'英文导读未收录',
      missingTitle:'英文标题未收录',
      missingBlock:'本段未收录',
      loading:'正在载入讲话…',
      error:'讲话没有载入。'
    },
    en:{
      guide:'Introduction',
      background:'Background',
      points:'Main points',
      notes:'Notes',
      missingGuide:'English introduction is not in the source.',
      missingTitle:'English heading is not in the source.',
      missingBlock:'This passage is not in the source.',
      loading:'Loading the speech…',
      error:'The speech did not load.'
    }
  };

  const titleEl=document.getElementById('speech-title');
  const metaEl=document.getElementById('speech-meta');
  const stackEl=document.getElementById('speech');
  const noticeEl=document.getElementById('notice');
  const btnZh=document.getElementById('lang-zh');
  const btnEn=document.getElementById('lang-en');
  let doc=null;
  let lang='zh';

  function storedLang(){
    try{
      const v=localStorage.getItem(KEY);
      if(v==='zh'||v==='en') return v;
    }catch(e){}
    return null;
  }

  function remember(next){
    try{localStorage.setItem(KEY,next);}catch(e){}
  }

  function langFromUrl(){
    const q=new URLSearchParams(location.search).get('lang');
    if(q==='zh'||q==='en') return q;
    return null;
  }

  function resolveLang(){
    return langFromUrl()||storedLang()||'zh';
  }

  function writeUrl(next,mode){
    const url=new URL(location.href);
    url.searchParams.set('lang',next);
    if(mode==='push') history.pushState({lang:next},'',url);
    else history.replaceState({lang:next},'',url);
  }

  function esc(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function withNotes(s){
    return esc(s).replace(/\[(\d+)\]/g,function(_,n){
      return '<sup class="fnref"><a href="#fn-'+n+'">['+n+']</a></sup>';
    });
  }

  function field(obj,code){
    if(!obj) return null;
    const status=obj[code+'Status'];
    const text=obj[code];
    if(status==='missing'||text==null||text==='') return null;
    return text;
  }

  function p(className,html){
    const el=document.createElement('p');
    if(className) el.className=className;
    el.innerHTML=html;
    return el;
  }

  function missing(text){
    return p('missing',esc(text));
  }

  function labeled(className,label,text){
    return p(className,'<span class="lbl">'+esc(label)+'</span>'+withNotes(text));
  }

  function prose(text){
    return p('',withNotes(text));
  }

  function sectionTitle(text){
    const h=document.createElement('h2');
    h.textContent=text;
    return h;
  }

  function paintChrome(){
    const ui=UI[lang];
    document.documentElement.lang=lang==='zh'?'zh-CN':'en';
    btnZh.setAttribute('aria-pressed',lang==='zh'?'true':'false');
    btnEn.setAttribute('aria-pressed',lang==='en'?'true':'false');
    if(!doc){
      metaEl.textContent=ui.loading;
      return;
    }
    const zhTitle=doc.title&&doc.title.zh;
    const enTitle=doc.title&&doc.title.en;
    titleEl.textContent=(zhTitle||'')+(zhTitle&&enTitle?' / ':'')+(enTitle||'');
    document.title=titleEl.textContent;
    metaEl.replaceChildren();
    const speaker=field(doc.speaker,lang);
    const role=field(doc.role,lang);
    const who=[speaker,role].filter(Boolean).join(' · ');
    if(who) metaEl.appendChild(document.createTextNode(who));
    const dateText=field(doc.dateLabel,lang)||doc.date||'';
    const occasion=field(doc.occasion,lang);
    [dateText,occasion].filter(Boolean).forEach(function(line){
      metaEl.appendChild(document.createElement('br'));
      metaEl.appendChild(document.createTextNode(line));
    });
    if(doc.source&&doc.source.url){
      metaEl.appendChild(document.createElement('br'));
      const a=document.createElement('a');
      a.href=doc.source.url;
      a.rel='noopener';
      const label=field(doc.source.label,lang);
      a.textContent=label||doc.source.url;
      metaEl.appendChild(a);
    }
  }

  function guideCard(){
    const ui=UI[lang];
    const guide=doc.guide&&doc.guide[lang];
    if(!guide||guide.status==='missing') return null;
    const card=document.createElement('div');
    card.className='card';
    card.appendChild(sectionTitle(ui.guide));
    if(guide.kicker) card.appendChild(p('src',esc(guide.kicker)));
    const background=guide.background||[];
    background.forEach(function(text,i){
      card.appendChild(i===0?labeled('take',ui.background,text):prose(text));
    });
    const points=guide.corePoints||[];
    points.forEach(function(text,i){
      card.appendChild(i===0?labeled('take',ui.points,text):prose(text));
    });
    if(guide.marketReaction) card.appendChild(prose(guide.marketReaction));
    return card;
  }

  function chapterCard(chapter,index){
    const ui=UI[lang];
    const card=document.createElement('section');
    card.className='card';
    const heading=field(chapter.title,lang);
    if(heading) card.appendChild(sectionTitle(heading));
    else if(index===0) card.appendChild(sectionTitle(ui.guide));
    else card.appendChild(missing(ui.missingTitle));
    (chapter.paragraphs||[]).forEach(function(para){
      const text=field(para,lang);
      card.appendChild(text?prose(text):missing(ui.missingBlock));
    });
    return card;
  }

  function notesCard(){
    const ui=UI[lang];
    const details=document.createElement('details');
    details.className='card footnotes';
    details.id='footnotes';
    const summary=document.createElement('summary');
    const notes=doc.footnotes||[];
    const nums=notes.map(function(n){return n.n;});
    const range=nums.length?nums[0]+'–'+nums[nums.length-1]:'';
    summary.textContent=range?ui.notes+' '+range:ui.notes;
    details.appendChild(summary);
    const list=document.createElement('ol');
    notes.forEach(function(note){
      const li=document.createElement('li');
      li.id='fn-'+note.n;
      li.value=note.n;
      const text=field(note,lang);
      li.innerHTML=text?withNotes(text):esc(ui.missingBlock);
      list.appendChild(li);
    });
    details.appendChild(list);
    return details;
  }

  function paint(){
    paintChrome();
    if(!doc) return;
    noticeEl.hidden=true;
    noticeEl.textContent='';
    stackEl.replaceChildren();
    const guide=guideCard();
    if(guide) stackEl.appendChild(guide);
    (doc.chapters||[]).forEach(function(chapter,index){
      stackEl.appendChild(chapterCard(chapter,index));
    });
    stackEl.appendChild(notesCard());
  }

  function fail(){
    const ui=UI[lang];
    noticeEl.hidden=false;
    noticeEl.textContent=ui.error;
    stackEl.replaceChildren();
    metaEl.textContent=ui.error;
  }

  function apply(next,historyMode){
    lang=next;
    remember(lang);
    if(historyMode!=='none'&&langFromUrl()!==lang) writeUrl(lang,historyMode||'replace');
    if(doc) paint();
    else paintChrome();
  }

  btnZh.addEventListener('click',function(){if(lang!=='zh') apply('zh','push');});
  btnEn.addEventListener('click',function(){if(lang!=='en') apply('en','push');});
  window.addEventListener('popstate',function(){apply(resolveLang(),'none');});
  stackEl.addEventListener('click',function(e){
    const a=e.target.closest('a[href^="#fn-"]');
    if(!a) return;
    const details=document.getElementById('footnotes');
    if(details) details.open=true;
  });

  apply(resolveLang(),'replace');
  fetch(new URL('data/speeches/in-our-time.json',document.baseURI))
    .then(function(res){if(!res.ok) throw new Error(String(res.status));return res.json();})
    .then(function(data){doc=data;paint();})
    .catch(fail);
})();
