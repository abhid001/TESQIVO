import type { ReactNode } from "react";

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

/** Alphanumeric / natural comparison used for all client-side sorting. */
export function naturalCompare(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return collator.compare(String(a), String(b));
}

export function sortBy<T>(rows: T[], key: keyof T | ((r: T) => unknown), dir: "asc" | "desc"): T[] {
  const get = typeof key === "function" ? key : (r: T) => r[key];
  const sorted = [...rows].sort((x, y) => naturalCompare(get(x), get(y)));
  return dir === "desc" ? sorted.reverse() : sorted;
}

export interface SortState {
  field: string;
  dir: "asc" | "desc";
}

export function SortHeader({
  label,
  field,
  sort,
  onSort,
  className,
}: {
  label: ReactNode;
  field: string;
  sort: SortState | null;
  onSort: (s: SortState) => void;
  className?: string;
}) {
  const active = sort?.field === field;
  const next: SortState = { field, dir: active && sort!.dir === "asc" ? "desc" : "asc" };
  return (
    <th className={className}>
      <button
        className="sort-th"
        onClick={() => onSort(next)}
        aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"}
      >
        {label}
        <span className="sort-caret">{active ? (sort!.dir === "asc" ? "▲" : "▼") : "↕"}</span>
      </button>
    </th>
  );
}

export function Pager({
  page,
  pages,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}) {
  if (total <= pageSize) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="pager">
      <span className="muted">
        {from}–{to} of {total}
      </span>
      <div className="inline-actions">
        <button className="sm" disabled={page <= 1} onClick={() => onPage(1)} aria-label="First page">
          «
        </button>
        <button className="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          ‹ Prev
        </button>
        <span className="muted">
          Page {page} / {pages}
        </span>
        <button className="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next ›
        </button>
        <button
          className="sm"
          disabled={page >= pages}
          onClick={() => onPage(pages)}
          aria-label="Last page"
        >
          »
        </button>
      </div>
    </div>
  );
}
