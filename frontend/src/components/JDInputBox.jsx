/**
 * JDInputBox — Textarea for job description with character counter.
 */

export default function JDInputBox({ value, onChange, maxLength = 3000 }) {
  const charCount = value?.length || 0;

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text">
        Job Description
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        rows={6}
        placeholder="Paste the job description here... Include role title, required skills, responsibilities, and qualifications."
        className="w-full resize-none rounded-xl border border-text-muted/20 bg-surface-light p-4
                   text-sm text-text placeholder-text-muted/50
                   transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30"
      />
      <div className="flex justify-between text-xs text-text-muted">
        <span>{charCount < 10 ? 'Minimum 10 characters' : ''}</span>
        <span>{charCount} / {maxLength}</span>
      </div>
    </div>
  );
}
