import { useState, useEffect } from 'react';

export default function ThemeToggle() {
  const [isDark, setIsDark] = useState(true); // Default to dark mode

  useEffect(() => {
    const stored = localStorage.getItem('theme');
    // Default to dark mode if no preference stored
    const dark = stored !== 'light';
    setIsDark(dark);
  }, []);

  function toggle() {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('theme', next ? 'dark' : 'light');
  }

  return (
    <div className="relative inline-block w-14 h-7">
      <input
        type="checkbox"
        checked={isDark}
        onChange={toggle}
        className="opacity-0 w-0 h-0"
        id="theme-toggle"
      />
      <label
        htmlFor="theme-toggle"
        title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        className="absolute cursor-pointer inset-0 rounded-full transition-all duration-300 ease-in-out"
        style={{
          backgroundColor: isDark ? 'rgb(107 33 168)' : 'rgb(209 213 219)',
        }}
      >
        {/* Sun icon (left side) */}
        <div
          className="absolute left-2 top-1/2 transform -translate-y-1/2 transition-opacity duration-300"
          style={{
            opacity: isDark ? 0.5 : 1,
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="5" />
            <line x1="12" y1="1" x2="12" y2="3" />
            <line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" />
            <line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
        </div>
        
        {/* Moon icon (right side) */}
        <div
          className="absolute right-2 top-1/2 transform -translate-y-1/2 transition-opacity duration-300"
          style={{
            opacity: isDark ? 1 : 0.5,
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </div>
        
        {/* Slider */}
        <span
          className="absolute left-1 top-1 w-5 h-5 rounded-full transition-transform duration-300 ease-in-out flex items-center justify-center"
          style={{
            transform: isDark ? 'translateX(28px)' : 'translateX(0)',
            backgroundColor: 'white',
          }}
        >
          {isDark ? (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
            </svg>
          )}
        </span>
      </label>
    </div>
  );
}
