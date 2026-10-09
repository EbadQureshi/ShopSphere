"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, api, ChatProduct, clearSessionToken, getSessionToken } from "@/lib/api";
import { useNotifications } from "@/components/Notifications";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  products?: ChatProduct[];
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [message, setMessage] = useState("");
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const endOfMessages = useRef<HTMLDivElement>(null);
  const notify = useNotifications();

  useEffect(() => {
    if (!getSessionToken()) {
      setAuthenticated(false);
      setLoadingHistory(false);
      return;
    }
    setAuthenticated(true);
    api.chatHistory()
      .then((result) => setMessages(result.messages))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearSessionToken();
          setAuthenticated(false);
          return;
        }
        notify(error instanceof Error ? error.message : "Could not load chat history.", "error");
      })
      .finally(() => setLoadingHistory(false));
  }, [notify]);

  useEffect(() => {
    endOfMessages.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = message.trim();
    if (!question || sending) return;
    setSending(true);
    try {
      const result = await api.chat(question);
      setMessages(result.messages.map((item) => (
        item.id === result.answer.id ? { ...item, products: result.products } : item
      )));
      setMessage("");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearSessionToken();
        setAuthenticated(false);
        return;
      }
      notify(error instanceof Error ? error.message : "Could not send your message.", "error");
    } finally {
      setSending(false);
    }
  }

  if (authenticated === false) {
    return (
      <main className="mx-auto max-w-md px-5 py-20 text-center">
        <h1 className="text-3xl font-black">Sign in to chat</h1>
        <p className="mt-3 text-gray-600">Your chat history is private to your account.</p>
        <Link href="/login" className="mt-6 inline-block rounded-xl bg-gray-950 px-6 py-3 font-bold text-white">Sign in</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-4xl flex-col px-5 py-10">
      <h1 className="text-3xl font-black">ShopSphere Assistant</h1>
      <p className="mt-2 text-gray-600">Ask about products, prices, availability, and recommendations. Your question and recent chat context are sent to Groq to generate replies.</p>
      <section aria-label="Chat history" className="mt-6 flex-1 space-y-4 overflow-y-auto rounded-2xl border bg-white p-5">
        {loadingHistory ? <p className="text-gray-500">Loading your chat...</p> : null}
        {!loadingHistory && messages.length === 0 ? <p className="text-gray-500">Start a conversation. I can help you find products from our catalog.</p> : null}
        {messages.map((item) => (
          <div key={item.id} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[95%] rounded-2xl px-4 py-3 ${
              item.role === "user" ? "bg-gray-950 text-white" : "bg-orange-50 text-gray-900"
            }`}>
              <p className="whitespace-pre-wrap">{item.content}</p>
              {item.role === "assistant" && item.products?.length ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {item.products.map((product) => (
                    <Link
                      key={product.id}
                      href={`/products/${product.id}`}
                      className="group overflow-hidden rounded-xl border border-orange-100 bg-white text-gray-900 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                    >
                      {product.image_url ? (
                        <img
                          src={product.image_url}
                          alt={product.name}
                          className="h-36 w-full bg-gray-50 object-contain p-3"
                        />
                      ) : (
                        <div className="flex h-36 items-center justify-center bg-gradient-to-br from-orange-50 to-amber-100 text-4xl" aria-hidden="true">
                          🛍️
                        </div>
                      )}
                      <div className="p-3">
                        <span className="text-xs font-semibold uppercase tracking-wide text-orange-600">
                          {product.category_name}
                        </span>
                        <h2 className="mt-1 line-clamp-2 min-h-10 font-bold group-hover:text-orange-600">
                          {product.name}
                        </h2>
                        <p className="mt-1 line-clamp-2 min-h-10 text-sm text-gray-500">
                          {product.description}
                        </p>
                        <div className="mt-3 flex items-center justify-between gap-2">
                          <span className="text-lg font-black">${Number(product.price).toFixed(2)}</span>
                          <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                            product.stock > 0 ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"
                          }`}>
                            {product.stock > 0 ? `${product.stock} in stock` : "Out of stock"}
                          </span>
                        </div>
                        <span className="mt-3 block rounded-lg bg-gray-950 px-3 py-2 text-center text-sm font-bold text-white transition group-hover:bg-orange-500">
                          View product
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ))}
        {sending ? <p role="status" className="text-sm text-gray-500">Finding relevant products and preparing an answer...</p> : null}
        <div ref={endOfMessages} />
      </section>
      <form onSubmit={submit} className="mt-4 flex gap-3">
        <input
          aria-label="Message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          maxLength={2000}
          placeholder="Ask about a product..."
          className="min-w-0 flex-1 rounded-xl border bg-white px-4 py-3"
          disabled={sending}
        />
        <button
          type="submit"
          disabled={sending || !message.trim()}
          className="rounded-xl bg-orange-500 px-6 py-3 font-bold text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </main>
  );
}
