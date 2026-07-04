/**
 * LoadingSkeleton — 骨架屏
 * card: 高亮列表用 / grid: 视图列表用 / graph: 图谱加载用
 */

function Bar({ className = '' }: { className?: string }) {
  return <div className={`bg-muted animate-pulse rounded ${className}`} />;
}

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="border rounded-lg p-4 flex flex-col gap-3">
          <Bar className="h-4 w-3/4" />
          <Bar className="h-3 w-1/2" />
          <div className="flex justify-between mt-2">
            <Bar className="h-3 w-32" />
            <Bar className="h-3 w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function GridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="border rounded-lg p-4 flex flex-col gap-2">
          <Bar className="h-5 w-2/3" />
          <Bar className="h-3 w-full" />
          <Bar className="h-3 w-1/3 mt-2" />
        </div>
      ))}
    </div>
  );
}

export function GraphSkeleton() {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="grid grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="w-16 h-16 rounded-full bg-muted animate-pulse" />
          ))}
        </div>
        <p className="text-sm text-muted-foreground mt-4">加载图谱中…</p>
      </div>
    </div>
  );
}
