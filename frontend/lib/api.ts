const BASE=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8001/api/v1";
export const AUTH_CHANGE_EVENT="shopsphere:auth-change";
export function getSessionToken(){
 if(typeof window==="undefined")return null;
 const current=sessionStorage.getItem("token");
 if(current)return current;
 const legacy=localStorage.getItem("token");
 if(legacy){sessionStorage.setItem("token",legacy);localStorage.removeItem("token");return legacy}
 return null;
}
export function setSessionToken(token:string){
 sessionStorage.setItem("token",token);
 localStorage.removeItem("token");
 window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}
export function clearSessionToken(){
 sessionStorage.removeItem("token");
 localStorage.removeItem("token");
 window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}
export class ApiError extends Error{
 constructor(message:string,readonly status:number){
  super(message);
  this.name="ApiError";
 }
}
export type ChatProduct={
 id:number;
 name:string;
 description:string;
 price:number|string;
 image_url:string;
 stock:number;
 category_name:string;
};
type ChatReply={
 answer:{id:number;role:"assistant";content:string;created_at:string};
 messages:{id:number;role:"user"|"assistant";content:string;created_at:string}[];
 products:ChatProduct[];
};
export type ChatSession={id:number};
export type ChatSessionSummary={id:number;preview:string;updated_at:string};
async function req<T>(path:string,options:RequestInit={}):Promise<T>{
 const token=getSessionToken();
 const headers=new Headers(options.headers);
 if(options.body!==undefined&&!headers.has("Content-Type"))headers.set("Content-Type","application/json");
 if(token&&!headers.has("Authorization"))headers.set("Authorization",`Bearer ${token}`);
 const r=await fetch(BASE+path,{...options,headers});
 if(!r.ok){
  const b=await r.json().catch(()=>({}));
  if(r.status===401)clearSessionToken();
  throw new ApiError(b.detail||"Request failed",r.status);
 }
 return r.json();
}
export const api={
 products:(q="")=>req<any[]>(`/products${q}`),
 product:(id:number)=>req<any>(`/products/${id}`),
 related:(id:number)=>req<any[]>(`/products/${id}/related`),
 login:(d:any)=>req<any>("/auth/login",{method:"POST",body:JSON.stringify(d)}),
 register:(d:any)=>req<any>("/auth/register",{method:"POST",body:JSON.stringify(d)}),
 me:()=>req<{id:number;name:string;email:string;is_admin:boolean}>("/auth/me"),
 chatHistory:()=>req<{messages:{id:number;role:"user"|"assistant";content:string;created_at:string}[]}>("/chat/history"),
 createChatSession:()=>req<ChatSession>("/chat/sessions",{method:"POST"}),
 chatSessions:()=>req<ChatSessionSummary[]>("/chat/sessions"),
 chatSessionHistory:(sessionId:number)=>req<{messages:{id:number;role:"user"|"assistant";content:string;created_at:string}[]}>(
  `/chat/sessions/${sessionId}`
 ),
 chat:(sessionId:number,message:string)=>req<ChatReply>("/chat",{method:"POST",body:JSON.stringify({session_id:sessionId,message})}),
 cart:()=>req<any>("/cart"),
 add:(product_id:number,quantity=1)=>req<any>("/cart/items",{method:"POST",body:JSON.stringify({product_id,quantity})}),
 remove:(id:number)=>req<any>(`/cart/items/${id}`,{method:"DELETE"}),
 checkout:(shipping_address:string)=>req<any>("/orders",{method:"POST",body:JSON.stringify({shipping_address})})
};
