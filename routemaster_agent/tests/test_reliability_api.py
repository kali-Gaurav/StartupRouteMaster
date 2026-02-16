from fastapi.testclient import TestClient
from routemaster_agent.main import app
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainMaster, TrainReliabilityIndex, LiveStatus, ScheduleChangeLog

client = TestClient(app)


def _seed_train(session, train_no: str):
    session.query(TrainMaster).filter(TrainMaster.train_number == train_no).delete()
    session.add(TrainMaster(train_number=train_no, train_name='T', source='A', destination='B'))
    session.commit()


def test_admin_recompute_reliability(monkeypatch):
    session = SessionLocal()
    train_no = 'RECOMP-001'
    _seed_train(session, train_no)

    # seed LiveStatus and ScheduleChangeLog to influence computation
    session.query(LiveStatus).filter(LiveStatus.train_number == train_no).delete()
    session.add(LiveStatus(train_number=train_no, current_station='SRC', status='On Time', delay_minutes=6))
    diff = {'train_number': train_no, 'db_count': 10, 'added_stations': [], 'removed_stations': [], 'changed_stations': [], 'timestamp': 'now'}
    session.add(ScheduleChangeLog(train_number=train_no, diff=diff))
    session.commit()

    # monkeypatch prometheus helper to return avg confidence 0.9
    import routemaster_agent.intelligence.reliability_scheduler as rs
    monkeypatch.setattr(rs, '_get_avg_extraction_confidence', lambda tn, window_hours=6: 0.9)

    resp = client.post('/api/admin/reliability/recompute', json={'trains': [train_no]})
    assert resp.status_code == 200
    data = resp.json()
    assert 'results' in data and train_no in data['results']

    # verify DB row inserted
    row = session.query(TrainReliabilityIndex).filter(TrainReliabilityIndex.train_number == train_no).order_by(TrainReliabilityIndex.id.desc()).first()
    assert row is not None

    # cleanup
    session.query(TrainReliabilityIndex).filter(TrainReliabilityIndex.train_number == train_no).delete()
    session.query(LiveStatus).filter(LiveStatus.train_number == train_no).delete()
    session.query(ScheduleChangeLog).filter(ScheduleChangeLog.train_number == train_no).delete()
    session.query(TrainMaster).filter(TrainMaster.train_number == train_no).delete()
    session.commit()
    session.close()