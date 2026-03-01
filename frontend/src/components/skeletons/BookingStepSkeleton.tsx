/** Skeleton for booking flow steps (e.g. checking payment status, availability). */
export function BookingStepSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-6 w-40 bg-secondary rounded" />
      <div className="rounded-xl border border-border bg-muted/20 p-6 min-h-[140px] flex flex-col items-center justify-center gap-3">
        <div className="h-10 w-10 rounded-full bg-secondary" />
        <div className="h-4 w-48 bg-secondary rounded" />
        <div className="h-3 w-24 bg-secondary rounded" />
      </div>
      <div className="flex gap-3 pt-2">
        <div className="h-10 w-20 bg-secondary rounded-lg" />
        <div className="h-10 flex-1 max-w-[200px] bg-secondary rounded-lg" />
      </div>
    </div>
  );
}
