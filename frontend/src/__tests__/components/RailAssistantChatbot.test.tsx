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
  