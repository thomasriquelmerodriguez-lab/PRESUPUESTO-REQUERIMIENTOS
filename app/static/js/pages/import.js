import{api,downloadUrl}from'../api.js';
import{state,hasPermission}from'../state.js';
import{$,money,escapeHtml,announce,showLoading,confirmAction}from'../ui.js';

function previewHtml(data){
  const stats=[
    ['Filas leídas',data.rows_read],
    ['Cuentas válidas',data.valid_rows],
    ['Incluidas',data.included_rows],
    ['Descartadas',data.excluded_rows],
    ['Presupuesto',money(data.total_budget)],
    ['Pre obligado planilla (referencia)',money(data.total_new_requirements)],
    ['Obligado CAS',money(data.total_obligated_cas)],
  ];
  const rows=data.sample.slice(0,30).map(row=>`<article class="data-card"><div><h3>${escapeHtml(row.code||'Sin cuenta')}</h3><div class="meta">${escapeHtml(row.name||'Sin denominación')}</div></div><div class="data-fields"><div class="data-field"><span>Presupuesto</span><strong>${money(row.budget)}</strong></div><div class="data-field"><span>Pre obligado planilla (referencia)</span><strong>${money(row.base_new_requirements)}</strong></div><div class="data-field"><span>Obligado CAS</span><strong>${money(row.obligated_cas)}</strong></div></div><span class="status ${row.included?'ok':'warn'}">${escapeHtml(row.reason)}</span></article>`).join('');
  return `<div class="preview-grid">${stats.map(([label,value])=>`<div class="preview-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div><div class="button-row"><button id="cancelImport" class="button ghost" type="button">Cancelar</button><button id="applyImport" class="button primary" type="button">Aplicar presupuesto</button></div><div class="data-list">${rows}</div>`;
}

function renderPeriods(periods){
  const container=$('#budgetYearsList');
  if(!container)return;
  if(!periods.length){
    container.innerHTML='<div class="progress-message">No hay años presupuestarios creados para esta área. Agregue el primero para poder cargar su presupuesto.</div>';
    return;
  }
  container.innerHTML=periods.map(period=>`<article class="data-card"><div><h3>Año ${period.year}</h3><div class="meta">${period.has_budget?`Presupuesto activo · ${escapeHtml(period.source_name||'Planilla cargada')}`:'Año creado · pendiente de cargar presupuesto'}</div></div><div class="data-fields"><div class="data-field"><span>Estado</span><strong>${period.has_budget?'Con presupuesto':'Sin presupuesto'}</strong></div><div class="data-field"><span>Total vigente</span><strong>${period.has_budget?money(period.total_budget):'—'}</strong></div><div class="data-field"><span>Versión activa</span><strong>${period.active_version??'—'}</strong></div></div>${hasPermission('budgets.import')?`<div class="data-actions"><button class="button ${period.has_budget?'secondary':'primary'}" data-use-year="${period.year}" type="button">${period.has_budget?'Actualizar este año':'Cargar presupuesto'}</button></div>`:''}</article>`).join('');
}

async function loadPeriods(){
  const container=$('#budgetYearsList');
  if(container)showLoading(container);
  try{
    const periods=await api(`/budgets/${state.area}/years`);
    state.budgetPeriods=periods;
    state.registeredYears=periods.map(item=>item.year).sort((a,b)=>b-a);
    state.years=periods.filter(item=>item.has_budget).map(item=>item.year).sort((a,b)=>b-a);
    renderPeriods(periods);
    const select=$('#importYear');
    if(select){
      const current=Number(select.value);
      select.innerHTML=state.registeredYears.length?state.registeredYears.map(year=>`<option value="${year}">${year}</option>`).join(''):'<option value="">Primero agregue un año</option>';
      if(state.registeredYears.includes(current))select.value=String(current);
    }
    return periods;
  }catch(error){
    if(container)container.innerHTML=`<div class="callout error">${escapeHtml(error.message)}</div>`;
    return [];
  }
}

async function createYear(event){
  event.preventDefault();
  if(!hasPermission('budgets.import'))return;
  const year=Number($('#newBudgetYear').value);
  if(!Number.isInteger(year)||year<2020||year>2100){announce('Ingrese un año válido entre 2020 y 2100.');return}
  try{
    await api(`/budgets/${state.area}/years`,{method:'POST',body:{year}});
    $('#newBudgetYear').value='';
    announce(`Año presupuestario ${year} creado para ${state.area}.`);
    document.dispatchEvent(new CustomEvent('budget-years-changed'));
    await loadPeriods();
    $('#importYear').value=String(year);
  }catch(error){announce(error.message)}
}

