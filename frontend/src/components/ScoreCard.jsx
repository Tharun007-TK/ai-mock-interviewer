/**
 * ScoreCard — Displays a single rubric score with visual bar.
 */

export default function ScoreCard({ label, score, maxScore = 10 }) {
  const percentage = maxScore > 0 ? (score / maxScore) * 100 : 0;

  const getColor = () => {
    if (percentage >= 70) return 'bg-success text-success';
    if (percentage >= 40) return 'bg-warning text-warning';
    return 'bg-danger text-danger';
  };

  const barColor = getColor().split(' ')[0];
  const textColor = getColor().split(' ')[1];

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-text-muted">{label}</span>
        <span className={`text-sm font-semibold ${textColor}`}>
          {score.toFixed(1)}/{maxScore}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-light">
        <div
          className={`h-full rounded-full ${barColor} transition-all duration-700 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
