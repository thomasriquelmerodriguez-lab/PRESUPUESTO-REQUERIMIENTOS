import{api,reportUrl}from'../api.js';
import{state,hasPermission}from'../state.js';
import{$,money,escapeHtml,showLoading,announce}from'../ui.js';

let catalog=null;
let dashboard=null;

const percent=value=>`${new Intl.NumberFormat('es-CL',{maximumFractionDigits:1}).format(Number(value)||0)}%`;
const statusLabel=status=>({green:'Bajo 50%',yellow:'50% a 75%',orange:'75% a 90%',red:'90% o más'}[status]||status);

function svgEscape(value){return escapeHtml(value)}

function query(){
  const params=new URLSearchParams();
  const matrix=$('#dashboardMatrix')?.value||'';
  const account=$('#dashboardAccount')?.value||'';
  if(matrix)params.set('matrix',matrix);
  if(account)params.set('account',account);
  return params;
}

function renderMatrixOptions(){
  const select=$('#dashboardMatrix');
  if(!select||!catalog)return;
  const current=select.value;
  const matrices=catalog.accounts.filter(item=>item.level===0).sort((a,b)=>a.code.localeCompare(b.code));
  select.innerHTML='<option value="">Todas las cuentas de primer orden</option>'+matrices.map(item=>`<option value="${escapeHtml(item.code)}">${escapeHtml(item.code)} · ${escapeHtml(item.name)}</option>`).join('');
  if(matrices.some(item=>item.code===current))select.value=current;
}

function renderAccountOptions(){
  const select=$('#dashboardAccount');
  if(!select||!catalog)return;
  const matrix=$('#dashboardMatrix').value;
  const current=select.value;
  const rows=catalog.accounts.filter(item=>(!matrix||item.matrix_code===matrix)&&(!matrix||item.code!==matrix));
  select.innerHTML='<option value="">Toda la cuenta seleccionada</option>'+rows.map(item=>`<option value="${escapeHtml(item.code)}">${escapeHtml(item.code)} · ${escapeHtml(item.name)}</option>`).join('');
  if(rows.some(item=>item.code===current))select.value=current;
  else select.value='';
  select.disabled=!matrix;
}

function renderMetrics(){
  const d=dashboard;
  const items=[
    ['Presupuesto vigente',money(d.total_budget)],
    ['Obligado CAS',money(d.total_obligated_cas)],
    ['Requerimientos',money(d.total_requirements)],
    ['Saldo disponible',money(d.total_available),d.total_available<0?'negative':'positive'],
    ['% comprometido',percent(d.committed_percent),d.committed_percent>=90?'negative':''],
  ];
  $('#dashboardMetrics').innerHTML=items.map(([label,value,cls=''])=>`<div class="metric-card"><span>${escapeHtml(label)}</span><strong class="${cls}">${escapeHtml(value)}</strong></div>`).join('');
  const scope=d.scope_code?`${d.scope_code} · ${d.scope_name}`:'Todas las cuentas de primer orden';
  $('#dashboardScope').textContent=`${scope} · ${d.requirements_count} requerimientos · ${d.accounts_used} cuentas utilizadas`;
}

function renderAttention(){
  const a=dashboard.attention;
  const cards=[
    {kind:a.negative_balance_accounts?'bad':'ok',value:a.negative_balance_accounts,label:'cuentas con saldo negativo'},
    {kind:a.over_90_percent_accounts?'bad':'ok',value:a.over_90_percent_accounts,label:'cuentas sobre 90% comprometido'},
    {kind:a.low_balance_accounts?'warn':'ok',value:a.low_balance_accounts,label:'cuentas con saldo ≤ $5.000.000'},
    {kind:a.unmapped_requirements_count?'warn':'ok',value:a.unmapped_requirements_count,label:'requerimientos en cuentas fuera del presupuesto vigente',detail:a.unmapped_requirements_amount?money(a.unmapped_requirements_amount):''},
  ];
  $('#dashboardAttention').innerHTML=cards.map(item=>`<div class="decision-alert ${item.kind}"><strong>${escapeHtml(item.value)}</strong><span>${escapeHtml(item.label)}</span>${item.detail?`<small>${escapeHtml(item.detail)}</small>`:''}</div>`).join('');
}

