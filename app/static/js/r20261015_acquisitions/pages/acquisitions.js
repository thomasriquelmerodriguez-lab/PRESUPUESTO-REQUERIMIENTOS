import{api}from'../api.js';
import{state,hasPermission}from'../state.js';
import{$,money,dateCL,escapeHtml,debounce,announce,confirmAction,showLoading,today}from'../ui.js';

let currentItems=[];
let current=null;
let page=1;

const statusLabels={REGISTRADO:'Registrado',EN_ADQUISICIONES:'En adquisiciones',EN_LICITACION:'En licitación',ADJUDICADO:'Adjudicado',OC_EMITIDA:'OC emitida',CERRADO:'Cerrado'};
const statusOptions=()=>Object.entries(statusLabels).map(([value,label])=>`<option value="${value}">${label}</option>`).join('');
function badge(status,closed=false){const key=closed?'CERRADO':status;return`<span class="procurement-badge status-${escapeHtml(key.toLowerCase())}">${escapeHtml(statusLabels[key]||key)}</span>`}

function query(){
  const params=new URLSearchParams({area:state.area,page:String(page),page_size:'40'});
  const year=$('#acqYear').value,status=$('#acqStatus').value,q=$('#acqSearch').value.trim();
  if(year)params.set('year',year);if(status)params.set('status',status);if(q)params.set('q',q);
  return params;
}

