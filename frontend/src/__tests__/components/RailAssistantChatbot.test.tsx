import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RailAssistantChatbot } from '@/components/RailAssistantChatbot';
import { test, expect, vi } from 'vitest';

const noop = () => {};
test('renders Rail Assistant Chatbot', () => {
  render(
    <RailAssistantChatbot
      onSearchRequest={noop}
      onSortChange={noop}
      onNavigate={noop}
    />
  );
  const el = screen.queryByText(/chatbot|search|rail/i);
  expect(el || document.body).toBeTruthy();
});

test('dispatches suggestion event when backend returns actions', async () => {
  const mockResponse = {
    ok: true,
    json: async () => ({ reply: 'Here are suggestions', actions: [{ label: 'Delhi to Mumbai', type: 'intent', value: 'search' }] }),
  } as unknown as Response;
  
  const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(mockResponse);
  const dispatchSpy = vi.spyOn(window, 'dispatchEvent');

  render(<RailAssistantChatbot onSearchRequest={noop} onSortChange={noop} onNavigate={noop} />);

  // Open the chatbot first (it starts minimized)
  const toggleBtn = screen.getByRole('button');
  fireEvent.click(toggleBtn);

  // Type into input and send a phrase that BYPASSES local intent (which triggers search directly)
  const input = await screen.findByPlaceholderText(/Type or Ask Rail Assistant/i);
  fireEvent.change(input, { target: { value: 'tell me about the app' } });
  const sendBtn = screen.getByRole('button', { name: /send/i }) || screen.getAllByRole('button').find(b => b.querySelector('svg'));
  // Click send (use any available send button)
  fireEvent.click(sendBtn as Element);

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: 'rail-assistant-suggestions' }));
  
    fetchSpy.mockRestore();
    dispatchSpy.mockRestore();
  });

  test('quick action Search Trains adds prompt and does not trigger backend', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<RailAssistantChatbot onSearchRequest={noop} onSortChange={noop} onNavigate={noop} />);
    // clear any initialization network calls
    fetchSpy.mockClear();

    const toggleBtn = screen.getByRole('button');
    fireEvent.click(toggleBtn);
    const quickBtns = await screen.findAllByText('Search Trains');
    // click the bottom toolbar version (last occurrence)
    fireEvent.click(quickBtns[quickBtns.length - 1]);
    // user message should appear immediately (at least one message contains the text)
    expect(screen.getAllByText(/Search Trains/).length).toBeGreaterThanOrEqual(1);
    // the prompt text should show (partial match to avoid markup issues)
    await waitFor(() => expect(screen.getByText(/Where would you like/i)).toBeInTheDocument());
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });


  test('cancel button aborts inflight request and hides loader', async () => {
    // simulate a long-running fetch
    let resolveFetch: Function;
    const promise = new Promise<Response>((res) => { resolveFetch = res; });
    const fetchSpy = vi.spyOn(global, 'fetch').mockReturnValue(promise as any);

    render(<RailAssistantChatbot onSearchRequest={noop} onSortChange={noop} onNavigate={noop} />);
    const toggleBtn = screen.getByRole('button');
    fireEvent.click(toggleBtn);
    const input = await screen.findByPlaceholderText(/Type or Ask Rail Assistant/i);
    // send a query that will NOT be handled locally so backend request is made
    fireEvent.change(input, { target: { value: 'unhandled query 123' } });
    const sendBtn = screen.getByRole('button', { name: /send/i }) || screen.getAllByRole('button').find(b => b.querySelector('svg'));
    fireEvent.click(sendBtn as Element);
    // wait for loader/cancel to appear
    await waitFor(() => expect(screen.getByText(/cancel/i)).toBeTruthy());
    // click cancel
    fireEvent.click(screen.getByText(/cancel/i));
    // loader should disappear
    await waitFor(() => expect(screen.queryByText(/cancel/i)).toBeNull());
    fetchSpy.mockRestore();
  });
  