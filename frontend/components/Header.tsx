"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {AUTH_CHANGE_EVENT,getSessionToken} from "@/lib/api";
export default function Header(){
 const[loggedIn,setLoggedIn]=useState(false);
 useEffect(()=>{
  const syncSession=()=>setLoggedIn(Boolean(getSessionToken()));
  syncSession();
  window.addEventListener(AUTH_CHANGE_EVENT,syncSession);
  window.addEventListener("storage",syncSession);
  return()=>{window.removeEventListener(AUTH_CHANGE_EVENT,syncSession);window.removeEventListener("storage",syncSession)};
 },[]);
 return <header className="sticky top-0 z-30 border-b bg-white/95 backdrop-blur"><div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4"><Link href="/" className="text-xl font-black">Shop<span className="text-orange-500">Sphere</span></Link><nav className="flex gap-6 text-sm font-bold"><Link href="/">Shop</Link><Link href="/cart">Cart</Link><Link href="/chat">Chat</Link>{loggedIn?<Link href="/account">My account</Link>:<><Link href="/register">Create account</Link><Link href="/login">Sign in</Link></>}</nav></div></header>
}
