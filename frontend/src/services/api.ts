import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: API_URL });

export interface Repo {
  repo_id: string;
  name: string;
  files: number;
  chunks: number;
  indexed_at: string;
}

export interface UploadResponse {
  repo_id: string;
  repo_name: string;
  files_processed: number;
  chunks_created: number;
  status: string;
}

export async function fetchRepos(): Promise<Repo[]> {
  const res = await api.get<{ repos: Repo[] }>("/api/repos");
  return res.data.repos;
}

export async function uploadRepo(githubUrl: string): Promise<UploadResponse> {
  const res = await api.post<UploadResponse>("/api/upload", {
    github_url: githubUrl,
  });
  return res.data;
}

export async function deleteRepo(repoId: string): Promise<void> {
  await api.delete(`/api/repos/${repoId}`);
}

export { API_URL };