function accountChart(rows){
  if(!rows.length)return'<div class="progress-message">No hay cuentas para los filtros seleccionados.</div>';
  const maxBudget=Math.max(...rows.map(row=>Number(row.budget)||0),1);
  const width=980,left=250,right=90,plot=width-left-right,rowH=56,height=Math.max(130,rows.length*rowH+48);
  const elements=[];
  rows.forEach((row,index)=>{
    const y=22+index*rowH;
    const budget=Math.max(Number(row.budget)||0,1);
    const barW=Math.max(2,(Number(row.budget)||0)/maxBudget*plot);
    const reqRaw=Math.max(0,Number(row.requirements)||0);
    const casRaw=Math.max(0,Number(row.obligated_cas)||0);
    const reqW=Math.min(barW,reqRaw/budget*barW);
    const casW=Math.min(Math.max(0,barW-reqW),casRaw/budget*barW);
    const availW=Math.max(0,barW-reqW-casW);
    elements.push(`<text x="0" y="${y+15}" class="dashboard-svg-code">${svgEscape(row.code)}</text>`);
    elements.push(`<text x="0" y="${y+32}" class="dashboard-svg-name">${svgEscape(String(row.name).slice(0,34))}</text>`);
    elements.push(`<rect x="${left}" y="${y}" width="${barW}" height="24" rx="4" class="dashboard-svg-budget"></rect>`);
    if(reqW>0)elements.push(`<rect x="${left}" y="${y}" width="${reqW}" height="24" rx="3" class="dashboard-svg-requirements"></rect>`);
    if(casW>0)elements.push(`<rect x="${left+reqW}" y="${y}" width="${casW}" height="24" class="dashboard-svg-cas"></rect>`);
    if(availW>0)elements.push(`<rect x="${left+reqW+casW}" y="${y}" width="${availW}" height="24" rx="3" class="dashboard-svg-available"></rect>`);
    elements.push(`<text x="${left+barW+8}" y="${y+16}" class="dashboard-svg-percent dashboard-svg-${svgEscape(row.status)}">${svgEscape(percent(row.committed_percent))}</text>`);
    elements.push(`<text x="${left}" y="${y+42}" class="dashboard-svg-value">Saldo ${svgEscape(money(row.available))}</text>`);
  });
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Estado presupuestario por cuenta">${elements.join('')}</svg>`;
}

function monthlyChart(months){
  const width=980,height=280,left=60,right=20,top=18,bottom=52,plotW=width-left-right,plotH=height-top-bottom;
  const max=Math.max(...months.map(item=>Number(item.requirements_amount)||0),1);
  const slot=plotW/12,barW=Math.max(14,slot*.58);
  const el=[`<line x1="${left}" y1="${top+plotH}" x2="${width-right}" y2="${top+plotH}" class="dashboard-svg-axis"></line>`];
  months.forEach((item,index)=>{
    const amount=Number(item.requirements_amount)||0;
    const h=amount/max*plotH;
    const x=left+index*slot+(slot-barW)/2;
    const y=top+plotH-h;
    el.push(`<rect x="${x}" y="${y}" width="${barW}" height="${h}" rx="4" class="dashboard-svg-month"></rect>`);
    el.push(`<text x="${x+barW/2}" y="${top+plotH+18}" text-anchor="middle" class="dashboard-svg-month-label">${svgEscape(item.label)}</text>`);
    if(amount>0)el.push(`<text x="${x+barW/2}" y="${Math.max(12,y-5)}" text-anchor="middle" class="dashboard-svg-month-count">${item.requirements_count}</text>`);
  });
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Evolución mensual de requerimientos">${el.join('')}</svg>`;
}

function renderBreakdown(){
  const rows=dashboard.breakdown;
  $('#dashboardAccountChart').innerHTML=accountChart(rows);
  $('#dashboardBreakdownTable').innerHTML=rows.length?`<div class="dashboard-table-wrap"><table class="dashboard-table"><thead><tr><th>Cuenta</th><th>Presupuesto</th><th>Obligado CAS</th><th>Requerimientos</th><th>Saldo</th><th>% comprometido</th></tr></thead><tbody>${rows.map(row=>`<tr><td><strong>${escapeHtml(row.code)}</strong><small>${escapeHtml(row.name)}</small></td><td>${money(row.budget)}</td><td>${money(row.obligated_cas)}</td><td>${money(row.requirements)}</td><td class="${row.available<0?'negative':'positive'}">${money(row.available)}</td><td><span class="dashboard-status ${escapeHtml(row.status)}">${percent(row.committed_percent)}</span></td></tr>`).join('')}</tbody></table></div>`:'<div class="progress-message">No hay cuentas para los filtros seleccionados.</div>';
}