function renderMetrics(data){
  $('#acqMetrics').innerHTML=[
    ['Solicitado original',money(data.original_total)],
    ['Órdenes de compra',money(data.orders_total)],
    ['Reserva pendiente',money(data.reservation_pending_total)],
    ['Saldo liberado',money(data.released_total)],
    ['Compromiso vigente',money(data.effective_commitment_total)],
  ].map(([label,value])=>`<div class="metric-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
}

function card(item){
  const manage=hasPermission('acquisitions.manage')?'<button class="button primary" data-action="manage" type="button">Gestionar</button>':'<button class="button ghost" data-action="manage" type="button">Ver detalle</button>';
  return `<article class="acquisition-card" data-id="${escapeHtml(item.id)}">
    <div class="acquisition-card-head"><div>${badge(item.procurement_status,item.procurement_closed)}<h3>${escapeHtml(item.expedient)}</h3><p>${escapeHtml(item.subject)}</p><small>${dateCL(item.request_date)} · ${escapeHtml(item.account_code)} · ${escapeHtml(item.department||'Sin departamento')}</small></div>${manage}</div>
    <div class="acquisition-financial-grid">
      <div><span>Solicitado</span><strong>${money(item.original_amount)}</strong></div>
      <div><span>OC emitidas</span><strong>${money(item.orders_total)}</strong></div>
      <div><span>Reserva pendiente</span><strong>${money(item.reservation_pending)}</strong></div>
      <div><span>Saldo liberado</span><strong class="positive">${money(item.released_amount)}</strong></div>
      <div><span>OC pendientes CAS</span><strong>${money(item.orders_pending_cas)}</strong></div>
      <div><span>Compromiso al presupuesto</span><strong>${money(item.effective_commitment)}</strong></div>
    </div>
  </article>`;
}

export async function loadAcquisitions(){
  if(!state.area)return;
  showLoading($('#acqList'),'Cargando requerimientos y órdenes de compra…');
  try{
    const data=await api(`/acquisitions?${query()}`);
    currentItems=data.items;
    renderMetrics(data);
    $('#acqSummary').textContent=`${data.total} requerimientos · Compromiso vigente: ${money(data.effective_commitment_total)} · Saldo liberado: ${money(data.released_total)}`;
    $('#acqList').innerHTML=data.items.length?data.items.map(card).join(''):'<div class="progress-message">No hay requerimientos para los filtros seleccionados.</div>';
    const pages=Math.max(1,Math.ceil(data.total/data.page_size));
    $('#acqPage').textContent=`Página ${data.page} de ${pages}`;
    $('#acqPrev').disabled=data.page<=1;$('#acqNext').disabled=data.page>=pages;
  }catch(error){
    $('#acqMetrics').innerHTML='';$('#acqSummary').textContent='';
    $('#acqList').innerHTML=`<div class="callout error">${escapeHtml(error.message)}</div>`;
  }
}

function renderDetail(item){
  current=item;
  $('#acqDialogTitle').textContent=`${item.expedient} · ${item.subject}`;
  $('#acqDialogMeta').textContent=`${item.budget_year} · ${item.account_code}${item.account_name?` · ${item.account_name}`:''}`;
  $('#acqDialogMetrics').innerHTML=[
    ['Solicitud original',money(item.original_amount)],
    ['Total OC',money(item.orders_total)],
    ['Reserva pendiente',money(item.reservation_pending)],
    ['Saldo liberado',money(item.released_amount)],
    ['OC pendiente CAS',money(item.orders_pending_cas)],
    ['OC conciliada CAS',money(item.orders_reconciled_cas)],
    ['Compromiso vigente',money(item.effective_commitment)],
  ].map(([label,value])=>`<div class="preview-stat"><span>${label}</span><strong>${value}</strong></div>`).join('');
  $('#acqStatusEdit').innerHTML=statusOptions();$('#acqStatusEdit').value=item.procurement_status;
  $('#acqClosed').checked=item.procurement_closed;
  $('#acqStatusForm').hidden=!hasPermission('acquisitions.manage');
  $('#orderPanel').hidden=!hasPermission('acquisitions.manage');
  renderOrders(item.orders);
}

function renderOrders(orders){
  const canManage=hasPermission('acquisitions.manage');
  $('#orderList').innerHTML=orders.length?orders.map(order=>`<article class="purchase-order-card" data-order-id="${escapeHtml(order.id)}">
    <div><div class="order-title"><strong>OC ${escapeHtml(order.order_number)}</strong>${order.cas_reconciled?'<span class="cas-chip reconciled">Conciliada con CAS</span>':'<span class="cas-chip pending">Pendiente CAS</span>'}</div><p>${dateCL(order.order_date)} · ${escapeHtml(order.supplier)}</p><small>${escapeHtml(order.tender_reference||'Sin referencia de licitación')}</small></div>
    <div class="order-amount">${money(order.amount)}</div>
    ${canManage?`<div class="data-actions"><button class="button ghost" data-order-action="edit" type="button">Editar</button><button class="button secondary" data-order-action="cas" type="button">${order.cas_reconciled?'Quitar conciliación':'Conciliar CAS'}</button><button class="button danger" data-order-action="delete" type="button">Eliminar</button></div>`:''}
  </article>`).join(''):'<div class="progress-message">Todavía no se han registrado órdenes de compra.</div>';
}

async function openDetail(id){
  try{const item=await api(`/acquisitions/${id}?area=${encodeURIComponent(state.area)}`);renderDetail(item);resetOrderForm();$('#acqDialog').showModal()}catch(error){announce(error.message)}
}

function resetOrderForm(){
  $('#orderForm').reset();$('#orderId').value='';$('#orderVersion').value='';$('#orderDate').value=today();$('#orderSave').textContent='Agregar orden de compra';$('#orderCancel').hidden=true;
}

async function saveStatus(event){
  event.preventDefault();if(!current||!hasPermission('acquisitions.manage'))return;
  const closed=$('#acqClosed').checked;
  if(closed&&!await confirmAction('Al cerrar el requerimiento se libera la diferencia no adjudicada. ¿Continuar?'))return;
  try{
    const item=await api(`/acquisitions/${current.id}/status?area=${encodeURIComponent(state.area)}`,{method:'PATCH',body:{status:$('#acqStatusEdit').value,closed}});
    renderDetail(item);announce(closed?'Requerimiento cerrado y saldo remanente liberado.':'Estado actualizado.');await loadAcquisitions();
  }catch(error){announce(error.message)}
}

async function saveOrder(event){
  event.preventDefault();if(!current||!hasPermission('acquisitions.manage'))return;
  const payload={order_number:$('#orderNumber').value,order_date:$('#orderDate').value,supplier:$('#orderSupplier').value,amount:Number($('#orderAmount').value),tender_reference:$('#orderTender').value,notes:$('#orderNotes').value,close_requirement:$('#orderClose').checked};
  const id=$('#orderId').value;
  if(id)payload.version=Number($('#orderVersion').value);
  if(payload.close_requirement&&!await confirmAction('Esta OC cerrará el requerimiento y liberará cualquier diferencia no adjudicada. ¿Continuar?'))return;
  try{
    const item=await api(id?`/acquisitions/${current.id}/orders/${id}?area=${encodeURIComponent(state.area)}`:`/acquisitions/${current.id}/orders?area=${encodeURIComponent(state.area)}`,{method:id?'PUT':'POST',body:payload});
    renderDetail(item);resetOrderForm();announce(id?'Orden de compra actualizada.':'Orden de compra registrada.');await loadAcquisitions();
  }catch(error){announce(error.message)}
}

function editOrder(order){
  $('#orderId').value=order.id;$('#orderVersion').value=order.version;$('#orderNumber').value=order.order_number;$('#orderDate').value=String(order.order_date).slice(0,10);$('#orderSupplier').value=order.supplier;$('#orderAmount').value=order.amount;$('#orderTender').value=order.tender_reference;$('#orderNotes').value=order.notes;$('#orderClose').checked=false;$('#orderSave').textContent='Guardar cambios';$('#orderCancel').hidden=false;$('#orderNumber').focus();
}

async function orderAction(event){
  const button=event.target.closest('[data-order-action]');if(!button||!current||!hasPermission('acquisitions.manage'))return;
  const order=current.orders.find(item=>item.id===button.closest('[data-order-id]').dataset.orderId);if(!order)return;
  if(button.dataset.orderAction==='edit'){editOrder(order);return}
  if(button.dataset.orderAction==='cas'){
    const next=!order.cas_reconciled;
    const message=next?'Confirme que esta orden ya está incluida en Obligado CAS. Al conciliarla dejará de descontarse separadamente.':'¿Quitar la conciliación? La OC volverá a descontarse separadamente del CAS.';
    if(!await confirmAction(message))return;
    try{const item=await api(`/acquisitions/${current.id}/orders/${order.id}/cas?area=${encodeURIComponent(state.area)}`,{method:'PATCH',body:{reconciled:next,version:order.version}});renderDetail(item);announce(next?'OC conciliada con CAS.':'Conciliación retirada.');await loadAcquisitions()}catch(error){announce(error.message)}
    return;
  }
  if(button.dataset.orderAction==='delete'&&await confirmAction(`¿Eliminar la OC ${order.order_number}?`)){
    try{const item=await api(`/acquisitions/${current.id}/orders/${order.id}?area=${encodeURIComponent(state.area)}&version=${order.version}`,{method:'DELETE'});renderDetail(item);announce('Orden de compra eliminada.');await loadAcquisitions()}catch(error){announce(error.message)}
  }
}

export function initAcquisitionsPage(){
  $('#acqYear').addEventListener('change',()=>{page=1;loadAcquisitions()});
  $('#acqStatus').addEventListener('change',()=>{page=1;loadAcquisitions()});
  $('#acqSearch').addEventListener('input',debounce(()=>{page=1;loadAcquisitions()}));
  $('#acqList').addEventListener('click',event=>{const button=event.target.closest('[data-action="manage"]');if(button)openDetail(button.closest('[data-id]').dataset.id)});
  $('#acqPrev').addEventListener('click',()=>{page=Math.max(1,page-1);loadAcquisitions()});
  $('#acqNext').addEventListener('click',()=>{page+=1;loadAcquisitions()});
  $('#acqStatusEdit').innerHTML=statusOptions();
  $('#acqStatusForm').addEventListener('submit',saveStatus);
  $('#orderForm').addEventListener('submit',saveOrder);
  $('#orderCancel').addEventListener('click',resetOrderForm);
  $('#orderList').addEventListener('click',orderAction);
  $('#closeAcqDialog').addEventListener('click',()=>$('#acqDialog').close());
  $('#orderDate').value=today();
}
