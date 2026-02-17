/**
 * ProgressTracker — Shows interview progress (question X of Y).
 */

export default function ProgressTracker({ current, total }) {
  const progress = total > 0 ? (current / total) * 100 : 0;

  return (
    <div className="w-full space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-muted">Progress</span>
        <span className="font-medium text-text">
          Question {current} of {total}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-light">
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
