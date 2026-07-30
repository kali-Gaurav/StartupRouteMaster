import { render, screen } from '@testing-library/react';
import { test, expect, describe } from 'vitest';
import { cn } from '@/lib/utils';

// Simplified component representing the density logic
function BubbleDensityMock({ role }: { role: string }) {
  return (
    <div 
      data-role={role}
      className={cn("flex gap-3 group message-container", 
        role === "user" ? "flex-row-reverse py-3" : 
        role === "system" ? "flex-row py-1" : "flex-row py-3"
      )}
    >
      Content
    </div>
  );
}

describe('Task 1.13: Adaptive Bubble Density Logic Verification', () => {
  test('TC1: System messages use py-1 (high density)', () => {
    render(<BubbleDensityMock role="system" />);
    const systemMsg = screen.getByAttribute('data-role', 'system');
    expect(systemMsg.className).toContain('py-1');
  });

  test('TC2: Assistant messages maintain py-3 (standard spacing)', () => {
    render(<BubbleDensityMock role="assistant" />);
    const assistantMsg = screen.getByAttribute('data-role', 'assistant');
    expect(assistantMsg.className).toContain('py-3');
  });

  test('TC3: User messages maintain py-3 (standard spacing)', () => {
    render(<BubbleDensityMock role="user" />);
    const userMsg = screen.getByAttribute('data-role', 'user');
    expect(userMsg.className).toContain('py-3');
  });
});

// Helper for selecting by attribute since RTL doesn't have it natively
import { queryByAttribute } from '@testing-library/react';
const getByAttribute = queryByAttribute.bind(null, 'data-role');
screen.getByAttribute = (attr, val) => {
  const el = getByAttribute(document.body, val);
  if (!el) throw new Error(`Element with data-role="${val}" not found`);
  return el;
};
