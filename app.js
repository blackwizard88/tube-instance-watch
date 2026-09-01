let rows=[],events=[],kind="all";
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state=x=>x.health&&x.playback?"ready":x.health?"health":"down";
const fmtPct=v=>v==null?"—":`${v}%`;
const ageDays=iso=>iso?(Date.now()-new Date(iso).getTime())/86400000:99999;

function render(){
  const status=$("#statusFilter").value,sort=$("#sort").value;
  let d=rows.filter(x=>(kind==="all"||x.service===kind)&&(status==="all"||state(x)===status));
  d.sort((a,b)=>{
    if(sort==="latency") return (a.latency_ms??999999)-(b.latency_ms??999999);
    if(sort==="uptime") return (b.uptime_7d??-1)-(a.uptime_7d??-1);
    if(sort==="newest") return new Date(b.first_seen||0)-new Date(a.first_seen||0);
    if(sort==="name") return a.name.localeCompare(b.name);
    return (b.score??0)-(a.score??0)||(a.latency_ms??999999)-(b.latency_ms??999999);
  });

  const ready=d.filter(x=>state(x)==="ready").length;
  $("#summary").innerHTML=`<span class="pill">${d.length} shown</span><span class="pill">${ready} playback ready</span><span class="pill">${d.filter(x=>state(x)==="health").length} API only</span><span class="pill">${d.filter(x=>state(x)==="down").length} down</span>`;

  $("#grid").innerHTML=d.map((x,i)=>{
    const s=state(x), label=s==="ready"?"● READY":s==="health"?"● API ONLY":"● DOWN";
    const cls=s==="ready"?"ready":s==="health"?"api-only":"dead";
    const isNew=ageDays(x.first_seen)<=7;
    return `<article class="card" data-api="${esc(x.api_url)}">
      <div class="top"><div><div class="service">${esc(x.service)}</div><div class="name">${esc(x.name)}</div></div><div class="state ${cls}">${label}</div></div>
      <div class="badges">${isNew?'<span class="badge">NEW</span>':''}${x.cdn===true?'<span class="badge">CDN</span>':''}<span class="badge">score ${esc(x.score??0)}/100</span></div>
      <div class="meta">
        <div>Latency<strong>${x.latency_ms==null?"—":esc(x.latency_ms)+" ms"}</strong></div>
        <div>Playback<strong>${x.playback?"OK":"FAIL"}</strong></div>
        <div>24h uptime<strong>${fmtPct(x.uptime_24h)}</strong></div>
        <div>7d uptime<strong>${fmtPct(x.uptime_7d)}</strong></div>
        <div>Location<strong>${esc(x.location||"Unknown")}</strong></div>
        <div>First seen<strong>${x.first_seen?new Date(x.first_seen).toLocaleDateString():"—"}</strong></div>
      </div>
      <div class="actions"><button onclick="copyUrl('${encodeURIComponent(x.api_url)}')">Copy API URL</button><button onclick="window.open('${esc(x.url)}','_blank','noopener')">Open</button></div>
      <div class="browser">Browser test: not run</div>
    </article>`;
  }).join("")||"<p>No instances match these filters.</p>";
}

function renderEvents(){
  $("#events").innerHTML=events.slice(0,30).map(e=>`<div class="event"><b class="${esc(e.type)}">${esc(e.type.toUpperCase())}: ${esc(e.name)}</b><span>${esc(e.service)}</span><time>${new Date(e.at).toLocaleString()}</time></div>`).join("")||"<p>No changes recorded yet.</p>";
}
window.copyUrl=async encoded=>navigator.clipboard.writeText(decodeURIComponent(encoded));

async function browserTests(){
  const cards=[...document.querySelectorAll(".card")];
  await Promise.all(cards.map(async c=>{
    const out=c.querySelector(".browser"),url=c.dataset.api,t=performance.now();
    try{await fetch(url,{mode:"no-cors",cache:"no-store"});out.textContent=`Browser test: reachable in ~${Math.round(performance.now()-t)} ms`}
    catch(e){out.textContent="Browser test: failed or blocked by browser/CORS/network policy"}
  }));
}

fetch("data/instances.json",{cache:"no-store"}).then(r=>r.json()).then(data=>{
  rows=data.instances||[];events=data.recent_events||[];
  $("#updated").textContent=data.generated_at?new Date(data.generated_at).toLocaleString():"unknown";
  render();renderEvents();
}).catch(()=>$("#grid").innerHTML="<p>Could not load status data.</p>");

document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");kind=b.dataset.kind;render();
});
$("#statusFilter").onchange=render;$("#sort").onchange=render;$("#browserTest").onclick=browserTests;
