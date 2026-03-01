/** Skeleton for booking/ticket history lists. */
export function HistorySkeleton({ count = 5 }: { count?: number }) {
  return (
    <ul className="space-y-4 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="rounded-xl border border-border p-4 bg-card">
          <div className="flex justify-between gap-2">
            <div className="h-5 w-40 bg-secondary rounded" />
            <div className="h-4 w-24 bg-secondary rounded" />
          </div>
          <div className="h-4 w-28 bg-secondary rounded mt-3" />
        </li>
      ))}
    </ul>
  );
}
