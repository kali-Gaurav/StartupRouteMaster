from core.engines.frontier import FrontierRoute, ParetoFrontier, FrontierManager

def test_pareto_dominance():
    # Route A: Arrives 10:00 (600), 1 transfer, 60m wait
    a = FrontierRoute(600, 1, 60, 500.0)
    
    # Route B: Arrives 10:30 (630), 1 transfer, 90m wait
    # A should dominate B (earlier arrival, same transfers, less wait)
    b = FrontierRoute(630, 1, 90, 500.0)
    assert a.dominates(b) is True
    assert b.dominates(a) is False
    
    # Route C: Arrives 11:00 (660), 0 transfers, 0m wait
    # A and C are non-dominating. A arrives earlier, C has fewer transfers.
    c = FrontierRoute(660, 0, 0, 500.0)
    assert a.dominates(c) is False
    assert c.dominates(a) is False

def test_frontier_eviction():
    frontier = ParetoFrontier(max_size=2)
    
    # Add non-dominating routes
    r1 = FrontierRoute(600, 2, 60, 500.0) # Best arrival
    r2 = FrontierRoute(700, 1, 30, 500.0)
    r3 = FrontierRoute(800, 0, 0, 500.0)  # Best transfers
    
    frontier.add(r1)
    frontier.add(r2)
    assert len(frontier.routes) == 2
    
    # Adding r3 should trigger eviction.
    # It should keep r1 (best arrival) and r3 (best transfers), evicting r2.
    frontier.add(r3)
    assert len(frontier.routes) == 2
    assert frontier.routes[0].arrival_time == 600
    assert frontier.routes[1].arrival_time == 800
    assert frontier.routes[1].transfers == 0
    print("Scenario: Smart Eviction: OK")

def test_frontier_manager_isolation():
    manager = FrontierManager()
    r1 = FrontierRoute(600, 1, 60, 500.0)
    
    # Station 1
    assert manager.is_dominated(1, r1) is False
    # Repeat should be dominated (already exists)
    assert manager.is_dominated(1, r1) is True
    
    # Station 2 should be independent
    assert manager.is_dominated(2, r1) is False

if __name__ == "__main__":
    test_pareto_dominance()
    test_frontier_eviction()
    test_frontier_manager_isolation()
    print("TASK 3 VERIFICATION COMPLETE")
