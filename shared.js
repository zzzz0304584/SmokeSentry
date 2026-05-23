// ── SmokeSentry Shared UI ──
const NAV = [
  { section:'// 監控', items:[
    { icon:'📊', label:'總覽儀表板', href:'dashboard.html' },
    { icon:'📹', label:'即時攝影機', href:'cameras.html', badge:'4' },
    { icon:'🚨', label:'警示管理',   href:'alerts.html',  badge:'3', danger:true },
  ]},
  { section:'// 分析', items:[
    { icon:'📈', label:'統計報表', href:'stats.html' },
    { icon:'🗺️', label:'熱點分析', href:'heatmap.html' },
    { icon:'📋', label:'違規紀錄', href:'records.html' },
  ]},
  { section:'// 系統', items:[
    { icon:'⚙️', label:'系統設定',  href:'settings.html' },
    { icon:'🔔', label:'通知設定',  href:'notify.html' },
  ]},
];

function injectShell(pageTitle) {
  const cur = location.pathname.split('/').pop() || 'dashboard.html';
  let sb = `<div class="sidebar">
    <div class="sidebar-logo">Smoke<span>Sentry</span></div>`;
  NAV.forEach(g => {
    sb += `<div class="sidebar-section">${g.section}</div>`;
    g.items.forEach(it => {
      const active = cur === it.href ? ' active' : '';
      const badge  = it.badge
        ? `<span class="nav-badge"${it.danger?' style="background:var(--danger)"':''}>${it.badge}</span>`
        : '';
      sb += `<a class="nav-item${active}" href="${it.href}">${it.icon} ${it.label}${badge}</a>`;
    });
  });
  sb += `<div class="sidebar-status">
    <div class="sys-online">SYSTEM ONLINE</div>
    <div style="font-family:var(--font-mono);font-size:.62rem;color:var(--text-muted);margin-top:.3rem">4/4 攝影機運作中</div>
  </div></div>`;

  const tb = `<div class="topbar">
    <div class="topbar-title">${pageTitle}</div>
    <div class="topbar-right">
      <div class="topbar-time" id="clockDisplay">--:--:--</div>
      <a href="alerts.html" class="alert-bell">🔔<div class="bell-badge">3</div></a>
      <a href="index.html" class="back-btn">← 返回主頁</a>
    </div>
  </div>`;

  document.getElementById('sidebar-slot').innerHTML = sb;
  document.getElementById('topbar-slot').innerHTML  = tb;

  function tick(){
    const n=new Date();
    const el=document.getElementById('clockDisplay');
    if(el) el.textContent=`${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}`;
  }
  tick(); setInterval(tick,1000);
}

// Toast
function showToast(msg, type='success', duration=3500) {
  let tc = document.getElementById('toast-container');
  if (!tc) { tc=document.createElement('div'); tc.id='toast-container'; tc.className='toast-container'; document.body.appendChild(tc); }
  const t = document.createElement('div');
  t.className=`toast ${type}`;
  const icons = {success:'✅', error:'❌', warn:'⚠️', info:'ℹ️'};
  t.innerHTML=`<span>${icons[type]||'ℹ️'}</span><span>${msg}</span>`;
  tc.appendChild(t);
  setTimeout(()=>{ t.style.opacity='0'; t.style.transition='opacity .4s'; setTimeout(()=>t.remove(),400); }, duration);
}
