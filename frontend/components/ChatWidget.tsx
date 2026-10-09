"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { History, MessageSquare, Plus, Send, X } from "lucide-react";
import {
  ApiError,
  api,
  AUTH_CHANGE_EVENT,
  ChatProduct,
  ChatSessionSummary,
  clearSessionToken,
  getSessionToken,
} from "@/lib/api";
import { useNotifications } from "@/components/Notifications";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  products?: ChatProduct[];
};

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [creatingSession, setCreatingSession] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionError, setSessionError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingSessionId, setLoadingSessionId] = useState<number | null>(null);
  const sessionRequestId = useRef(0);
  const historyRequestId = useRef(0);
  const sessionToken = useRef<string | null>(null);
  const endOfMessages = useRef<HTMLDivElement>(null);
  const notify = useNotifications();

  useEffect(() => {
    const syncAuthentication = () => {
      const token = getSessionToken();
      setAuthenticated(Boolean(token));
      if (sessionToken.current !== token) {
        sessionToken.current = token;
        sessionRequestId.current += 1;
        historyRequestId.current += 1;
        setIsOpen(false);
        setSessionId(null);
        setCreatingSession(false);
        setLoadingSessions(false);
        setLoadingSessionId(null);
        setMessages([]);
        setMessage("");
        setSending(false);
        setShowHistory(false);
        setChatSessions([]);
      }
    };
    syncAuthentication();
    window.addEventListener(AUTH_CHANGE_EVENT, syncAuthentication);
    window.addEventListener("storage", syncAuthentication);
    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, syncAuthentication);
      window.removeEventListener("storage", syncAuthentication);
    };
  }, []);

  useEffect(() => {
    endOfMessages.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, creatingSession]);

  async function startNewChat() {
    const requestId = ++sessionRequestId.current;
    historyRequestId.current += 1;
    setMessages([]);
    setMessage("");
    setSending(false);
    setSessionId(null);
    setSessionError("");
    setShowHistory(false);
    if (!getSessionToken()) return;

    setCreatingSession(true);
    setLoadingSessionId(null);
    try {
      const session = await api.createChatSession();
      if (sessionRequestId.current === requestId) setSessionId(session.id);
    } catch (error) {
      if (sessionRequestId.current === requestId) {
        if (error instanceof ApiError && error.status === 401) {
          clearSessionToken();
        } else {
          const detail = error instanceof Error ? error.message : "Could not start a new chat.";
          setSessionError(detail);
          notify(detail, "error");
        }
      }
    } finally {
      if (sessionRequestId.current === requestId) setCreatingSession(false);
    }
  }

  async function openChat() {
    setIsOpen(true);
    await startNewChat();
  }

  async function showChatHistory() {
    setShowHistory(true);
    setSessionError("");
    if (chatSessions.length > 0 || loadingSessions) return;

    const requestId = ++historyRequestId.current;
    setLoadingSessions(true);
    try {
      const sessions = await api.chatSessions();
      if (historyRequestId.current === requestId) setChatSessions(sessions);
    } catch (error) {
      if (historyRequestId.current === requestId) {
        if (error instanceof ApiError && error.status === 401) {
          clearSessionToken();
        } else {
          const detail = error instanceof Error ? error.message : "Could not load previous chats.";
          setSessionError(detail);
          notify(detail, "error");
        }
      }
    } finally {
      if (historyRequestId.current === requestId) setLoadingSessions(false);
    }
  }

  async function openPreviousChat(chatId: number) {
    const requestId = ++sessionRequestId.current;
    historyRequestId.current += 1;
    setLoadingSessionId(chatId);
    setSessionId(null);
    setMessages([]);
    setMessage("");
    setSending(false);
    setSessionError("");
    setShowHistory(false);
    try {
      const result = await api.chatSessionHistory(chatId);
      if (sessionRequestId.current === requestId) {
        setSessionId(chatId);
        setMessages(result.messages);
      }
    } catch (error) {
      if (sessionRequestId.current === requestId) {
        if (error instanceof ApiError && error.status === 401) {
          clearSessionToken();
        } else {
          const detail = error instanceof Error ? error.message : "Could not reopen this chat.";
          setSessionError(detail);
          setShowHistory(true);
          notify(detail, "error");
        }
      }
    } finally {
      if (sessionRequestId.current === requestId) setLoadingSessionId(null);
    }
  }

  function closeChat() {
    sessionRequestId.current += 1;
    historyRequestId.current += 1;
    setIsOpen(false);
    setSessionId(null);
    setCreatingSession(false);
    setLoadingSessionId(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = message.trim();
    if (!question || sending || sessionId === null) return;
    const requestId = sessionRequestId.current;
    setSending(true);
    try {
      const result = await api.chat(sessionId, question);
      if (sessionRequestId.current !== requestId) return;
      setMessages((current) => result.messages.map((item) => {
        const previous = current.find((existing) => existing.id === item.id);
        return item.id === result.answer.id
          ? { ...item, products: result.products }
          : { ...item, products: previous?.products };
      }));
      historyRequestId.current += 1;
      setChatSessions([]);
      setMessage("");
    } catch (error) {
      if (sessionRequestId.current !== requestId) return;
      if (error instanceof ApiError && error.status === 401) {
        clearSessionToken();
      } else {
        notify(error instanceof Error ? error.message : "Could not send your message.", "error");
      }
    } finally {
      if (sessionRequestId.current === requestId) setSending(false);
    }
  }

  return (
    <div className="fixed bottom-0 right-5 z-40 sm:right-8">
      {isOpen ? (
        <section
          id="shopsphere-chat-panel"
          aria-label="ShopSphere messages"
          className="mb-3 flex h-[min(70vh,34rem)] w-[min(calc(100vw-2rem),24rem)] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl"
        >
          <header className="flex items-center justify-between bg-gray-950 px-4 py-3 text-white">
            <div>
              <h2 className="font-bold">ShopSphere Assistant</h2>
              <p className="text-xs text-gray-300">
                {showHistory ? "Your previous conversations" : "Product help, whenever you need it"}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {authenticated ? (
                <>
                  <button
                    type="button"
                    onClick={() => void showChatHistory()}
                    aria-label="Show previous chats"
                    title="Previous chats"
                    className={`rounded-lg p-2 transition hover:bg-white/10 ${showHistory ? "bg-white/15" : ""}`}
                  >
                    <History size={19} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void startNewChat()}
                    aria-label="Start a new chat"
                    title="New chat"
                    className="rounded-lg p-2 transition hover:bg-white/10"
                  >
                    <Plus size={20} aria-hidden="true" />
                  </button>
                </>
              ) : null}
              <button
                type="button"
                onClick={closeChat}
                aria-label="Close messages"
                className="rounded-lg p-2 transition hover:bg-white/10"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>
          </header>

          {!authenticated ? (
            <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
              <MessageSquare className="mb-3 text-orange-500" size={32} aria-hidden="true" />
              <p className="font-bold">Sign in to start a conversation</p>
              <p className="mt-2 text-sm text-gray-500">Your shopping chats are private to your account.</p>
              <Link href="/login" className="mt-5 rounded-xl bg-gray-950 px-5 py-2.5 font-bold text-white">
                Sign in
              </Link>
            </div>
          ) : (
            <>
              {showHistory ? (
                <div aria-label="Previous conversations" className="flex-1 overflow-y-auto bg-gray-50 p-3">
                  {loadingSessions ? (
                    <p role="status" className="p-3 text-sm text-gray-500">Loading previous chats...</p>
                  ) : chatSessions.length === 0 ? (
                    <p className="rounded-xl bg-white p-4 text-sm leading-relaxed text-gray-600">
                      No previous conversations yet. Your chats will appear here after you send a message.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {chatSessions.map((chat) => (
                        <li key={chat.id}>
                          <button
                            type="button"
                            onClick={() => void openPreviousChat(chat.id)}
                            disabled={loadingSessionId !== null}
                            className="w-full rounded-xl border border-gray-200 bg-white p-3 text-left transition hover:border-orange-300 hover:shadow-sm disabled:opacity-60"
                          >
                            <span className="block line-clamp-2 text-sm font-semibold text-gray-900">
                              {chat.preview}
                            </span>
                            <span className="mt-1 block text-xs text-gray-500">
                              {new Date(chat.updated_at).toLocaleString()}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {loadingSessionId !== null ? (
                    <p role="status" className="p-3 text-sm text-gray-500">Opening conversation...</p>
                  ) : null}
                  {sessionError ? <p role="alert" className="mt-2 text-sm text-red-700">{sessionError}</p> : null}
                </div>
              ) : (
                <div
                  aria-label="Chat messages"
                  aria-live="polite"
                  className="flex-1 space-y-3 overflow-y-auto bg-gray-50 p-4"
                >
                {messages.length === 0 && !creatingSession && loadingSessionId === null ? (
                  <div className="rounded-2xl border border-orange-100 bg-white p-4 text-sm leading-relaxed text-gray-700 shadow-sm">
                    Hi! I can help you find products, compare prices, and answer questions about our catalog.
                  </div>
                ) : null}
                {messages.map((item) => (
                  <div
                    key={item.id}
                    className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                      item.role === "user"
                        ? "bg-gray-950 text-white"
                        : "border border-orange-100 bg-white text-gray-900 shadow-sm"
                    }`}>
                      <p className="whitespace-pre-wrap">{item.content}</p>
                      {item.role === "assistant" && item.products?.length ? (
                        <div className="mt-3 space-y-2">
                          {item.products.map((product) => (
                            <Link
                              key={product.id}
                              href={`/products/${product.id}`}
                              className="flex items-center gap-3 rounded-xl border border-gray-100 p-2.5 transition hover:border-orange-300"
                            >
                              {product.image_url ? (
                                <img
                                  src={product.image_url}
                                  alt=""
                                  className="h-12 w-12 rounded-lg bg-gray-50 object-contain p-1"
                                />
                              ) : (
                                <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-50" aria-hidden="true">
                                  🛍️
                                </span>
                              )}
                              <span className="min-w-0 flex-1">
                                <span className="block line-clamp-2 font-semibold">{product.name}</span>
                                <span className="mt-1 block font-bold text-orange-600">
                                  ${Number(product.price).toFixed(2)}
                                </span>
                              </span>
                            </Link>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
                {sessionError ? <p role="alert" className="text-sm text-red-700">{sessionError}</p> : null}
                {creatingSession || loadingSessionId !== null || sending ? (
                  <p role="status" className="text-xs text-gray-500">
                    {creatingSession
                      ? "Starting a new chat..."
                      : loadingSessionId !== null
                        ? "Opening conversation..."
                        : "Finding helpful answers..."}
                  </p>
                ) : null}
                <div ref={endOfMessages} />
                </div>
              )}

              {!showHistory ? (
                <form onSubmit={submit} className="flex gap-2 border-t bg-white p-3">
                  <input
                    aria-label="Message"
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    maxLength={2000}
                    placeholder="Ask about a product..."
                    className="min-w-0 flex-1 rounded-xl border px-3 py-2.5 text-sm outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
                    disabled={!sessionId || sending}
                  />
                  <button
                    type="submit"
                    aria-label="Send message"
                    disabled={!sessionId || sending || !message.trim()}
                    className="flex h-11 w-11 items-center justify-center rounded-xl bg-orange-500 text-white transition hover:bg-orange-600 disabled:opacity-50"
                  >
                    <Send size={18} aria-hidden="true" />
                  </button>
                </form>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      <button
        type="button"
        onClick={() => {
          if (isOpen) closeChat();
          else void openChat();
        }}
        aria-expanded={isOpen}
        aria-controls="shopsphere-chat-panel"
        className="mb-0 flex items-center gap-3 rounded-t-md border border-b-0 border-gray-300 bg-white px-5 py-3 text-lg font-medium text-sky-950 shadow-[0_-3px_14px_rgba(15,23,42,0.16)] transition hover:bg-gray-50"
      >
        <MessageSquare size={24} fill="currentColor" strokeWidth={1.5} aria-hidden="true" />
        Messages
      </button>
    </div>
  );
}
