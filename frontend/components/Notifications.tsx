"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

type NotificationKind = "success" | "error";
type Notification = {
  id: number;
  message: string;
  kind: NotificationKind;
};

const NotificationsContext = createContext<
  ((message: string, kind?: NotificationKind) => void) | null
>(null);

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const nextId = useRef(0);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
    setNotifications((current) => current.filter((notification) => notification.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, kind: NotificationKind = "success") => {
      const id = ++nextId.current;
      setNotifications((current) => [...current, { id, message, kind }]);
      timers.current.set(id, setTimeout(() => dismiss(id), 5000));
    },
    [dismiss],
  );

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      timers.current.clear();
    },
    [],
  );

  return (
    <NotificationsContext.Provider value={notify}>
      {children}
      <div className="fixed right-4 top-20 z-50 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-3">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            role={notification.kind === "error" ? "alert" : "status"}
            className={`flex items-start justify-between gap-4 rounded-xl border p-4 shadow-lg ${
              notification.kind === "error"
                ? "border-red-200 bg-red-50 text-red-900"
                : "border-green-200 bg-green-50 text-green-900"
            }`}
          >
            <p className="text-sm font-medium">{notification.message}</p>
            <button
              type="button"
              onClick={() => dismiss(notification.id)}
              aria-label="Dismiss notification"
              className="shrink-0 text-lg leading-5 opacity-70 hover:opacity-100"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const notify = useContext(NotificationsContext);
  if (!notify) {
    throw new Error("useNotifications must be used within NotificationsProvider");
  }
  return notify;
}
