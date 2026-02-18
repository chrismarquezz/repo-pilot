import { useEffect, useRef, useState } from "react";
import { Toaster } from "react-hot-toast";
import toast from "react-hot-toast";
import { fetchRepos, uploadRepo, deleteRepo } from "./services/api";
import type { Repo } from "./services/api";
import ChatInterface from "./components/ChatInterface";
import type { Message } from "./components/ChatInterface";
import { AnimatePresence, motion } from "framer-motion";
import RepoItem from "./components/RepoItem";

const INDEXING_STEPS = [
  { key: "cloning", message: "Cloning repository..." },
  { key: "chunking", message: "Chunking code files..." },
  { key: "embedding", message: "Generating embeddings..." },
  { key: "storing", message: "Storing vectors..." },
];

export default function App() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [indexing, setIndexing] = useState(false);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [activeStepIndex, setActiveStepIndex] = useState(-1);
  const [displayNames, setDisplayNames] = useState<Record<string, string>>({});
  const [chatHistory, setChatHistory] = useState<Record<string, Message[]>>({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRepos = async () => {
    try {
      const data = await fetchRepos();
      setRepos(data);
    } catch {
      toast.error("Failed to load repositories");
    }
  };

  const handleRename = (repoId: string, newName: string) => {
    setDisplayNames((prev) => ({ ...prev, [repoId]: newName }));
  };

  const handleDelete = async (repoId: string) => {
    try {
      await deleteRepo(repoId);
      setRepos((prev) => prev.filter((r) => r.repo_id !== repoId));
      if (selectedRepo?.repo_id === repoId) {
        setSelectedRepo(null);
      }
      setDisplayNames((prev) => {
        const next = { ...prev };
        delete next[repoId];
        return next;
      });
      setChatHistory((prev) => {
        const next = { ...prev };
        delete next[repoId];
        return next;
      });
      toast.success("Repository deleted");
    } catch {
      toast.error("Failed to delete repository");
    }
  };

  useEffect(() => {
    loadRepos();
  }, []);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    };
  }, []);

  const startStepAnimation = () => {
    setActiveStepIndex(0);
    let step = 0;
    stepTimerRef.current = setInterval(() => {
      step += 1;
      if (step < INDEXING_STEPS.length) {
        setActiveStepIndex(step);
      } else {
        // Stay on last step — the actual completion will clear it
        if (stepTimerRef.current) clearInterval(stepTimerRef.current);
        stepTimerRef.current = null;
      }
    }, 3000);
  };

  const stopStepAnimation = () => {
    if (stepTimerRef.current) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
    // Mark all steps done briefly, then clear
    setActiveStepIndex(INDEXING_STEPS.length);
    setTimeout(() => setActiveStepIndex(-1), 1500);
  };

  const handleIndex = async () => {
    if (!githubUrl.trim()) return;
    setIndexing(true);
    setIndexError(null);
    startStepAnimation();

    try {
      await uploadRepo(githubUrl.trim());
      setGithubUrl("");
      await loadRepos();
      toast.success("Repository indexed successfully");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Indexing failed";
      setIndexError(msg);
      toast.error(msg.includes("429") ? "Rate limit exceeded. Try again later." : msg);
    } finally {
      setIndexing(false);
      stopStepAnimation();
    }
  };

  const handleSelectRepo = (repo: Repo) => {
    setSelectedRepo(repo);
    setSidebarOpen(false);
  };

  // Dynamic page title
  useEffect(() => {
    if (selectedRepo) {
      const name = displayNames[selectedRepo.repo_id] || selectedRepo.name;
      document.title = `RepoPilot — ${name}`;
    } else {
      document.title = "RepoPilot — Chat with any codebase";
    }
  }, [selectedRepo, displayNames]);

  return (
    <div className="flex h-screen bg-[#0d1117] text-gray-200">
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: "#1c2128",
            color: "#e6edf3",
            border: "1px solid rgba(55, 65, 81, 0.5)",
            fontSize: "0.875rem",
          },
          success: {
            iconTheme: { primary: "#22c55e", secondary: "#1c2128" },
          },
          error: {
            iconTheme: { primary: "#ef4444", secondary: "#1c2128" },
          },
        }}
      />
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-80 flex-shrink-0 border-r border-gray-700/50 flex flex-col bg-[#0d1117] transition-transform duration-200 md:static md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Index form */}
        <div className="p-4 border-b border-gray-700/50">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-lg font-semibold text-white">RepoPilot</h1>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1 rounded hover:bg-gray-700/50 md:hidden"
            >
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleIndex()}
              placeholder="https://github.com/user/repo"
              disabled={indexing}
              className="flex-1 min-w-0 rounded-md bg-[#161b22] border border-gray-700 px-3 py-1.5 text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleIndex}
              disabled={indexing || !githubUrl.trim()}
              className="rounded-md bg-green-600 hover:bg-green-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
            >
              Index
            </button>
          </div>
          {indexError && (
            <p className="mt-2 text-xs text-red-400">{indexError}</p>
          )}
        </div>

        {/* Indexing progress steps */}
        {activeStepIndex >= 0 && (
          <div className="px-4 py-3 border-b border-gray-700/50 bg-[#161b22]/50 space-y-2">
            {INDEXING_STEPS.map((s, i) => {
              const isDone = i < activeStepIndex;
              const isActive = i === activeStepIndex;
              const isPending = i > activeStepIndex;

              if (isPending) return null;

              return (
                <div key={s.key} className="flex items-center gap-2.5">
                  {isDone ? (
                    <svg className="w-4 h-4 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : isActive ? (
                    <svg className="animate-spin h-4 w-4 text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : null}
                  <span className={`text-xs ${isDone ? "text-gray-500" : "text-gray-300"}`}>
                    {s.message}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Repo list */}
        <div className="flex-1 overflow-y-auto">
          {repos.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-4 text-center">
              <svg className="w-10 h-10 mb-3 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <p className="text-sm text-gray-500">No repositories indexed yet</p>
              <p className="text-xs text-gray-600 mt-1">Add a GitHub URL above to get started</p>
            </div>
          ) : (
            <ul>
              <AnimatePresence initial={false}>
                {repos.map((repo) => (
                  <motion.div
                    key={repo.repo_id}
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, height: 0, overflow: "hidden" }}
                    transition={{ duration: 0.25 }}
                  >
                    <RepoItem
                      repo={repo}
                      isSelected={selectedRepo?.repo_id === repo.repo_id}
                      displayName={displayNames[repo.repo_id] || repo.name}
                      onSelect={() => handleSelectRepo(repo)}
                      onRename={(name) => handleRename(repo.repo_id, name)}
                      onDelete={() => handleDelete(repo.repo_id)}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </ul>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Mobile header with hamburger */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-700/50 md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded hover:bg-gray-700/50"
          >
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-sm font-medium text-white truncate">
            {selectedRepo ? (displayNames[selectedRepo.repo_id] || selectedRepo.name) : "RepoPilot"}
          </span>
        </div>

        {selectedRepo ? (
          <ChatInterface
            repo={selectedRepo}
            displayName={displayNames[selectedRepo.repo_id] || selectedRepo.name}
            messages={chatHistory[selectedRepo.repo_id] || []}
            onMessagesChange={(msgs) =>
              setChatHistory((prev) => ({ ...prev, [selectedRepo.repo_id]: msgs }))
            }
          />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-500">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={0.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-2.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <p className="text-lg">Select a repository to start chatting</p>
              <p className="text-sm mt-1 text-gray-600">
                Or index a new one from the sidebar
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
