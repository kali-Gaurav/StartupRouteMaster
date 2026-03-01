interface RouteSkeletonProps {
  count: number;
}

export function RouteSkeleton({ count }: RouteSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className="bg-card rounded-2xl border-2 overflow-hidden border-primary shadow-soft animate-pulse"
          style={{ animationDelay: `${i * 0.1}s` }}
        >
          {/* Header */}
          <div className="p-5">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="h-8 w-24 bg-secondary rounded-full" />
                <div className="h-6 w-20 bg-secondary rounded-full" />
              </div>
              <div className="text-right">
                <div className="h-8 w-16 bg-secondary rounded mb-1" />
                <div className="h-4 w-20 bg-secondary rounded" />
              </div>
            </div>

            {/* Route info */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-4">
                <div className="h-6 w-16 bg-secondary rounded" />
                <div className="h-4 w-8 bg-secondary rounded" />
                <div className="h-6 w-16 bg-secondary rounded" />
              </div>
              <div className="text-right">
                <div className="h-5 w-12 bg-secondary rounded" />
              </div>
            </div>

            {/* Times */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="h-6 w-20 bg-secondary rounded mb-1" />
                <div className="h-4 w-16 bg-secondary rounded" />
              </div>
              <div className="text-center">
                <div className="h-4 w-12 bg-secondary rounded mb-1" />
                <div className="h-5 w-16 bg-secondary rounded" />
              </div>
              <div className="text-right">
                <div className="h-6 w-20 bg-secondary rounded mb-1" />
                <div className="h-4 w-16 bg-secondary rounded" />
              </div>
            </div>

            {/* Availability */}
            <div className="flex items-center justify-between">
              <div className="h-6 w-24 bg-secondary rounded" />
              <div className="h-8 w-20 bg-secondary rounded" />
            </div>
          </div>

          {/* Footer */}
          <div className="px-5 pb-5">
            <div className="h-10 w-full bg-secondary rounded-lg" />
          </div>
        </div>
      ))}
    </>
  );
}