export async function api(path:string,body?:unknown,method?:string,signal?:AbortSignal):Promise<any>{
 const res=await fetch('/api'+path,{method:method||(body===undefined?'GET':'POST'),headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});
 const data=await res.json();if(!res.ok)throw new Error(data.error?.message||(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail))||`HTTP ${res.status}`);return data;
}
export function download(name:string,content:string,type='application/json'){const u=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
