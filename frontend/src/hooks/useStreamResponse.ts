import { useState, useCallback, useRef } from "react";
import { API_URL } from "../services/api";

export interface SourceChunk {
  filename: string;
  start_line: number;
  end_line: number;
  content: string;
  score: number;
}

export interface StreamResult {
  text: string;
  sources: SourceChunk[];
}

export function useStreamResponse() {
  const [streamedText, setStreamedText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sources stored in a ref, NOT React state — avoids batching issues entirely
  const sourcesRef = useRef<SourceChunk[]>([]);

  const query = useCallback(async (repoId: string, question: string): Promise<StreamResult | null> => {
    setStreamedText("");
    setIsStreaming(true);
    setError(null);
    sourcesRef.current = [];

    // Plain JS variables — guaranteed available when the stream ends
    let finalSources: SourceChunk[] = [];
    let finalText = "";

    try {
      const res = await fetch(`${API_URL}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_id: repoId, question }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        setIsStreaming(false);
        setError(err.detail || "Request failed");
        return null;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        setIsStreaming(false);
        setError("No response stream");
        return null;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);

            if (event.type === "sources") {
              finalSources = event.chunks;
              sourcesRef.current = event.chunks;
            } else if (event.type === "token") {
              finalText += event.content;
              setStreamedText((prev) => prev + event.content);
            } else if (event.type === "error") {
              setError(event.message);
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }

      return { text: finalText, sources: finalSources };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      return null;
    } finally {
      setIsStreaming(false);
    }
  }, []);

  return { sourcesRef, streamedText, isStreaming, error, query };
}
