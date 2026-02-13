/** Skeleton for the ticket page (e.g. while loading ticket data). */
export function TicketSkeleton() {
  return (
    <div className="max-w-2xl mx-auto animate-pulse">
      <div className="bg-card rounded-2xl border-2 border-border overflow-hidden">
        <div className="h-16 bg-secondary/50 rounded-t-2xl" />
        <div className="p-6 space-y-4">
          <div className="h-5 w-32 bg-secondary rounded" />
          <div className="h-8 w-48 bg-secondary rounded" />
          <div className="h-4 w-full bg-secondary rounded" />
          <div className="pt-4 space-y-3">
            <div className="h-4 w-20 bg-secondary rounded" />
            <div className="h-6 w-56 bg-secondary rounded" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-16 bg-secondary rounded" />
            <div className="h-5 w-40 bg-secondary rounded" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-24 bg-secondary rounded" />
            <div className="h-5 w-36 bg-secondary rounded" />
          </div>
          <div className="pt-2">
            <div className="h-4 w-28 bg-secondary rounded mb-1" />
            <div className="h-7 w-24 bg-secondary rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}