function renderMonthly(){
  $('#dashboardMonthlyChart').innerHTML=monthlyChart(dashboard.monthly);
  const peak=dashboard.monthly.reduce((best,item)=>item.requirements_amount>best.requirements_amount?item:best,dashboard.monthly[0]||{label:'—',requirements_amount:0,requirements_count:0});
  $('#dashboardMonthlySummary').textContent=`Mes de mayor requerimiento: ${peak.label} · ${money(peak.requirements_amount)} · ${peak.requirements_count} registros`;
}

function criticalCard(row){
  return `<article class="decision-account-card"><div><span class="dashboard-status ${escapeHtml(row.status)}">${statusLabel(row.status)}</span><h3>${escapeHtml(row.code)}</h3><p>${escapeHtml(row.name)}</p></div><div class="decision-account-values"><span>Saldo<strong class="${row.available<0?'negative':'positive'}">${money(row.available)}</strong></span><span>Comprometido<strong>${percent(row.committed_percent)}</strong></span><span>Requerimientos<strong>${money(row.requirements)}</strong></span></div></article>`;
}

function renderCritical(){
  const rows=dashboard.critical_accounts;
  $('#dashboardCritical').innerHTML=rows.length?rows.map(criticalCard).join(''):'<div class="callout">No se detectaron cuentas críticas con los filtros seleccionados.</div>';
}

function renderTopRequirements(){
  const rows=dashboard.top_requirement_accounts;
  const max=Math.max(...rows.map(row=>Number(row.requirements)||0),1);
  $('#dashboardTopRequirements').innerHTML=rows.length?rows.map((row,index)=>`<article class="ranking-row"><span class="ranking-number">${index+1}</span><div><strong>${escapeHtml(row.code)}</strong><small>${escapeHtml(row.name)}</small><div class="ranking-track"><svg viewBox="0 0 500 12" preserveAspectRatio="none" aria-hidden="true"><rect x="0" y="0" width="${Math.max(2,(Number(row.requirements)||0)/max*500)}" height="12" rx="5" class="dashboard-svg-ranking"></rect></svg></div></div><strong>${money(row.requirements)}</strong></article>`).join(''):'<div class="progress-message">No hay requerimientos registrados.</div>';
}

function render(){
  if(!dashboard)return;
  renderMetrics();
  renderAttention();
  renderBreakdown();
  renderMonthly();
  renderCritical();
  renderTopRequirements();
  $('#dashboardReport').hidden=!hasPermission('reports.generate');
}

export async function loadDashboard(){
  const year=Number($('#dashboardYear').value||state.years[0]||0);
  if(!year){
    $('#dashboardMetrics').innerHTML='';
    $('#dashboardAccountChart').innerHTML='<div class="progress-message">No existe un presupuesto cargado para esta área.</div>';
    return;
  }
  showLoading($('#dashboardAccountChart'),'Cargando indicadores…');
  showLoading($('#dashboardMonthlyChart'),'Cargando evolución…');
  try{
    catalog=await api(`/budgets/${state.area}/${year}/catalog`);
    renderMatrixOptions();
    renderAccountOptions();
    const params=query();
    dashboard=await api(`/budgets/${state.area}/${year}/decision-dashboard${params.toString()?`?${params}`:''}`);
    render();
  }catch(error){
    dashboard=null;
    $('#dashboardMetrics').innerHTML='';
    $('#dashboardAttention').innerHTML='';
    $('#dashboardAccountChart').innerHTML=`<div class="callout error">${escapeHtml(error.message)}</div>`;
    $('#dashboardMonthlyChart').innerHTML='';
    $('#dashboardCritical').innerHTML='';
    $('#dashboardTopRequirements').innerHTML='';
  }
}

async function matrixChanged(){
  renderAccountOptions();
  await loadDashboard();
}

function report(){
  if(!hasPermission('reports.generate'))return;
  const year=Number($('#dashboardYear').value||0);
  if(!year){announce('Seleccione un año con presupuesto.');return}
  const params=query();
  params.set('area',state.area);
  params.set('year',String(year));
  reportUrl(`/reports/dashboard?${params}`);
}

export function initDashboardPage(){
  $('#dashboardYear').addEventListener('change',async()=>{catalog=null;$('#dashboardMatrix').value='';$('#dashboardAccount').value='';await loadDashboard()});
  $('#dashboardMatrix').addEventListener('change',matrixChanged);
  $('#dashboardAccount').addEventListener('change',loadDashboard);
  $('#dashboardReport').addEventListener('click',report);
}
