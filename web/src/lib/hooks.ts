import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, wsUrl } from "./api";
import { emptySession, reduce, type SessionState } from "./session";
import type { ServerEvent, SessionInfo } from "./types";

/** Live state of one session: a snapshot over the WebSocket, then every event. */
export function useSessionStream(sessionId: string | null): SessionState {
  const [state, dispatch] = useReducer(reduce, emptySession);
  useEffect(() => {
    dispatch({ type: "snapshot_reset", data: null });
    if (!sessionId) return;
    let closed = false;
    let ws: WebSocket | null = null;
    let retry: number | undefined;
    const connect = () => {
      ws = new WebSocket(wsUrl(`/sessions/${sessionId}/events`));
      ws.onmessage = (m) => dispatch(JSON.parse(m.data) as ServerEvent);
      ws.onclose = () => {
        if (!closed) retry = window.setTimeout(connect, 1000);
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry);
      ws?.close();
    };
  }, [sessionId]);
  return sessionId ? state : emptySession;
}

/** The session list, refreshed whenever any session changes. */
export function useSessionList(): [SessionInfo[], () => void] {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const timer = useRef<number>();
  const refresh = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      api.sessions().then(setSessions).catch(() => undefined);
    }, 150);
  }, []);
  useEffect(() => {
    refresh();
    let closed = false;
    let ws: WebSocket | null = null;
    const connect = () => {
      ws = new WebSocket(wsUrl("/events"));
      ws.onmessage = refresh;
      ws.onclose = () => {
        if (!closed) window.setTimeout(connect, 1500);
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [refresh]);
  return [sessions, refresh];
}

/** Calls `fn` on Cmd/Ctrl + key. */
export function useHotkey(key: string, fn: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === key) {
        e.preventDefault();
        fn();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [key, fn]);
}
