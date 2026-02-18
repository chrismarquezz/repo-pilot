import { useEffect, useState } from "react";
import { fetchRepos, uploadRepo, deleteRepo } from "./services/api";
import type { Repo } from "./services/api";
import ChatInterface from "./components/ChatInterface";
import RepoItem from "./components/RepoItem";

export default function App() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [indexing, setIndexing] = useState(false);
  const [indexError, setIndexError] = useState<string | null>(null);
  // Frontend-only display names (keyed by repo_id)
  const [displayNames, setDisplayNames] = useState<Record<string, string>>({});

  const loadRepos = async () => {
    try {
      const data = await fetchRepos();
      setRepos(data);
    } catch {
      // silently fail on initial load
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
    } catch {
      // ignore delete errors
    }
  };

  useEffect(() => {
    loadRepos();
  }, []);

  const handleIndex = async () => {
    if (!githubUrl.trim()) return;
    setIndexing(true);
    setIndexError(null);
    try {
      await uploadRepo(githubUrl.trim());
      setGithubUrl("");
      await loadRepos();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Indexing failed";
      setIndexError(msg);
    } finally {
      setIndexing(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#0d1117] text-gray-200">
      {/* Sidebar */}
      <aside className="w-80 flex-shrink-0 border-r border-gray-700/50 flex flex-col">
        {/* Index form */}
        <div className="p-4 border-b border-gray-700/50">
          <h1 className="text-lg font-semibold text-white mb-3">RepoPilot</h1>
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
              {indexing ? (
                <span className="flex items-center gap-1.5">
                  <svg
                    className="animate-spin h-3.5 w-3.5"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Indexing
                </span>
              ) : (
                "Index"
              )}
            </button>
          </div>
          {indexError && (
            <p className="mt-2 text-xs text-red-400">{indexError}</p>
          )}
        </div>

        {/* Repo list */}
        <div className="flex-1 overflow-y-auto">
          {repos.length === 0 ? (
            <p className="p-4 text-sm text-gray-500">
              No repos indexed yet. Add a GitHub URL above.
            </p>
          ) : (
            <ul>
              {repos.map((repo) => (
                <RepoItem
                  key={repo.repo_id}
                  repo={repo}
                  isSelected={selectedRepo?.repo_id === repo.repo_id}
                  displayName={displayNames[repo.repo_id] || repo.name}
                  onSelect={() => setSelectedRepo(repo)}
                  onRename={(name) => handleRename(repo.repo_id, name)}
                  onDelete={() => handleDelete(repo.repo_id)}
                />
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {selectedRepo ? (
          <ChatInterface repo={selectedRepo} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-500">
              <p className="text-lg">Select a repository to start asking questions</p>
              <p className="text-sm mt-1">
                Or index a new one from the sidebar
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
