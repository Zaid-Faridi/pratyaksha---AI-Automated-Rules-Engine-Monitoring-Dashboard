import React from 'react';

interface ScoreRingProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export const ScoreRing: React.FC<ScoreRingProps> = ({
  score,
  size = 'md',
  showLabel = true,
  className = '',
}) => {
  const clampedScore = Math.max(0, Math.min(100, score));

  // Determine color scheme
  let strokeColor = '#10B981'; // Emerald
  let bgStroke = 'rgba(16, 185, 129, 0.15)';
  let textColor = 'text-emerald-600 dark:text-emerald-400';

  if (clampedScore < 65) {
    strokeColor = '#EF4444'; // Rose
    bgStroke = 'rgba(239, 68, 68, 0.15)';
    textColor = 'text-rose-600 dark:text-rose-400';
  } else if (clampedScore < 85) {
    strokeColor = '#F59E0B'; // Amber
    bgStroke = 'rgba(245, 158, 11, 0.15)';
    textColor = 'text-amber-600 dark:text-amber-400';
  }

  const dimensions = {
    sm: { diameter: 44, strokeWidth: 4, textSize: 'text-xs font-bold' },
    md: { diameter: 72, strokeWidth: 6, textSize: 'text-base font-bold' },
    lg: { diameter: 108, strokeWidth: 8, textSize: 'text-2xl font-extrabold' },
  }[size];

  const radius = (dimensions.diameter - dimensions.strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clampedScore / 100) * circumference;

  return (
    <div
      className={`inline-flex items-center justify-center relative ${className}`}
      aria-label={`Compliance Score: ${clampedScore.toFixed(1)} out of 100`}
    >
      <svg
        width={dimensions.diameter}
        height={dimensions.diameter}
        className="transform -rotate-90"
      >
        {/* Background circle */}
        <circle
          cx={dimensions.diameter / 2}
          cy={dimensions.diameter / 2}
          r={radius}
          stroke={bgStroke}
          strokeWidth={dimensions.strokeWidth}
          fill="none"
        />
        {/* Progress circle */}
        <circle
          cx={dimensions.diameter / 2}
          cy={dimensions.diameter / 2}
          r={radius}
          stroke={strokeColor}
          strokeWidth={dimensions.strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          fill="none"
          className="transition-all duration-700 ease-out"
        />
      </svg>
      {showLabel && (
        <span className={`absolute ${dimensions.textSize} ${textColor}`}>
          {clampedScore.toFixed(0)}%
        </span>
      )}
    </div>
  );
};
