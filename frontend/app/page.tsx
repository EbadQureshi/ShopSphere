"use client";
import {useCallback,useEffect,useState} from "react"; import {api} from "@/lib/api"; import ProductCard from "@/components/ProductCard";
export default function Home(){
 const[p,setP]=useState<any[]>([]);
 const[q,setQ]=useState("");
 const[error,setError]=useState("");
 const[loading,setLoading]=useState(true);
 const load=useCallback(async(s="")=>{
  setLoading(true);
  setError("");
  try{setP(await api.products(s?`?search=${encodeURIComponent(s)}`:""))}
  catch(e){setError(e instanceof TypeError?"Cannot connect to the ShopSphere API. Start the backend and check NEXT_PUBLIC_API_URL.":e instanceof Error?e.message:"Could not load products.");setP([])}
  finally{setLoading(false)}
 },[]);
 useEffect(()=>{void load()},[load]);
 return <>
  <main>
   <section className="bg-gray-950 text-white">
    <div className="mx-auto max-w-7xl px-5 py-20">
     <p className="font-bold text-orange-400">SHOPSPHERE</p>
     <h1 className="mt-3 max-w-3xl text-5xl font-black md:text-7xl">Everything you want. One smart store.</h1>
     <p className="mt-5 max-w-2xl text-lg text-gray-300">A clean full-stack shopping experience powered by Next.js, FastAPI and PostgreSQL.</p>
     <form onSubmit={event=>{event.preventDefault();void load(q)}} className="mt-8 flex max-w-xl rounded-2xl bg-white p-2">
      <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search products..." className="flex-1 px-3 text-gray-900 outline-none"/>
      <button type="submit" className="rounded-xl bg-orange-500 px-5 font-bold">Search</button>
     </form>
    </div>
   </section>
   <section className="mx-auto max-w-7xl px-5 py-14">
    <div className="mb-8 flex justify-between">
     <h2 className="text-3xl font-black">Featured products</h2>
     <span className="text-sm text-gray-500">{loading?"Loading...":`${p.length} products`}</span>
    </div>
    {error?<div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900">
     <p>{error}</p>
     <button type="button" onClick={()=>void load(q)} className="mt-4 rounded-lg bg-gray-950 px-4 py-2 font-bold text-white">Retry</button>
    </div>:<div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">{p.map(x=><ProductCard key={x.id} p={x}/>)}</div>}
   </section>
  </main>
 </>
}
