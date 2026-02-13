import React from 'react';
import { render, screen } from '@testing-library/react';
import { StationSearch } from '@/components/StationSearch';

test('renders Station Search component', () => {
  render(
    <StationSearch
      label="From"
      placeholder="Search station"
      value={null}
      onChange={() => {}}
    />
  );
  const el = screen.getByText(/From|Search station/i);
  expect(el).toBeInTheDocument();
});