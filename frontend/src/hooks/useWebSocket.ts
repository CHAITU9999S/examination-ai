
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type WebSocketStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

interface UseWebSocketOptions {
  url: string | null;
  enabled?: boolean;
  reconnect?: boolean;
  reconnectIntervalMs?: number;
  maxReconnectAttempts?: number;
  heartbeatIntervalMs?: number;
  heartbeatPayload?: () => Record<string, unknown>;
  onMessage?: (message: unknown) => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  status: WebSocketStatus;
  lastMessage: unknown;
  sendMessage: (message: unknown) => boolean;
  connect: () => void;
  disconnect: () => void;
  isConnected: boolean;
  reconnectAttempts: number;
}

export function useWebSocket({
  url,
  enabled = true,
  reconnect = true,
  reconnectIntervalMs = 3000,
  maxReconnectAttempts = 5,
  heartbeatIntervalMs = 10000,
  heartbeatPayload,
  onMessage,
  onError,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [status, setStatus] = useState<WebSocketStatus>("disconnected");
  const [lastMessage, setLastMessage] = useState<unknown>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const manuallyClosedRef = useRef(false);

  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const heartbeatPayloadRef = useRef(heartbeatPayload);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    heartbeatPayloadRef.current = heartbeatPayload;
  }, [heartbeatPayload]);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (heartbeatTimerRef.current !== null) {
      window.clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    manuallyClosedRef.current = true;
    clearTimers();

    const socket = socketRef.current;
    socketRef.current = null;

    if (
      socket &&
      socket.readyState !== WebSocket.CLOSED &&
      socket.readyState !== WebSocket.CLOSING
    ) {
      socket.close(1000, "Client disconnected");
    }

    setStatus("disconnected");
  }, [clearTimers]);

  const connect = useCallback(() => {
    if (!enabled || !url) {
      setStatus("disconnected");
      return;
    }

    const currentSocket = socketRef.current;

    if (
      currentSocket &&
      (currentSocket.readyState === WebSocket.OPEN ||
        currentSocket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    manuallyClosedRef.current = false;
    clearTimers();
    setStatus(
      reconnectAttemptsRef.current > 0 ? "reconnecting" : "connecting"
    );

    let socket: WebSocket;

    try {
      socket = new WebSocket(url);
    } catch {
      setStatus("error");
      return;
    }

    socketRef.current = socket;

    socket.onopen = () => {
      if (socketRef.current !== socket) {
        return;
      }

      reconnectAttemptsRef.current = 0;
      setReconnectAttempts(0);
      setStatus("connected");

      if (heartbeatIntervalMs > 0) {
        heartbeatTimerRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            let signals: Record<string, unknown> = {};
            try {
              signals = heartbeatPayloadRef.current?.() ?? {};
            } catch {
              // A failed client-side summary must not stop the heartbeat.
            }
            socket.send(JSON.stringify({ type: "heartbeat", signals }));
          }
        }, heartbeatIntervalMs);
      }
    };

    socket.onmessage = (event) => {
      if (socketRef.current !== socket) {
        return;
      }

      let message: unknown = event.data;

      try {
        message = JSON.parse(event.data);
      } catch {
        // Preserve non-JSON messages as received.
      }

      setLastMessage(message);
      onMessageRef.current?.(message);
    };

    socket.onerror = (event) => {
      if (socketRef.current !== socket) {
        return;
      }

      setStatus("error");
      onErrorRef.current?.(event);
    };

    socket.onclose = () => {
      if (socketRef.current !== socket) {
        return;
      }

      socketRef.current = null;
      clearTimers();

      if (
        manuallyClosedRef.current ||
        !enabled ||
        !reconnect ||
        reconnectAttemptsRef.current >= maxReconnectAttempts
      ) {
        setStatus("disconnected");
        return;
      }

      reconnectAttemptsRef.current += 1;
      setReconnectAttempts(reconnectAttemptsRef.current);
      setStatus("reconnecting");

      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, reconnectIntervalMs);
    };
  }, [
    enabled,
    url,
    reconnect,
    reconnectIntervalMs,
    maxReconnectAttempts,
    heartbeatIntervalMs,
    clearTimers,
  ]);

  const sendMessage = useCallback((message: unknown): boolean => {
    const socket = socketRef.current;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false;
    }

    try {
      socket.send(
        typeof message === "string"
          ? message
          : JSON.stringify(message)
      );

      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    if (enabled && url) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      manuallyClosedRef.current = true;
      clearTimers();

      const socket = socketRef.current;
      socketRef.current = null;

      if (
        socket &&
        socket.readyState !== WebSocket.CLOSED &&
        socket.readyState !== WebSocket.CLOSING
      ) {
        socket.close(1000, "Component cleanup");
      }
    };
  }, [enabled, url, connect, disconnect, clearTimers]);

  return {
    status,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
    isConnected: status === "connected",
    reconnectAttempts,
  };
}
