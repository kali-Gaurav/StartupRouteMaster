import { Card, CardContent } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

export const TrainCardSkeleton = () => (
  <Card className="shadow-md overflow-hidden animate-pulse">
    <CardContent className="p-0">
      <div className="bg-slate-100 p-4 border-b space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="w-9 h-9 rounded-lg" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-16" />
            </div>
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-8 w-8 rounded-md" />
            <Skeleton className="h-8 w-20 rounded-md" />
          </div>
        </div>
      </div>
      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-12" />
          <Skeleton className="h-1 flex-1 mx-4" />
          <Skeleton className="h-6 w-12" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Skeleton className="h-12 rounded-lg" />
          <Skeleton className="h-12 rounded-lg" />
          <Skeleton className="h-12 rounded-lg" />
        </div>
      </div>
    </CardContent>
  </Card>
);