export async function loadVersions(){
  await loadPeriods();
  const container=$('#versionsList');
  if(!hasPermission('budgets.view')){container.innerHTML='';return}
  showLoading(container);
  try{
    const versions=await api(`/budgets/${state.area}/versions`);
    container.innerHTML=versions.length?versions.map(version=>`<article class="data-card"><div><h3>Presupuesto ${version.year} · versión ${version.version_number}</h3><div class="meta">${escapeHtml(version.source_name)} · ${new Date(version.created_at).toLocaleString('es-CL')}</div></div><div class="data-fields"><div class="data-field"><span>Total</span><strong>${money(version.total_budget)}</strong></div><div class="data-field"><span>Estado</span><strong>${version.active?'Activo':'Histórico'}</strong></div><div class="data-field"><span>Origen</span><strong>${version.is_seed?'Base incorporada':'Carga de usuario'}</strong></div></div>${hasPermission('budgets.import')&&version.is_seed&&!version.active?'<div class="data-actions"><button class="button secondary" data-restore-year="'+version.year+'" type="button">Restaurar base</button></div>':''}</article>`).join(''):'<div class="progress-message">No hay presupuestos cargados para esta área.</div>';
  }catch(error){container.innerHTML=`<div class="callout error">${escapeHtml(error.message)}</div>`}
}

async function preview(event){
  event.preventDefault();
  if(!hasPermission('budgets.import'))return;
  const file=$('#budgetFile').files[0];
  const year=Number($('#importYear').value);
  if(!year){announce('Primero cree y seleccione un año presupuestario.');return}
  if(!file){announce('Seleccione una planilla Excel o CSV.');return}
  $('#importProgress').hidden=false;
  $('#importPreview').hidden=true;
  const form=new FormData();
  form.append('area',state.area);
  form.append('year',String(year));
  form.append('file',file);
  try{
    const data=await api('/budgets/import/preview',{method:'POST',body:form});
    state.importToken=data.token;
    $('#importPreview').innerHTML=previewHtml(data);
    $('#importPreview').hidden=false;
    $('#cancelImport').addEventListener('click',()=>{$('#importPreview').hidden=true;state.importToken=null});
    $('#applyImport').addEventListener('click',apply);
  }catch(error){announce(error.message)}finally{$('#importProgress').hidden=true}
}

async function apply(){
  if(!hasPermission('budgets.import')||!state.importToken)return;
  const year=Number($('#importYear').value);
  if(!await confirmAction(`¿Aplicar esta planilla como presupuesto vigente de ${state.area} para ${year}?`))return;
  try{
    await api('/budgets/import/apply',{method:'POST',body:{token:state.importToken,area:state.area,year}});
    announce(`Presupuesto ${year} aplicado correctamente.`);
    state.importToken=null;
    $('#importPreview').hidden=true;
    $('#budgetFile').value='';
    document.dispatchEvent(new CustomEvent('budget-years-changed'));
    await loadVersions();
  }catch(error){announce(error.message)}
}

function template(){
  if(!hasPermission('budgets.import'))return;
  const text='CUENTA;DENOMINACIÓN;PRESUPUESTO VIGENTE;PRE OBLIGADO ZE COMPRAS;OBLIGADO CAS\n215-22-01-000-000-000;ALIMENTOS Y BEBIDAS;54000000;19460054;1691756\n';
  const blob=new Blob(['\ufeff'+text],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='plantilla_presupuesto.csv';a.click();URL.revokeObjectURL(url);
}

async function importBackup(event){
  event.preventDefault();
  if(!hasPermission('backups.import'))return;
  const file=$('#backupFile').files[0];
  if(!file)return;
  if(!await confirmAction('¿Importar este respaldo?'))return;
  const form=new FormData();
  form.append('area',state.area);
  form.append('replace_existing',$('#backupReplace').checked?'true':'false');
  form.append('file',file);
  try{
    const result=await api('/backup/import',{method:'POST',body:form});
    announce(result.message);
    $('#backupFile').value='';
    document.dispatchEvent(new CustomEvent('budget-years-changed'));
    await loadVersions();
  }catch(error){announce(error.message)}
}

async function restore(event){
  if(!hasPermission('budgets.import'))return;
  const button=event.target.closest('[data-restore-year]');
  if(!button)return;
  const year=Number(button.dataset.restoreYear);
  if(!await confirmAction(`¿Restaurar la base incorporada del año ${year}?`))return;
  try{
    await api(`/budgets/${state.area}/${year}/restore-seed`,{method:'POST'});
    announce('Presupuesto base restaurado.');
    document.dispatchEvent(new CustomEvent('budget-years-changed'));
    await loadVersions();
  }catch(error){announce(error.message)}
}

function selectPeriod(event){
  const button=event.target.closest('[data-use-year]');
  if(!button)return;
  $('#importYear').value=button.dataset.useYear;
  $('#budgetFile').focus();
  document.querySelector('#budgetImportPanel').scrollIntoView({behavior:'smooth',block:'start'});
}

export function initImportPage(){
  $('#budgetYearForm').addEventListener('submit',createYear);
  $('#budgetYearsList').addEventListener('click',selectPeriod);
  $('#budgetImportForm').addEventListener('submit',preview);
  $('#downloadTemplate').addEventListener('click',template);
  $('#backupExport').addEventListener('click',()=>{if(hasPermission('backups.export'))downloadUrl(`/backup?area=${encodeURIComponent(state.area)}`)});
  $('#backupImportForm').addEventListener('submit',importBackup);
  $('#versionsList').addEventListener('click',restore);
}
