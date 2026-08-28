export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="TESQIVO"
    >
      <defs>
        <linearGradient id="tq-g" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffffff" />
          <stop offset="1" stopColor="#d9e4ff" />
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="url(#tq-g)" opacity="0.16" />
      <rect x="1.5" y="1.5" width="29" height="29" rx="8" stroke="currentColor" strokeOpacity="0.5" />
      <path
        d="M9 16.5 L14 21.5 L23.5 10.5"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="24.5" cy="21.5" r="2.4" fill="currentColor" />
    </svg>
  );
}
