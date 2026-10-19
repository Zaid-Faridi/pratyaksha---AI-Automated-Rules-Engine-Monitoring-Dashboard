import React from 'react';
import { LucideIcon } from 'lucide-react';

interface ScoreRingProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  icon?: LucideIcon;
  className?: string;
}

export const ScoreRing: React.FC<ScoreRingProps> = ({
  score,
  size = 'md',
  showLabel = true,
  icon: Icon,
  className = '',
}) => {
  const clampedScore = Math.max(0, Math.min(100, score));

  // Determine color scheme: green 85+, amber 70-84, red below 70
  let strokeColor = '#10B981'; // Green
  let bgStroke = 'rgba(16, 185, 129, 0.15)';
  let textColor = 'text-emerald-600 dark:text-emerald-400';

  if (clampedScore < 70) {
    strokeColor = '#EF4444'; // Red below 70
    bgStroke = 'rgba(239, 68, 68, 0.15)';
    textColor = 'text-rose-600 dark:text-rose-400';
  } else if (clampedScore < 85) {
    strokeColor = '#F59E0B'; // Amber 70-84
    bgStroke = 'rgba(245, 158, 11, 0.15)';
    textColor = 'text-amber-600 dark:text-amber-400';
  }

  const dimensions = {
    sm: { diameter: 46, strokeWidth: 3.5, textSize: 'text-xs font-bold', iconSize: 16 },
    md: { diameter: 68, strokeWidth: 5.5, textSize: 'text-sm font-bold', iconSize: 22 },
    lg: { diameter: 108, strokeWidth: 8, textSize: 'text-2xl font-extrabold', iconSize: 32 },
  }[size];

  const radius = (dimensions.diameter - dimensions.strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clampedScore / 100) * circumference;

  return (
    <div
      className={`inline-flex items-center justify-center relative flex-shrink-0 ${className}`}
      aria-label={`Compliance Score: ${clampedScore.toFixed(1)} out of 100`}
    >
      <svg
        width={dimensions.diameter}
        height={dimensions.diameter}
        className="transform -rotate-90 flex-shrink-0"
      >
        {/* Background track */}
        <circle
          cx={dimensions.diameter / 2}
          cy={dimensions.diameter / 2}
          r={radius}
          stroke={bgStroke}
          strokeWidth={dimensions.strokeWidth}
          fill="none"
        />
        {/* Progress indicator */}
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
      {showLabel ? (
        <span className={`absolute ${dimensions.textSize} ${textColor}`}>
          {clampedScore.toFixed(0)}%
        </span>
      ) : Icon ? (
        <Icon className={`absolute ${textColor}`} style={{ width: dimensions.iconSize, height: dimensions.iconSize }} aria-hidden="true" />
      ) : null}
    </div>
  );
};
