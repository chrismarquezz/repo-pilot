import { useState, useRef, useEffect } from "react";
import type { Repo } from "../services/api";

interface Props {
  repo: Repo;
  isSelected: boolean;
  displayName: string;
  onSelect: () => void;
  onRename: (newName: string) => void;
  onDelete: () => void;
}

export default function RepoItem({
  repo,
  isSelected,
  displayName,
  onSelect,
  onRename,
  onDelete,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(displayName);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const commitRename = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== displayName) {
      onRename(trimmed);
    } else {
      setEditValue(displayName);
    }
    setEditing(false);
  };

  const handleDelete = () => {
    setMenuOpen(false);
    if (window.confirm(`Are you sure you want to delete ${displayName}?`)) {
      onDelete();
    }
  };

  return (
    <li className="relative group">
      <button
        onClick={onSelect}
        className={`w-full text-left px-4 py-3 border-b border-gray-700/30 hover:bg-[#161b22] transition-colors ${
          isSelected ? "bg-[#161b22] border-l-2 border-l-blue-500" : ""
        }`}
      >
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") {
                setEditValue(displayName);
                setEditing(false);
              }
              e.stopPropagation();
            }}
            onBlur={commitRename}
            onClick={(e) => e.stopPropagation()}
            className="w-full bg-[#0d1117] border border-blue-500 rounded px-1.5 py-0.5 text-sm text-white focus:outline-none"
          />
        ) : (
          <p className="text-sm font-medium text-white truncate pr-6">
            {displayName}
          </p>
        )}
        <p className="text-xs text-gray-500 mt-0.5">
          {repo.files} files &middot; {repo.chunks} chunks
        </p>
      </button>

      {/* Kebab menu button */}
      <div ref={menuRef}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen(!menuOpen);
          }}
          className="absolute right-2 top-3 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-700/50 transition-opacity"
        >
          <svg
            className="w-4 h-4 text-gray-400"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <circle cx="8" cy="3" r="1.5" />
            <circle cx="8" cy="8" r="1.5" />
            <circle cx="8" cy="13" r="1.5" />
          </svg>
        </button>

        {menuOpen && (
          <div className="absolute right-2 top-9 z-10 w-32 rounded-md bg-[#1c2128] border border-gray-700 shadow-lg py-1">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                setEditValue(displayName);
                setEditing(true);
              }}
              className="w-full text-left px-3 py-1.5 text-sm text-gray-300 hover:bg-[#161b22] transition-colors"
            >
              Rename
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDelete();
              }}
              className="w-full text-left px-3 py-1.5 text-sm text-red-400 hover:bg-[#161b22] transition-colors"
            >
              Delete
            </button>
          </div>
        )}
      </div>
    </li>
  );
}
