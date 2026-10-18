import React from 'react';

interface PratyakshaLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showText?: boolean;
  className?: string;
}

export const PratyakshaLogo: React.FC<PratyakshaLogoProps> = ({
  size = 'md',
  showText = false,
  className = '',
}) => {
  const sizeMap = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-11 h-11',
    xl: 'w-14 h-14',
  };

  const emblem = (
    <div className={`relative flex items-center justify-center flex-shrink-0 ${sizeMap[size]} ${className}`}>
      <svg
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full drop-shadow-sm select-none"
      >
        <defs>
          <linearGradient id="logoBg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0A2540" />
            <stop offset="50%" stopColor="#075985" />
            <stop offset="100%" stopColor="#0D9488" />
          </linearGradient>
          <linearGradient id="lensRing" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="60%" stopColor="#2DD4BF" />
            <stop offset="100%" stopColor="#14B8A6" />
          </linearGradient>
          <filter id="logoGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Shield Container */}
        <rect
          x="6"
          y="6"
          width="108"
          height="108"
          rx="26"
          fill="url(#logoBg)"
          stroke="#38BDF8"
          strokeWidth="2.5"
          strokeOpacity="0.4"
        />

        {/* Concentric Radar Grid */}
        <circle cx="60" cy="60" r="42" stroke="#38BDF8" strokeWidth="1" strokeOpacity="0.2" strokeDasharray="3 3" />
        <circle cx="60" cy="60" r="30" stroke="#2DD4BF" strokeWidth="1" strokeOpacity="0.25" />

        {/* Viewfinder Reticles */}
        <path d="M 24 34 L 24 24 L 34 24" stroke="#38BDF8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M 96 34 L 96 24 L 86 24" stroke="#38BDF8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M 24 86 L 24 96 L 34 96" stroke="#38BDF8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M 96 86 L 96 96 L 86 96" stroke="#38BDF8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

        {/* Optical Lens Curve (Direct Perception / प्रत्यक्ष) */}
        <path
          d="M 26 60 C 37 42, 83 42, 94 60 C 83 78, 37 78, 26 60 Z"
          fill="#031726"
          fillOpacity="0.55"
          stroke="url(#lensRing)"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Inner Iris Housing */}
        <circle cx="60" cy="60" r="17" stroke="#38BDF8" strokeWidth="2" fill="#0A2540" fillOpacity="0.9" />
        <circle cx="60" cy="60" r="11" fill="url(#lensRing)" />

        {/* Central Core Pulse */}
        <circle cx="60" cy="60" r="5" fill="#FFFFFF" filter="url(#logoGlow)" />

        {/* Crosshair Target Marks */}
        <line x1="60" y1="36" x2="60" y2="40" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
        <line x1="60" y1="80" x2="60" y2="84" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
        <line x1="36" y1="60" x2="40" y2="60" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
        <line x1="80" y1="60" x2="84" y2="60" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />

        {/* Lens Light Reflection Specular */}
        <circle cx="56.5" cy="56.5" r="2" fill="#FFFFFF" fillOpacity="0.9" />
      </svg>
    </div>
  );

  if (!showText) {
    return emblem;
  }

  return (
    <div className="flex items-center gap-3">
      {emblem}
      <div>
        <span className="font-extrabold text-lg tracking-tight text-gov-900 dark:text-white block leading-tight">
          Pratyaksha
        </span>
        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium leading-tight mt-0.5">
          AI Skilling Centre Monitoring Unit
        </p>
      </div>
    </div>
  );
};
