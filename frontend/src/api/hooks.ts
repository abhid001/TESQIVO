import { useQuery } from "@tanstack/react-query";
import { http } from "./client";
import type { Project } from "./types";

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: () => http.get<Project[]>("/projects") });
}

/** Resolve the readable project key in the URL to the project record. */
export function useProject(projectKey: string | undefined) {
  const q = useProjects();
  const project = q.data?.find((p) => p.key === projectKey);
  return { ...q, project };
}

export function useList<T>(key: unknown[], path: string, enabled = true) {
  return useQuery({ queryKey: key, queryFn: () => http.get<T>(path), enabled });
}
