export const $=(selector,root=document)=>root.querySelector(selector);
export const $$=(selector,root=document)=>Array.from(root.querySelectorAll(selector));
export const money=value=>new Intl.NumberFormat('es-CL',{style:'currency',currency:'CLP',maximumFractionDigits:0}).format(Number(value)||0);
export const dateCL=value=>{if(!value)return'—';const date=new Date(`${String(value).slice(0,10)}T12:00:00`);return new Intl.DateTimeFormat('es-CL').format(date)};
export function announce(message){$('#liveRegion').textContent=message;toast(message)}
export function toast(message){const node=$('#toast');node.textContent=message;node.classList.add('show');clearTimeout(node.timer);node.timer=setTimeout(()=>node.classList.remove('show'),3200)}
export function setError(id,error){const node=$(id);if(!node)return;node.textContent=error?.message||String(error||'');if(error?.fields?.length)node.textContent+=` ${error.fields.map(item=>`${item.field}: ${item.message}`).join(' · ')}`}
export function metricCards(items){return items.map(item=>`<div class="metric-card"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>`).join('')}
export function escapeHtml(value){return String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]))}
export function accountClass(level){return `level-${Math.min(4,Math.max(0,Number(level)||0))}`}
export function indentClass(level){return `indent-${Math.min(4,Math.max(0,Number(level)||0))}`}
export function debounce(fn,delay=300){let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay)}}
export function today(){const now=new Date();return new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,10)}
export function options(items,{value='code',label=item=>`${item.code} · ${item.name}`,empty='Seleccione'}={}){return `<option value="">${escapeHtml(empty)}</option>`+items.map(item=>`<option value="${escapeHtml(item[value])}">${escapeHtml(label(item))}</option>`).join('')}
export function showLoading(container,message='Cargando…'){container.innerHTML=`<div class="progress-message">${escapeHtml(message)}</div>`}
export async function confirmAction(message){return window.confirm(message)}
