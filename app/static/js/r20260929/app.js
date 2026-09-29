import{api,setCsrf}from'./api.js';
import{state,areaNames,hasPermission}from'./state.js';
import{$,$$,announce,setError,escapeHtml}from'./ui.js';
import{initRequestPage,loadRequestPage,resetRequestForm}from'./pages/request.js';
import{initRecordsPage,loadRecords}from'./pages/records.js';
import{initBudgetPage,loadBudget}from'./pages/budget.js';
import{initImportPage,loadVersions}from'./pages/import.js';
import{initAuditPage,loadAudit}from'./pages/audit.js';
import{initUsersPage,loadUsers}from'./pages/users.js';

const titles={request:'Nuevo requerimiento',records:'Registros guardados',budget:'Presupuesto vigente',import:'Actualizar presupuesto',audit:'Auditoría',users:'Usuarios y privilegios'};
const pageAccess={
  request:()=>hasPermission('requirements.create')&&hasPermission('budgets.view')&&Boolean(state.area),
  records:()=>hasPermission('requirements.view')&&Boolean(state.area),
  budget:()=>hasPermission('budgets.view')&&Boolean(state.area),
  import:()=>Boolean(state.area)&&['budgets.import','backups.export','backups.import'].some(hasPermission),
  audit:()=>hasPermission('audit.view'),
  users:()=>hasPermission('users.manage'),
};
let eventRefreshTimer;

function allowedPages(){return Object.keys(titles).filter(page=>pageAccess[page]())}

async function loadLoginOptions(){
  const container=$('#loginUsers');
  if(!container)return;
  const selected=$('input[name="loginUserId"]:checked')?.value;
  container.innerHTML='<div class="progress-message">Cargando usuarios…</div>';
  try{
    const users=await api('/auth/login-options');
    if(!users.length){container.innerHTML='<div class="callout error">No hay usuarios activos disponibles.</div>';return}
    container.innerHTML=users.map((user,index)=>`<label class="login-user-option"><input type="radio" name="loginUserId" value="${escapeHtml(user.id)}" ${(selected===user.id||(!selected&&index===0))?'checked':''}><span>${escapeHtml(user.display_name)}</span></label>`).join('');
  }catch(error){container.innerHTML=`<div class="callout error">${escapeHtml(error.message)}</div>`}
}

function showAuthenticated(authenticated){
  $('#loginView').hidden=authenticated;
  $('#appView').hidden=!authenticated;
  if(!authenticated){
    loadLoginOptions().finally(()=>setTimeout(()=>$('#loginPassword').focus(),0));
  }
}

function configureFeatureVisibility(){
  const visibility={
    request:pageAccess.request(),records:pageAccess.records(),budget:pageAccess.budget(),import:pageAccess.import(),audit:pageAccess.audit(),users:pageAccess.users(),
  };
  $$('.nav-button').forEach(button=>{button.hidden=!visibility[button.dataset.page]});
  $('#recordsCsv').hidden=!hasPermission('requirements.export');
  $('#recordsReport').hidden=!hasPermission('reports.generate');
  $('#budgetCsv').hidden=!hasPermission('budgets.export');
  $('#yearsPanel').hidden=!hasPermission('budgets.import');
  $('#budgetImportPanel').hidden=!hasPermission('budgets.import');
  $('#backupImportPanel').hidden=!hasPermission('backups.import');
  $('#backupExport').hidden=!hasPermission('backups.export');
  $('#downloadTemplate').hidden=!hasPermission('budgets.import');
  $('#versionsPanel').hidden=!hasPermission('budgets.view');
}

function configureUser(){
  const user=state.user;
  $('#currentUser').textContent=user.display_name;
  $('#areaSelect').innerHTML=user.areas.map(area=>`<option value="${escapeHtml(area)}">${escapeHtml(areaNames[area]||area)}</option>`).join('');
  if(user.areas.length){
    if(!user.areas.includes(state.area))state.area=user.areas[0];
    $('#areaSelect').value=state.area;
    $('#areaSelect').disabled=user.areas.length===1;
    $('.area-control').hidden=false;
    $('#activeAreaName').textContent=areaNames[state.area]||state.area;
  }else{
    state.area='';
    $('#areaSelect').disabled=true;
    $('.area-control').hidden=true;
    $('#activeAreaName').textContent='Administración';
  }
  configureFeatureVisibility();
}

