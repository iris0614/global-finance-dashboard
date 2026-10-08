const C={text:'#1c2128',muted:'#5b6572',dim:'#98a1ac',line:'#e6eaef',up:'#1a8f47',down:'#d43f45',accent:'#2b7cd3',gold:'#c9930f',warn:'#d1a017'};
Chart.defaults.font.family='"PingFang SC","Microsoft YaHei",-apple-system,Segoe UI,sans-serif';
Chart.defaults.font.size=11;
Chart.defaults.color=C.muted;
const base=(extra={})=>Object.assign({
  responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'#ffffff',titleColor:C.text,bodyColor:C.text,borderColor:C.line,borderWidth:1,padding:9,displayColors:false}},
  scales:{x:{grid:{display:false},ticks:{color:C.muted}},y:{grid:{color:C.line},ticks:{color:C.muted},border:{display:false}}}
},extra);
const tip=cb=>({backgroundColor:'#ffffff',titleColor:C.text,bodyColor:C.text,borderColor:C.line,borderWidth:1,padding:9,displayColors:false,callbacks:{label:cb}});

const tooltipFormatters={
  c1PercentTrim(c){return c.dataset.label+'：'+c.parsed.y.toFixed(3).replace(/0+$/,'').replace(/\.$/,'')+'%';},
  yoyPlus(c){return '同比 +'+c.parsed.y+'%';},
  qianren(c){return c.parsed.y+' 千人';},
  twoDecimals(c){return c.dataset.label+'：'+c.parsed.y.toFixed(2)+'%';},
  yield10y(c){return '10 年期收益率 '+c.parsed.y+'%';},
  usdPerBarrel(c){return '$'+c.parsed.y+' / 桶';},
  q3YoyPlus(c){return 'Q3 预期同比 +'+c.parsed.y+'%';},
  usdBillions(c){return c.parsed.y+' 十亿美元';},
  datasetPct(c){return c.dataset.label+'：'+c.parsed.y+'%';},
  signedPct(c){return '同比 '+(c.parsed.y>0?'+':'')+c.parsed.y+'%';}
};
const tickFormatters={
  pct(v){return v+'%';},
  pctTwoDecimals(v){return Number(v).toFixed(2)+'%';},
  thousandsK(v){return v+'k';},
  usd(v){return '$'+v;},
  usdB(v){return '$'+v+'B';}
};

const liveCharts=[];

function destroyCharts(){
  while(liveCharts.length){
    const chart=liveCharts.pop();
    try{chart.destroy();}catch(e){}
  }
}

function createChart(canvas, spec){
  const existing=typeof Chart.getChart==='function'?Chart.getChart(canvas):null;
  if(existing) existing.destroy();
  const tickFormatter=spec.id==='c5'?'pctTwoDecimals':spec.tickFormatter;
  const y={grid:{color:C.line},border:{display:false},ticks:{color:C.muted,callback:tickFormatters[tickFormatter]}};
  if(spec.y&&spec.y.beginAtZero) y.beginAtZero=true;
  if(spec.y&&spec.y.min!=null) y.min=spec.y.min;
  if(spec.y&&spec.y.max!=null) y.max=spec.y.max;
  const legend=spec.legend
    ?{display:true,position:'top',labels:{boxWidth:10,boxHeight:10,padding:12,color:C.muted}}
    :{display:false};
  const extra={
    plugins:{
      legend,
      tooltip:tip(tooltipFormatters[spec.tooltipFormatter])
    },
    scales:{
      x:{grid:{display:false},ticks:{color:C.muted}},
      y
    }
  };
  return new Chart(canvas,{
    type:spec.type,
    data:{
      labels:JSON.parse(JSON.stringify(spec.labels)),
      datasets:JSON.parse(JSON.stringify(spec.datasets))
    },
    options:base(extra)
  });
}

function mountChart(canvas, spec){
  const chart=createChart(canvas, spec);
  liveCharts.push(chart);
  return chart;
}

window.DashboardCharts={C, base, createChart, destroyCharts, mountChart, tooltipFormatters, tickFormatters};
