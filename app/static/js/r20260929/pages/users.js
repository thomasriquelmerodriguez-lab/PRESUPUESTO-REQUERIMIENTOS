import{api}from'../api.js';
import{state,areaNames}from'../state.js';
import{$,$$,escapeHtml,setError,announce,showLoading,confirmAction}from'../ui.js';

let users=[];
let permissions=[];
let editingId=null;

function selectedValues(name){return $$(`input[name="${name}"]:checked`).map(node=>node.value)}
function permissionName(code){return permissions.find(item=>item.code===code)?.label||code}

function renderPermissionChoices(selected=[]){
  const groups=new Map();
  for(const permission of permissions){
    if(!groups.has(permission.category))groups.set(permission.category,[]);
    groups.get(permission.category).push(permission);
  }
  const editing=users.find(item=>item.id===editingId);
  $('#permissionsList').innerHTML=[...groups.entries()].map(([category,items])=>`<section class="permission-group"><h3>${escapeHtml(category)}</h3><div class="permission-options">${items.map(item=>{
    const checked=selected.includes(item.code);
    const locked=Boolean(editing?.is_current_user);
    return`<label class="permission-option"><input type="checkbox" name="userPermission" value="${escapeHtml(item.code)}" ${checked?'checked':''} ${locked?'disabled':''}><span><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.description)}</span></span></label>`
  }).join('')}</div></section>`).join('');
}

function resetForm(){
  editingId=null;
  $('#userForm').reset();
  $('#userId').value='';
  $('#userActive').checked=true;
  $('#userActive').disabled=false;
  $$('input[name="userArea"]').forEach(node=>{node.disabled=false});
  $('#userDisplayName').value='';
  $('#userPassword').value='';
  $('#userPasswordLabel').hidden=false;
  $('#userPassword').required=true;
  $('#userFormTitle').textContent='Crear nuevo usuario';
  $('#userEditBadge').hidden=true;
  $('#cancelUserEdit').hidden=true;
  setError('#userError','');
  renderPermissionChoices([]);
}

function renderUsers(){
  const container=$('#usersList');
  if(!users.length){container.innerHTML='<div class="empty-state">No hay usuarios registrados.</div>';return}
  container.innerHTML=users.map(user=>{
    const areaLabels=user.areas.map(area=>areaNames[area]||area).join(', ')||'Sin áreas operativas';
    const permissionLabels=user.permissions.slice(0,5).map(code=>`<span class="privilege-chip">${escapeHtml(permissionName(code))}</span>`).join('');
    const remaining=Math.max(0,user.permissions.length-5);
    return`<article class="data-card user-card" data-user-id="${escapeHtml(user.id)}"><div><h3>${escapeHtml(user.display_name)}</h3><div class="user-status-row"><span class="status ${user.active?'ok':'bad'}">${user.active?'Activo':'Inactivo'}</span>${user.is_current_user?'<span class="badge">Sesión actual</span>':''}</div><div class="meta">${escapeHtml(areaLabels)}</div></div><div><div class="privilege-summary">${permissionLabels}${remaining?`<span class="privilege-chip">+${remaining} más</span>`:''}</div><div class="meta">${user.permissions.length} privilegios asignados</div></div><div class="data-actions"><button class="button secondary" data-action="edit-user" type="button">Editar</button><button class="button ghost" data-action="password-user" type="button">Cambiar clave</button></div></article>`
  }).join('');
}

export async function loadUsers(){
  const container=$('#usersList');
  showLoading(container);
  try{
    [users,permissions]=await Promise.all([api('/users'),api('/users/permissions')]);
    renderUsers();
    if(!editingId)renderPermissionChoices([]);
  }catch(error){container.innerHTML=`<div class="callout error">${escapeHtml(error.message)}</div>`}
}

function beginEdit(user){
  editingId=user.id;
  $('#userId').value=user.id;
  $('#userDisplayName').value=user.display_name;
  $('#userActive').checked=user.active;
  $('#userActive').disabled=user.is_current_user;
  $$('input[name="userArea"]').forEach(node=>{node.checked=user.areas.includes(node.value);node.disabled=user.is_current_user});
  $('#userPasswordLabel').hidden=true;
  $('#userPassword').required=false;
  $('#userPassword').value='';
  $('#userFormTitle').textContent=`Editar usuario: ${user.display_name}`;
  $('#userEditBadge').hidden=false;
  $('#cancelUserEdit').hidden=false;
  renderPermissionChoices(user.permissions);
  setError('#userError','');
  $('#userDisplayName').focus();
  window.scrollTo({top:0,behavior:'smooth'});
}

function payload(){
  return{
    display_name:$('#userDisplayName').value,
    active:$('#userActive').checked,
    areas:selectedValues('userArea'),
    permissions:selectedValues('userPermission'),
  }
}

async function submitUser(event){
  event.preventDefault();
  setError('#userError','');
  const body=payload();
  try{
    if(editingId){
      await api(`/users/${editingId}`,{method:'PUT',body});
      announce('Usuario y privilegios actualizados.');
    }else{
      body.password=$('#userPassword').value;
      await api('/users',{method:'POST',body});
      announce('Usuario creado correctamente.');
    }
    resetForm();
    await loadUsers();
    document.dispatchEvent(new CustomEvent('users-changed'));
  }catch(error){setError('#userError',error)}
}

function openPassword(user){
  $('#passwordUserId').value=user.id;
  $('#passwordTarget').textContent=`Usuario: ${user.display_name}`;
  $('#newUserPassword').value='';
  setError('#passwordError','');
  $('#passwordDialog').showModal();
  setTimeout(()=>$('#newUserPassword').focus(),0);
}

async function submitPassword(event){
  event.preventDefault();
  setError('#passwordError','');
  const user=users.find(item=>item.id===$('#passwordUserId').value);
  if(!user)return;
  if(!await confirmAction(`¿Restablecer la clave de ${user.display_name}? Se cerrarán sus sesiones activas.`))return;
  try{
    const result=await api(`/users/${user.id}/password`,{method:'PATCH',body:{password:$('#newUserPassword').value}});
    $('#passwordDialog').close();
    announce(result.message);
    if(user.is_current_user)setTimeout(()=>window.location.reload(),900);
  }catch(error){setError('#passwordError',error)}
}

function handleListClick(event){
  const button=event.target.closest('[data-action]');
  if(!button)return;
  const user=users.find(item=>item.id===button.closest('[data-user-id]')?.dataset.userId);
  if(!user)return;
  if(button.dataset.action==='edit-user')beginEdit(user);
  if(button.dataset.action==='password-user')openPassword(user);
}

export function initUsersPage(){
  $('#userForm').addEventListener('submit',submitUser);
  $('#cancelUserEdit').addEventListener('click',resetForm);
  $('#usersList').addEventListener('click',handleListClick);
  $('#selectAllPermissions').addEventListener('click',()=>$$('input[name="userPermission"]:not(:disabled)').forEach(node=>{node.checked=true}));
  $('#clearPermissions').addEventListener('click',()=>$$('input[name="userPermission"]:not(:disabled)').forEach(node=>{node.checked=false}));
  $('#passwordForm').addEventListener('submit',submitPassword);
  $('#closePasswordDialog').addEventListener('click',()=>$('#passwordDialog').close());
  resetForm();
}
