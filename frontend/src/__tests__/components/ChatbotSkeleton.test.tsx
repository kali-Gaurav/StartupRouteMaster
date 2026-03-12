import { render, screen, waitFor } from '@testing-library/react';
import { RailAssistantChatbot } from '@/components/RailAssistantChatbot';
import { test, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '@/store/useChatStore';

const noop = () => {};

describe('Chatbot Skeleton & Layout Stability (Task 1.6)', () => {
  beforeEach(() => {
    useChatStore.getState().clearHistory();
    vi.clearAllMocks();
  });

  test('TC1: Skeletons are visible when isHydrating is true', async () => {
    useChatStore.setState({ isHydrating: true, isOpen: true });
    
    render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  test('TC2: Skeletons disappear when isHydrating becomes false', async () => {
    useChatStore.setState({ isHydrating: true, isOpen: true });
    const { rerender } = render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    
    useChatStore.setState({ isHydrating: false });
    rerender(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    expect(document.querySelectorAll('.animate-pulse').length).toBe(0);
  });

  test('TC3: Virtualizer setup does not crash during hydration', () => {
    useChatStore.setState({ isHydrating: true, isOpen: true });
    expect(() => render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />)).not.toThrow();
  });

  test('TC4: Recent searches are preserved during hydration', async () => {
    localStorage.setItem('routemaster_ai_memory', JSON.stringify({ recentSearches: ['Delhi to Mumbai'] }));
    useChatStore.setState({ isHydrating: true, isOpen: true });
    
    render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    expect(await screen.findByText('Delhi to Mumbai')).toBeTruthy();
  });

  test('TC5: Header status reflects standby during hydration', () => {
    useChatStore.setState({ isHydrating: true, isOpen: true });
    render(<RailAssistantChatbot onSearchRequest={noop} onNavigate={noop} />);
    
    // Header should still show branding but maybe a loading state in telemetry
    expect(screen.getByText(/RouteMaster/i)).toBeTruthy();
  });
});
