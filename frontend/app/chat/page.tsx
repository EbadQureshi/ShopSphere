"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { ApiError, api, ChatProduct, clearSessionToken, getSessionToken } from "@/lib/api";
import { useNotifications } from "@/components/Notifications";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  products?: ChatProduct[];
};

function renderInlineFormatting(text: string) {
  const segments = text.split(/(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)/g);

  return segments.map((segment, index) => {
    const bold = segment.match(/^(?:\*\*|__)(.+)(?:\*\*|__)$/);
    if (bold) return <strong key={index}>{bold[1]}</strong>;

    const italic = segment.match(/^(?:\*|_)(.+)(?:\*|_)$/);
    if (italic) return <em key={index}>{italic[1]}</em>;

    return <span key={index}>{segment.replace(/[*`~]/g, "")}</span>;
  });
}

function renderAssistantContent(content: string) {
  const lines = content.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      blocks.push(
        <h3 key={`heading-${index}`} className="mt-4 text-base font-extrabold first:mt-0">
          {renderInlineFormatting(heading[1])}
        </h3>,
      );
      index += 1;
      continue;
    }

    const orderedItem = line.match(/^\d+[.)]\s+(.+)$/);
    const unorderedItem = line.match(/^[-*+]\s+(.+)$/);
    if (orderedItem || unorderedItem) {
      const ordered = Boolean(orderedItem);
      const items: string[] = [];
      while (index < lines.length) {
        const itemLine = lines[index].trim();
        const match = ordered
          ? itemLine.match(/^\d+[.)]\s+(.+)$/)
          : itemLine.match(/^[-*+]\s+(.+)$/);
        if (!match) break;
        items.push(match[1]);
        index += 1;
      }

      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List
          key={`list-${index}`}
          className={`my-3 space-y-2 pl-5 marker:text-orange-500 ${
            ordered ? "list-decimal" : "list-disc"
          }`}
        >
          {items.map((item, itemIndex) => (
            <li key={itemIndex} className="pl-1 leading-relaxed">
              {renderInlineFormatting(item)}
            </li>
          ))}
        </List>,
      );
      continue;
    }

    blocks.push(
      <p key={`paragraph-${index}`} className="my-2 leading-relaxed first:mt-0 last:mb-0">
        {renderInlineFormatting(line)}
      </p>,
    );
    index += 1;
  }

  return blocks;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [message, setMessage] = useState("");
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sessionId, setSessionId] = useState<number | null>(null);
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
    api.createChatSession()
      .then((session) => setSessionId(session.id))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearSessionToken();
          setAuthenticated(false);
          return;
        }
        notify(error instanceof Error ? error.message : "Could not start a new chat.", "error");
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
      if (sessionId === null) return;
      const result = await api.chat(sessionId, question);
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
        {loadingHistory ? <p className="text-gray-500">Starting a new chat...</p> : null}
        {!loadingHistory && messages.length === 0 ? <p className="text-gray-500">Start a conversation. I can help you find products from our catalog.</p> : null}
        {messages.map((item) => (
          <div key={item.id} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[95%] rounded-2xl px-4 py-3 shadow-sm ${
              item.role === "user"
                ? "bg-gray-950 text-white"
                : "border border-orange-100 bg-gradient-to-br from-orange-50 to-white text-gray-900"
            }`}>
              <p className={`mb-2 text-xs font-bold uppercase tracking-wide ${
                item.role === "user" ? "text-yellow-300" : "text-orange-600"
              }`}>
                {item.role === "user" ? "You" : "ShopSphere Assistant"}
              </p>
              {item.role === "assistant" ? (
                <div className="text-[15px]">{renderAssistantContent(item.content)}</div>
              ) : (
                <p className="whitespace-pre-wrap leading-relaxed">{item.content}</p>
              )}
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
          disabled={sending || sessionId === null}
        />
        <button
          type="submit"
          disabled={sending || sessionId === null || !message.trim()}
          className="rounded-xl bg-orange-500 px-6 py-3 font-bold text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </main>
  );
}
