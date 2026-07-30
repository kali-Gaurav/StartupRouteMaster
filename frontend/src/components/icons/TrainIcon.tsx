import React from "react";

/**
 * Optimized Train Icon (Zero Dependency)
 * Replaces lucide-react Train icon to reduce bundle size.
 */
export function TrainIcon({ className = "", size = 24, ...props }: React.SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`lucide lucide-train ${className}`}
      {...props}
    >
      <path d="M7 15h10" />
      <path d="M15 2H9a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2Z" />
      <path d="M7 11h10" />
      <path d="M9 5h6" />
      <path d="M7 5h10" />
      <path d="m15 22-2-4" />
      <path d="m9 22 2-4" />
    </svg>
  );
}
