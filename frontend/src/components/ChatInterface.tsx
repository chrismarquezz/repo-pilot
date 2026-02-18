import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
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
  displayName: string;
}

export default function ChatInterface({ repo, displayName }: Props) {
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

  const handleClearChat = () => {
    if (messages.length === 0) return;
    if (window.confirm("Clear all messages for this chat?")) {
      setMessages([]);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-700/50 flex-shrink-0 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">{displayName}</h2>
          <p className="text-xs text-gray-500">
            {repo.files} files &middot; {repo.chunks} chunks
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleClearChat}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-gray-400 hover:text-gray-200 hover:bg-[#1c2128] transition-colors"
            title="Clear chat"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <svg className="w-12 h-12 mb-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-sm">Ask anything about this codebase</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {/* In-progress streaming message */}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%]">
              {sources.length > 0 && <SourceCards sources={sources} />}
              <div className="rounded-lg bg-[#161b22] border border-gray-700/50 px-4 py-3 text-sm">
                {streamedText ? (
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown components={markdownComponents}>{streamedText}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 py-1">
                    <span className="typing-dot" />
                    <span className="typing-dot" style={{ animationDelay: "0.15s" }} />
                    <span className="typing-dot" style={{ animationDelay: "0.3s" }} />
                  </div>
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
            {isStreaming ? (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              "Send"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Markdown code block components ---------- */

const markdownComponents = {
  code({ className, children, ...props }: React.ComponentProps<"code"> & { inline?: boolean }) {
    const match = /language-(\w+)/.exec(className || "");
    const codeString = String(children).replace(/\n$/, "");

    // Block code (has language class or contains newlines)
    if (match || codeString.includes("\n")) {
      return (
        <SyntaxHighlighter
          style={oneDark}
          language={match?.[1] || "text"}
          PreTag="div"
          customStyle={{
            margin: 0,
            borderRadius: "0.375rem",
            fontSize: "0.8125rem",
          }}
        >
          {codeString}
        </SyntaxHighlighter>
      );
    }

    // Inline code
    return (
      <code
        className="rounded bg-[#1c2128] px-1.5 py-0.5 text-[0.8125rem] font-mono text-gray-300"
        {...props}
      >
        {children}
      </code>
    );
  },
};

/* ---------- Message bubble ---------- */

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[80%]">
        {message.sources && message.sources.length > 0 && (
          <SourceCards sources={message.sources} />
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
              <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- Collapsible source cards ---------- */

function SourceCards({ sources }: { sources: SourceChunk[] }) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const toggle = (i: number) => {
    setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));
  };

  return (
    <div className="mb-2 space-y-1">
      <p className="text-[0.6875rem] uppercase tracking-wider text-gray-500 mb-1">
        Sources
      </p>
      {sources.map((s, i) => (
        <div
          key={i}
          className="rounded-md border border-gray-700/40 bg-[#1c2128]/60 overflow-hidden"
        >
          <button
            onClick={() => toggle(i)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-[#1c2128] transition-colors"
          >
            <svg
              className={`w-3 h-3 text-gray-500 flex-shrink-0 transition-transform ${
                expanded[i] ? "rotate-90" : ""
              }`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-xs text-gray-400 font-mono truncate">
              {s.filename}
            </span>
            <span className="text-[0.6875rem] text-gray-600 flex-shrink-0">
              L{s.start_line}-{s.end_line}
            </span>
          </button>
          {expanded[i] && s.content && (
            <div className="border-t border-gray-700/30 max-h-60 overflow-auto">
              <SyntaxHighlighter
                style={oneDark}
                language={detectLanguage(s.filename)}
                showLineNumbers
                startingLineNumber={s.start_line}
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  fontSize: "0.75rem",
                  background: "transparent",
                }}
              >
                {s.content}
              </SyntaxHighlighter>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function detectLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    py: "python",
    js: "javascript",
    ts: "typescript",
    tsx: "tsx",
    jsx: "jsx",
    java: "java",
    go: "go",
    rs: "rust",
    cpp: "cpp",
    c: "c",
    rb: "ruby",
    sh: "bash",
    yml: "yaml",
    yaml: "yaml",
    json: "json",
    md: "markdown",
    css: "css",
    html: "html",
    sql: "sql",
  };
  return map[ext] || "text";
}
