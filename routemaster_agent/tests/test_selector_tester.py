from routemaster_agent.intelligence.selector_tester import evaluate_selectors


def test_selector_tester_basic_table():
    html = """
    <html><body>
    <table class="table-striped"><tbody>
      <tr><td>1</td><td>NDLS</td><td>06:00</td></tr>
      <tr><td>2</td><td>CNB</td><td>09:30</td></tr>
    </tbody></table>
    </body></html>
    """
    selectors = ['table.table-striped tbody tr', 'table tbody tr td:nth-child(2)']
    results = evaluate_selectors(html, selectors, expected_min_rows=2)
    assert results, "results should not be empty"
    # best result should have non-zero score and rows_count >= 2 for first selector
    best = results[0]
    assert best['rows_count'] >= 1
    assert best['score'] > 0