async function refreshYears(){
  if(!state.area){state.years=[];state.registeredYears=[];state.budgetPeriods=[];return}
  try{
    const periods=await api(`/budgets/${state.area}/years`);
    state.budgetPeriods=periods;
    state.registeredYears=periods.map(item=>item.year).sort((a,b)=>b-a);
    state.years=periods.filter(item=>item.has_budget).map(item=>item.year).sort((a,b)=>b-a);
  }catch{
    state.budgetPeriods=[];
    state.registeredYears=[];
    state.years=[];
  }
  const selectorConfig=[
    ['#requestYear',state.years,false],
    ['#recordsYear',state.registeredYears,true],
    ['#budgetYear',state.years,false],
    ['#importYear',state.registeredYears,false],
  ];
  for(const [selector,years,allOption] of selectorConfig){
    const node=$(selector);
    if(!node)continue;
    const current=node.value;
    const prefix=allOption?'<option value="">Todos</option>':'';
    const empty=!years.length&&!allOption?'<option value="">Sin años disponibles</option>':'';
    node.innerHTML=prefix+empty+years.map(year=>`<option value="${year}">${year}</option>`).join('');
    if(years.includes(Number(current)))node.value=current;
  }
}

async function loadPage(page=state.page){
  const pages=allowedPages();
  if(!pages.length){announce('El usuario no tiene módulos habilitados.');return}
  if(!pages.includes(page))page=pages[0];
  state.page=page;
  $$('.page').forEach(node=>node.classList.toggle('active',node.id===`page-${page}`));
  $$('.nav-button').forEach(node=>node.classList.toggle('active',node.dataset.page===page));
  $('#pageTitle').textContent=titles[page];
  $('#sidebar').classList.remove('open');
  if(page==='request')await loadRequestPage();
  if(page==='records')await loadRecords();
  if(page==='budget')await loadBudget();
  if(page==='import')await loadVersions();
  if(page==='audit')await loadAudit();
  if(page==='users')await loadUsers();
}

function connectEvents(){
  state.eventSource?.close();
  const source=new EventSource('/api/events',{withCredentials:true});
  state.eventSource=source;
  source.onopen=()=>{$('#connectionStatus').textContent='Sincronización activa'};
  source.onerror=()=>{$('#connectionStatus').textContent='Reconectando…'};
  source.addEventListener('update',event=>{
    try{
      const data=JSON.parse(event.data);
      if(data.area&&data.area!==state.area)return;
      clearTimeout(eventRefreshTimer);
      eventRefreshTimer=setTimeout(()=>loadPage(state.page),450);
    }catch{}
  });
}

async function completeLogin(session){
  state.user=session.user;
  setCsrf(session.csrf_token);
  state.area=session.user.areas.includes(state.area)?state.area:(session.user.areas[0]||'');
  configureUser();
  await refreshYears();
  showAuthenticated(true);
  if(pageAccess.request())resetRequestForm();
  await loadPage(allowedPages()[0]);
  connectEvents();
}

async function recoverSession(){
  try{await completeLogin(await api('/auth/session'))}
  catch{showAuthenticated(false)}
}

async function login(event){
  event.preventDefault();
  setError('#loginError','');
  const userId=$('input[name="loginUserId"]:checked')?.value;
  if(!userId){setError('#loginError','Seleccione un usuario.');return}
  try{
    const session=await api('/auth/login',{method:'POST',body:{user_id:userId,password:$('#loginPassword').value}});
    $('#loginPassword').value='';
    await completeLogin(session);
    announce(`Sesión iniciada: ${session.user.display_name}.`);
  }catch(error){setError('#loginError',error);$('#loginPassword').select()}
}

async function logout(){
  try{await api('/auth/logout',{method:'POST'})}catch{}
  state.eventSource?.close();
  state.user=null;
  state.area='municipal';
  setCsrf('');
  showAuthenticated(false);
  $('#loginPassword').value='';
}

async function changeArea(){
  state.area=$('#areaSelect').value;
  $('#activeAreaName').textContent=areaNames[state.area]||state.area;
  state.catalog=null;
  state.recordPage=1;
  state.editing=null;
  await refreshYears();
  if(pageAccess.request())resetRequestForm();
  await loadPage(state.page);
  announce(`Área activa: ${areaNames[state.area]}.`);
}

function init(){
  $('#loginForm').addEventListener('submit',login);
  $('#logoutButton').addEventListener('click',logout);
  $('#areaSelect').addEventListener('change',changeArea);
  $('#menuButton').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
  $$('.nav-button').forEach(button=>button.addEventListener('click',()=>loadPage(button.dataset.page)));
  document.addEventListener('users-changed',loadLoginOptions);
  document.addEventListener('budget-years-changed',async()=>{await refreshYears();if(state.page==='import')await loadVersions();});
  initRequestPage();
  initRecordsPage();
  initBudgetPage();
  initImportPage();
  initAuditPage();
  initUsersPage();
  recoverSession();
}

init();
