import { render, screen, act, waitFor } from '@testing-library/react';
import { RailAssistantChatbot } from '@/components/RailAssistantChatbot';
import { test, expect, vi, beforeEach, describe } from 'vitest';
import { useChatStore } from '@/store/useChatStore';
import { ThemeProvider } from '@/context/ThemeContext';

const noop = () => {};

describe('Task 1.15 & 1.16: Origin Animation & Auto-Focus', () => {
  beforeEach(() => {
    // Mock matchMedia
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    // Mock getBattery
    (navigator as any).getBattery = vi.fn().mockResolvedValue({
      level: 1.0,
      charging: true,
      addEventListener: vi.fn(),
    });

    act(() => {
      useChatStore.getState().clearHistory();
      useChatStore.setState({ isOpen: false });
    });
    localStorage.clear();
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('TC1.16: Input field is focused when chatbot opens', async () => {
    render(<ThemeProvider><RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} /></ThemeProvider>);
    
    // Initial state: closed
    expect(screen.queryByPlaceholderText(/Message/i)).toBeNull();

    // Open it
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    // Chatbot should appear
    expect(screen.getByPlaceholderText(/Message/i)).toBeTruthy();

    // Advance timers to trigger the focus useEffect
    act(() => {
      vi.advanceTimersByTime(600);
    });

    const input = screen.getByPlaceholderText(/Message/i);
    expect(document.activeElement).toBe(input);
  });

  test('TC1.15: Origin zoom classes are applied', async () => {
    render(<ThemeProvider><RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} /></ThemeProvider>);
    
    act(() => {
      useChatStore.setState({ isOpen: true });
    });

    const widget = document.querySelector('.origin-bottom-right');
    expect(widget).toBeTruthy();
    expect(widget?.className).toContain('will-change-transform');
  });
});
