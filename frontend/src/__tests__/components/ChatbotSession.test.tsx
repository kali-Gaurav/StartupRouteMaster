import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { RailAssistantChatbot } from '@/components/RailAssistantChatbot';
import { test, expect, vi, beforeEach, describe } from 'vitest';
import { useChatStore } from '@/store/useChatStore';
import { ThemeProvider } from '@/context/ThemeContext';

const noop = () => {};

describe('Task 1.10, 1.14, 1.17: Scroll, Scrollbar & Draft Persistence', () => {
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
      useChatStore.setState({ isOpen: true, isHydrating: false });
    });
    localStorage.clear();
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('TC1.17: Input draft is persisted in global store', async () => {
    render(<ThemeProvider><RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} /></ThemeProvider>);
    
    const input = screen.getByPlaceholderText(/Message/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Draft Message' } });
    
    expect(useChatStore.getState().draftInput).toBe('Draft Message');
  });

  test('TC1.17: Draft is restored when chatbot re-opens', async () => {
    act(() => {
      useChatStore.setState({ draftInput: 'Restored Draft' });
    });

    render(<ThemeProvider><RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} /></ThemeProvider>);
    
    const input = screen.getByPlaceholderText(/Message/i) as HTMLInputElement;
    expect(input.value).toBe('Restored Draft');
  });

  test('TC1.18: Reset Terminal clears history and draft', async () => {
    act(() => {
      useChatStore.setState({ draftInput: 'Typing...' });
      useChatStore.getState().addMessage({ role: 'user', content: 'Old Msg' });
    });

    render(<ThemeProvider><RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} /></ThemeProvider>);
    
    const resetButton = screen.getByTitle(/Reset Terminal/i);
    await act(async () => {
      fireEvent.click(resetButton);
    });
    
    expect(useChatStore.getState().messages.length).toBe(0);
    expect(useChatStore.getState().draftInput).toBe('');
    
    const input = screen.getByPlaceholderText(/Message/i) as HTMLInputElement;
    expect(input.value).toBe('');
  });

  test('TC1.10: New Message Badge appears when scrolled up', async () => {
    // Fill history to enable scrolling
    await act(async () => {
      useChatStore.getState().clearHistory();
      for(let i=0; i<10; i++) {
        useChatStore.getState().addMessage({ role: 'assistant', content: `Msg ${i}` });
      }
      useChatStore.setState({ isHydrating: false, isOpen: true });
    });

    render(<ThemeProvider><RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} /></ThemeProvider>);
    
    const scrollContainer = document.querySelector('.flex-1.overflow-y-auto');
    expect(scrollContainer).toBeTruthy();
    
    // Simulate being scrolled up
    await act(async () => {
      // Manual mock of the ref-based logic by triggering scroll with custom properties
      Object.defineProperty(scrollContainer, 'scrollTop', { value: 0, configurable: true });
      Object.defineProperty(scrollContainer, 'scrollHeight', { value: 1000, configurable: true });
      Object.defineProperty(scrollContainer, 'clientHeight', { value: 200, configurable: true });
      fireEvent.scroll(scrollContainer!);
    });

    // Add new message while "scrolled up"
    await act(async () => {
      useChatStore.getState().addMessage({ role: 'assistant', content: 'Incoming Telemetry' });
    });

    // Check for badge visibility with a clean selector
    await waitFor(() => {
      expect(screen.getByText(/New Telemetry/i)).toBeInTheDocument();
    }, { timeout: 4000 });
  });
});
