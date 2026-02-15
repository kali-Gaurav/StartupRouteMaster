from routemaster_agent.proxy import ProxyManager, get_random_ua
import os


def test_proxy_manager_from_env():
    os.environ['RMA_PROXY_LIST'] = 'http://proxy1:3128, http://proxy2:3128'
    pm = ProxyManager()
    assert pm.has_proxies()
    p1 = pm.get_next_proxy()
    p2 = pm.get_next_proxy()
    assert p1 != p2
    ps = pm.get_requests_proxies(p1)
    assert 'http' in ps and ps['http'] == p1


def test_get_random_ua_from_env():
    os.environ['RMA_UA_LIST'] = 'ua1,ua2,ua3'
    ua = get_random_ua()
    assert ua in ['ua1', 'ua2', 'ua3']
