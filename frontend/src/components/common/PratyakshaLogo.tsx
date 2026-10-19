import React from 'react';

interface PratyakshaLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  showText?: boolean;
  animated?: boolean;
  className?: string;
}

export const PratyakshaLogo: React.FC<PratyakshaLogoProps> = ({
  size = 'md',
  showText = false,
  animated = true,
  className = '',
}) => {
  const sizeMap = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-11 h-11',
    xl: 'w-14 h-14',
    '2xl': 'w-20 h-20',
  };

  const emblem = (
    <div
      className={`relative flex items-center justify-center flex-shrink-0 ${sizeMap[size]} ${className}`}
      role="img"
      aria-label="Pratyaksha AI Perception Emblem"
    >
      <svg
        viewBox="0 0 128 128"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full drop-shadow-md select-none transition-transform duration-300 group-hover:scale-105"
      >
        <defs>
          {/* Deep Space Cyber Shield Background */}
          <linearGradient id="pkShieldBg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#030A16" />
            <stop offset="45%" stopColor="#061B2E" />
            <stop offset="85%" stopColor="#082A3E" />
            <stop offset="100%" stopColor="#0B3848" />
          </linearGradient>

          {/* Electric Cyan to Mint Teal Gradient */}
          <linearGradient id="pkCyanTeal" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="50%" stopColor="#22D3EE" />
            <stop offset="100%" stopColor="#14B8A6" />
          </linearGradient>

          {/* Saffron & Amber Sovereign Tech Accent */}
          <linearGradient id="pkSaffronGold" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FF9933" />
            <stop offset="100%" stopColor="#F59E0B" />
          </linearGradient>

          {/* Aperture Shutter Gradient */}
          <linearGradient id="pkIrisBlade" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0F2840" />
            <stop offset="100%" stopColor="#071929" />
          </linearGradient>

          {/* Core Lens High-Energy Glow */}
          <filter id="pkCoreGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          {/* Outer Halo Glow */}
          <filter id="pkNeonHalo" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* 1. Outer Cybernetic Shield with Chamfered Corners */}
        <rect
          x="6"
          y="6"
          width="116"
          height="116"
          rx="26"
          fill="url(#pkShieldBg)"
          stroke="url(#pkCyanTeal)"
          strokeWidth="2.2"
          strokeOpacity="0.75"
        />

        {/* 2. Micro Circuit Matrix Grid Lines */}
        <path
          d="M 6 36 L 18 36 L 24 30 M 122 36 L 110 36 L 104 30 M 6 92 L 18 92 L 24 98 M 122 92 L 110 92 L 104 98"
          stroke="#38BDF8"
          strokeWidth="1.2"
          strokeOpacity="0.3"
          strokeLinecap="round"
        />

        {/* 3. Concentric Spatial Radar Coordinates */}
        <circle
          cx="64"
          cy="64"
          r="48"
          stroke="#38BDF8"
          strokeWidth="1"
          strokeOpacity="0.15"
          strokeDasharray="4 4"
        />
        <circle
          cx="64"
          cy="64"
          r="36"
          stroke="#22D3EE"
          strokeWidth="1.2"
          strokeOpacity="0.25"
        />

        {/* 4. High-Tech Precision Viewfinder Corner Brackets */}
        <path
          d="M 22 36 L 22 22 L 36 22"
          stroke="#38BDF8"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M 106 36 L 106 22 L 92 22"
          stroke="#38BDF8"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M 22 92 L 22 106 L 36 106"
          stroke="#38BDF8"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M 106 92 L 106 106 L 92 106"
          stroke="#38BDF8"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* 5. Pratyaksha Optical Perception Eye (प्रत्यक्ष त्रिनेत्र Contour) */}
        <path
          d="M 20 64 C 36 38, 92 38, 108 64 C 92 90, 36 90, 20 64 Z"
          fill="#020B16"
          fillOpacity="0.75"
          stroke="url(#pkCyanTeal)"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#pkNeonHalo)"
        />

        {/* 6. Mechanical Camera Shutter / Aperture Blades (Hex-Iris) */}
        <g stroke="#38BDF8" strokeWidth="1" strokeOpacity="0.45">
          <circle cx="64" cy="64" r="22" fill="url(#pkIrisBlade)" stroke="url(#pkCyanTeal)" strokeWidth="1.8" />
          <line x1="64" y1="42" x2="52" y2="58" />
          <line x1="84" y1="52" x2="68" y2="60" />
          <line x1="82" y1="76" x2="68" y2="72" />
          <line x1="64" y1="86" x2="76" y2="70" />
          <line x1="44" y1="76" x2="60" y2="68" />
          <line x1="46" y1="52" x2="60" y2="56" />
        </g>

        {/* 7. Inner Quantum Perception Sensor (Core Iris) */}
        <circle cx="64" cy="64" r="13" fill="#031221" stroke="#38BDF8" strokeWidth="1.8" />
        <circle cx="64" cy="64" r="9" fill="url(#pkCyanTeal)" />

        {/* 8. Central Radiant AI Pulse Core */}
        <circle
          cx="64"
          cy="64"
          r="4.5"
          fill="#FFFFFF"
          filter="url(#pkCoreGlow)"
          className={animated ? 'animate-pulse' : ''}
        />

        {/* 9. Crosshair Laser Targeting Marks */}
        <line x1="64" y1="18" x2="64" y2="24" stroke="url(#pkSaffronGold)" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="64" y1="104" x2="64" y2="110" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
        <line x1="18" y1="64" x2="24" y2="64" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
        <line x1="104" y1="64" x2="110" y2="64" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />

        {/* 10. Sovereign Tech Beacon Dot (Indian Saffron/Gold Top Apex) */}
        <circle cx="64" cy="14" r="2.5" fill="url(#pkSaffronGold)" filter="url(#pkCoreGlow)" />

        {/* 11. Optical Glass Specular Flare */}
        <ellipse cx="59" cy="59" rx="3.5" ry="2" fill="#FFFFFF" fillOpacity="0.85" transform="rotate(-30 59 59)" />
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
        <div className="flex items-center gap-1.5">
          <span className="font-extrabold text-lg tracking-tight text-gov-900 dark:text-white block leading-tight font-sans">
            Pratyaksha
          </span>
          <span className="text-[11px] font-semibold text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/70 border border-teal-200 dark:border-teal-800 px-1.5 py-0.2 rounded">
            प्रत्यक्ष
          </span>
        </div>
        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium leading-tight mt-0.5 tracking-wide uppercase">
          AI Skilling Centre Monitoring Unit
        </p>
      </div>
    </div>
  );
};
