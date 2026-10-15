let csrfToken='';
export function setCsrf(token){csrfToken=token||''}
export async function api(path,{method='GET',body,headers={},signal}={}){
  const options={method,credentials:'same-origin',headers:{Accept:'application/json',...headers},signal};
  if(body instanceof FormData){options.body=body}else if(body!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body)}
  if(!['GET','HEAD','OPTIONS'].includes(method.toUpperCase())&&csrfToken){options.headers['X-CSRF-Token']=csrfToken}
  const response=await fetch(`/api${path}`,options);
  const type=response.headers.get('content-type')||'';
  const payload=type.includes('application/json')?await response.json():await response.text();
  if(!response.ok){const error=new Error(payload?.error?.message||'No fue posible completar la operación.');error.status=response.status;error.code=payload?.error?.code;error.fields=payload?.error?.fields||[];throw error}
  return payload;
}
export function downloadUrl(path){window.location.assign(`/api${path}`)}
export function reportUrl(path){window.open(`/api${path}`,'_blank','noopener,noreferrer')}
