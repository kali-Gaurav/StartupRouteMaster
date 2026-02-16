import os
from datetime import datetime, timedelta

from routemaster_agent.intelligence import reliability_scheduler
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainMaster, LiveStatus, ScheduleChangeLog, TrainReliabilityIndex
from routemaster_agent.metrics import RMA_TRAIN_RELIABILITY_SCORE


def _seed_train(session, train_no: str):
    # ensure idempotent seed
    session.query(TrainMaster).filter(TrainMaster.train_number == train_no).delete()
    tm = TrainMaster(train_number=train_no, train_name='TNAME', source='SRC', destination='DST')
    session.add(tm)
    session.commit()


def test_compute_reliability_for_train_basic(tmp_path, monkeypatch):
    session = SessionLocal()
    train_no = 'TEST-REL-001'
    # seed train master
    _seed_train(session, train_no)

    # seed a ScheduleChangeLog row (small change)
    diff = {'train_number': train_no, 'db_count': 10, 'added_stations': [], 'removed_stations': [], 'changed_stations': [{'sequence':2}], 'timestamp': datetime.utcnow().isoformat()}
    scl = ScheduleChangeLog(train_number=train_no, detected_at=datetime.utcnow(), diff=diff)
    session.add(scl)

    # seed LiveStatus with small delay
    lst = LiveStatus(train_number=train_no, current_station='SRC', status='Delayed', delay_minutes=12)
    session.add(lst)
    session.commit()

    # monkeypatch avg extraction confidence helper to return 0.8
    monkeypatch.setattr(reliability_scheduler, '_get_avg_extraction_confidence', lambda tn, window_hours=6: 0.8)

    # run compute
    score = reliability_scheduler.compute_reliability_for_train(train_no)
    assert abs(score - (0.8 * (1 - (1/10)) * (1 - (12/60)))) < 1e-6

    # DB row inserted
    session.refresh(scl)
    row = session.query(TrainReliabilityIndex).filter(TrainReliabilityIndex.train_number == train_no).order_by(TrainReliabilityIndex.id.desc()).first()
    assert row is not None
    assert abs(row.reliability_score - score) < 1e-6

    # Prometheus gauge set (via metrics lib internal state)
    val = RMA_TRAIN_RELIABILITY_SCORE.labels(train_number=train_no)._value.get()
    assert abs(val - score) < 1e-6

    # cleanup
    session.query(TrainReliabilityIndex).filter(TrainReliabilityIndex.train_number == train_no).delete()
    session.query(LiveStatus).filter(LiveStatus.train_number == train_no).delete()
    session.query(ScheduleChangeLog).filter(ScheduleChangeLog.train_number == train_no).delete()
    session.query(TrainMaster).filter(TrainMaster.train_number == train_no).delete()
    session.commit()
    session.close()


def test_run_hourly_reliability_job_invokes_for_all(monkeypatch):
    # create two dummy trains
    session = SessionLocal()
    for tn in ('T1', 'T2'):
        session.add(TrainMaster(train_number=tn, train_name='X', source='A', destination='B'))
    session.commit()

    called = []
    monkeypatch.setattr(reliability_scheduler, 'compute_reliability_for_train', lambda tn: called.append(tn) or 0.5)

    count = reliability_scheduler.run_hourly_reliability_job(batch_size=0)
    assert count >= 2
    assert 'T1' in called and 'T2' in called

    # cleanup
    session.query(TrainMaster).filter(TrainMaster.train_number.in_(['T1','T2'])).delete()
    session.commit()
    session.close()