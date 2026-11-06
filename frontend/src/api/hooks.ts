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

/** Which AI features to offer: the help assistant (any edition, when an API key is
 *  configured) and the test-case generator (Enterprise + licence "ai"). */
export function useAiStatus() {
  const q = useQuery({
    queryKey: ["assistant-status"],
    queryFn: () => http.get<{ assistant: boolean; generator: boolean }>("/assistant/status"),
    staleTime: 5 * 60_000,
    retry: false,
  });
  return { assistant: !!q.data?.assistant, generator: !!q.data?.generator, loaded: !q.isPending };
}
