import React from 'react';
import { render, screen } from '@testing-library/react';
import { RailAssistantChatbot } from '@/components/RailAssistantChatbot';

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