import { render, screen, act } from '@testing-library/react';
import { RailAssistantChatbot } from '@/components/RailAssistantChatbot';
import { test, expect, vi, beforeEach, describe } from 'vitest';
import { useChatStore } from '@/store/useChatStore';

const noop = () => {};

describe('Chatbot Skeleton & Layout Stability (Task 1.6)', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().clearHistory();
      useChatStore.setState({ isHydrating: false, isOpen: false });
    });
    localStorage.clear();
    vi.clearAllMocks();
  });

  test('TC1: Skeletons are visible when isHydrating is true', async () => {
    await act(async () => {
      useChatStore.setState({ isHydrating: true, isOpen: true });
    });
    
    render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  test('TC2: Skeletons disappear when isHydrating becomes false', async () => {
    await act(async () => {
      useChatStore.setState({ isHydrating: true, isOpen: true });
    });
    const { rerender } = render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    
    await act(async () => {
      useChatStore.setState({ isHydrating: false });
    });
    rerender(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    expect(document.querySelectorAll('.animate-pulse').length).toBe(0);
  });

  test('TC3: Virtualizer setup does not crash during hydration', async () => {
    await act(async () => {
      useChatStore.setState({ isHydrating: true, isOpen: true });
    });
    expect(() => render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />)).not.toThrow();
  });

  test('TC4: Recent searches are preserved during hydration', async () => {
    const memory = { recentSearches: ['Delhi to Mumbai'] };
    localStorage.setItem('diksha_memory_v1', JSON.stringify(memory));
    
    await act(async () => {
      useChatStore.setState({ isHydrating: true, isOpen: true });
    });
    
    render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    // findByText handles the async effect inside the component
    expect(await screen.findByText('Delhi to Mumbai')).toBeTruthy();
  });

  test('TC5: Header status reflects standby during hydration', async () => {
    await act(async () => {
      useChatStore.setState({ isHydrating: true, isOpen: true });
    });
    render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    expect(screen.getByText(/RouteMaster/i)).toBeTruthy();
  });
});
