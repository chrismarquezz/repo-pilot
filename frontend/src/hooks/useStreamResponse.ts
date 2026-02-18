import { useState, useCallback } from "react";
import { API_URL } from "../services/api";

export interface SourceChunk {
  filename: string;
  start_line: number;
  end_line: number;
  score: number;
}

interface StreamState {
  sources: SourceChunk[];
  streamedText: string;
  isStreaming: boolean;
  error: string | null;
}

export function useStreamResponse() {
  const [state, setState] = useState<StreamState>({
    sources: [],
    streamedText: "",
    isStreaming: false,
    error: null,
  });

  const query = useCallback(async (repoId: string, question: string) => {
    setState({ sources: [], streamedText: "", isStreaming: true, error: null });

    try {
      const res = await fetch(`${API_URL}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_id: repoId, question }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: err.detail || "Request failed",
        }));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        setState((s) => ({ ...s, isStreaming: false, error: "No response stream" }));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const json = line.slice(6).trim();
          if (!json) continue;

          try {
            const event = JSON.parse(json);

            if (event.type === "sources") {
              setState((s) => ({ ...s, sources: event.chunks }));
            } else if (event.type === "token") {
              setState((s) => ({
                ...s,
                streamedText: s.streamedText + event.content,
              }));
            } else if (event.type === "error") {
              setState((s) => ({ ...s, error: event.message }));
            }
            // "done" — we just let the loop finish
          } catch {
            // skip malformed JSON lines
          }
        }
      }
    } catch (err) {
      setState((s) => ({
        ...s,
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    } finally {
      setState((s) => ({ ...s, isStreaming: false }));
    }
  }, []);

  return { ...state, query };
}
