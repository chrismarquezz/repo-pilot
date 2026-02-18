import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import type { Repo } from "../services/api";
import { useStreamResponse } from "../hooks/useStreamResponse";
import type { SourceChunk } from "../hooks/useStreamResponse";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
}

interface Props {
  repo: Repo;
}

export default function ChatInterface({ repo }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sources, streamedText, isStreaming, error, query } =
    useStreamResponse();

  // Auto-scroll on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamedText]);

  // When streaming finishes, commit the assistant message
  useEffect(() => {
    if (!isStreaming && streamedText) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: streamedText, sources },
      ]);
    }
    // Only trigger when streaming stops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming]);

  // Reset messages when switching repos
  useEffect(() => {
    setMessages([]);
  }, [repo.repo_id]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || isStreaming) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    await query(repo.repo_id, q);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-700/50 flex-shrink-0">
        <h2 className="text-sm font-semibold text-white">{repo.name}</h2>
        <p className="text-xs text-gray-500">
          {repo.files} files &middot; {repo.chunks} chunks
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && !isStreaming && (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            Ask a question about this repository
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {/* In-progress streaming message */}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%]">
              {sources.length > 0 && <SourcesList sources={sources} />}
              <div className="rounded-lg bg-[#161b22] border border-gray-700/50 px-4 py-3 text-sm">
                {streamedText ? (
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{streamedText}</ReactMarkdown>
                  </div>
                ) : (
                  <span className="text-gray-500 animate-pulse">
                    Thinking...
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {error && (
          <p className="text-sm text-red-400 text-center">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-3 border-t border-gray-700/50 flex-shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about this codebase..."
            disabled={isStreaming}
            className="flex-1 rounded-md bg-[#161b22] border border-gray-700 px-4 py-2 text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="rounded-md bg-blue-600 hover:bg-blue-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] ${isUser ? "" : ""}`}>
        {message.sources && message.sources.length > 0 && (
          <SourcesList sources={message.sources} />
        )}
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            isUser
              ? "bg-blue-600 text-white"
              : "bg-[#161b22] border border-gray-700/50 text-gray-200"
          }`}
        >
          {isUser ? (
            message.content
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SourcesList({ sources }: { sources: SourceChunk[] }) {
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {sources.map((s, i) => (
        <span
          key={i}
          className="inline-block rounded bg-[#1c2128] border border-gray-700/50 px-2 py-0.5 text-xs text-gray-400"
        >
          {s.filename}:{s.start_line}-{s.end_line}
        </span>
      ))}
    </div>
  );
}
