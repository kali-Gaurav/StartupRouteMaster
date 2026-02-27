import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { RouteCard } from '@/components/RouteCard';
import { Route } from '@/data/routes';

describe('RouteCard component', () => {
  const mockRoute: Route = {
    id: "TEST_ROUTE_1",
    category: "BALANCED",
    segments: [
      {
        routeId: "TEST_ROUTE_1",
        category: "BALANCED",
        segment: 1,
        trainNumber: "12345",
        trainName: "TEST EXP",
        from: "AAA",
        to: "BBB",
        departure: "10:00",
        arrival: "12:00",
        distance: 100,
        duration: 120,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-0050",
        liveFare: 500,
        seatAvailable: true,
      }
    ],
    totalTime: 120,
    totalCost: 500,
    totalTransfers: 0,
    totalDistance: 100,
    liveFareTotal: 500,
    seatProbability: 90,
    safetyScore: 95, // High safety score for Verified Safe badge
  };

  it('renders Safety Score and Verified Safe badge when safety score is >= 90', () => {
    render(
      <RouteCard 
        route={mockRoute} 
        index={0} 
        isUnlocked={true} 
        onUnlock={vi.fn()} 
      />
    );
    
    // Check if the verified safe badge is rendered
    expect(screen.getByText(/Verified Safe/i)).toBeInTheDocument();
    
    // Check if the actual safety score is rendered
    expect(screen.getByText(/Safety 95\/100/i)).toBeInTheDocument();
  });

  it('does not render Verified Safe badge when safety score is < 90', () => {
    const lowSafetyRoute = { ...mockRoute, safetyScore: 85 };
    render(
      <RouteCard 
        route={lowSafetyRoute} 
        index={0} 
        isUnlocked={true} 
        onUnlock={vi.fn()} 
      />
    );
    
    // Verified Safe badge should not be present
    expect(screen.queryByText(/Verified Safe/i)).not.toBeInTheDocument();
    
    // Safety score should still be present
    expect(screen.getByText(/Safety 85\/100/i)).toBeInTheDocument();
  });
});
