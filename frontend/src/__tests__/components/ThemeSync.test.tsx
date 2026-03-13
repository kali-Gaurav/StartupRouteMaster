import { render, screen, act, waitFor } from '@testing-library/react';
import { ThemeProvider, useTheme } from '@/context/ThemeContext';
import { test, expect, vi, beforeEach, describe } from 'vitest';

// Helper component to debug theme state
function ThemeDebugger() {
  const { mode, isLowPowerMode } = useTheme();
  return (
    <div>
      <div data-testid="mode">{mode}</div>
      <div data-testid="low-power">{isLowPowerMode ? 'true' : 'false'}</div>
    </div>
  );
}

describe('Task 1.12: Native Theme Sync & Energy-Aware UI', () => {
  let mediaQueryCallback: ((e: any) => void) | null = null;
  let batteryCallback: (() => void) | null = null;

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();

    // Mock matchMedia
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn((event, cb) => {
        if (event === 'change') mediaQueryCallback = cb;
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    // Mock getBattery
    (navigator as any).getBattery = vi.fn().mockResolvedValue({
      level: 1.0,
      charging: true,
      addEventListener: vi.fn((event, cb) => {
        if (event === 'levelchange' || event === 'chargingchange') batteryCallback = cb;
      }),
    });
  });

  test('TC1: OS Sync follows OS dark mode changes', async () => {
    render(<ThemeProvider><ThemeDebugger /></ThemeProvider>);
    
    expect(screen.getByTestId('mode').textContent).toBe('light');

    await act(async () => {
      if (mediaQueryCallback) {
        mediaQueryCallback({ matches: true } as any);
      }
    });

    expect(screen.getByTestId('mode').textContent).toBe('dark');
  });

  test('TC2: Battery Drop < 20% triggers Energy Safe mode', async () => {
    let batteryInstance = {
      level: 1.0,
      charging: true,
      addEventListener: vi.fn((event, cb) => {
        if (event === 'levelchange') batteryCallback = cb;
      }),
      removeEventListener: vi.fn(),
    };
    (navigator as any).getBattery = vi.fn().mockResolvedValue(batteryInstance);

    render(<ThemeProvider><ThemeDebugger /></ThemeProvider>);

    await act(async () => {
      // Simulate battery drop to 15% and unplugged on the same object
      batteryInstance.level = 0.15;
      batteryInstance.charging = false;
      if (batteryCallback) batteryCallback();
    });

    // Wait for the async effect inside component
    await waitFor(() => {
      expect(screen.getByTestId('low-power').textContent).toBe('true');
      expect(screen.getByTestId('mode').textContent).toBe('dark');
    }, { timeout: 2000 });
  });

  test('TC3: Charging Restore disables Energy Safe mode', async () => {
    let batteryInstance = {
      level: 0.15,
      charging: false,
      addEventListener: vi.fn((event, cb) => {
        if (event === 'chargingchange') batteryCallback = cb;
      }),
      removeEventListener: vi.fn(),
    };
    (navigator as any).getBattery = vi.fn().mockResolvedValue(batteryInstance);

    render(<ThemeProvider><ThemeDebugger /></ThemeProvider>);

    await waitFor(() => expect(screen.getByTestId('low-power').textContent).toBe('true'));

    await act(async () => {
      // Simulate plugging in
      batteryInstance.charging = true;
      if (batteryCallback) batteryCallback();
    });

    await waitFor(() => {
      expect(screen.getByTestId('low-power').textContent).toBe('false');
    }, { timeout: 2000 });
  });

  test('TC8: Manual Override pauses auto-sync', async () => {
    const { rerender } = render(<ThemeProvider><ThemeDebugger /></ThemeProvider>);
    
    // Set manual preference
    localStorage.setItem('rm-theme-mode', 'light');
    
    await act(async () => {
      if (mediaQueryCallback) {
        mediaQueryCallback({ matches: true } as any); // OS changes to dark
      }
    });

    // Should stay light because of manual override in localStorage
    expect(screen.getByTestId('mode').textContent).toBe('light');
  });

  test('TC12: Zustand/LocalStorage Hydration restores mode', () => {
    localStorage.setItem('rm-theme-mode', 'dark');
    render(<ThemeProvider><ThemeDebugger /></ThemeProvider>);
    expect(screen.getByTestId('mode').textContent).toBe('dark');
  });
});
