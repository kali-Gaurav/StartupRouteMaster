import React from 'react';

/**
 * IconSprite (Suggestion #12)
 * Inlines common SVG paths as symbols to reduce DOM weight and parsing time.
 */
export const IconSprite = () => (
  <svg xmlns="http://www.w3.org/2000/svg" style={{ display: 'none' }}>
    <symbol id="icon-train" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="16" height="16" x="4" y="3" rx="2" />
      <path d="M4 11h16" />
      <path d="M12 3v8" />
      <path d="m8 19-2 3" />
      <path d="m18 22-2-3" />
      <path d="M8 15h.01" />
      <path d="M16 15h.01" />
    </symbol>
    <symbol id="icon-clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </symbol>
    <symbol id="icon-map-pin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </symbol>
  </svg>
);

interface IconProps extends React.SVGProps<SVGSVGElement> {
  name: "train" | "clock" | "map-pin";
  size?: number;
}

export const Icon = ({ name, size = 24, className, ...props }: IconProps) => (
  <svg width={size} height={size} className={className} {...props}>
    <use href={`#icon-${name}`} />
  </svg>
);
