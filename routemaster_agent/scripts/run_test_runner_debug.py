import asyncio
from routemaster_agent.testing.runner import TestRunner
from routemaster_agent.scrapers.ntes_agent import NTESAgent

async def fake_get_schedule(self, page, train_no):
    return {
        'train_no': train_no,
        'name': 'TEST TRAIN',
        'source': 'SRC',
        'destination': 'DST',
        'days_of_run': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
        'schedule': [
            {'sequence':1,'station_code':'SRC','station_name':'SRC JN','day':1,'arrival':None,'departure':'06:00','halt_minutes':0,'distance':0},
            {'sequence':2,'station_code':'MID1','station_name':'MID1 STN','day':1,'arrival':'07:00','departure':'07:05','halt_minutes':5,'distance':80},
            {'sequence':3,'station_code':'MID2','station_name':'MID2 STN','day':1,'arrival':'08:30','departure':'08:35','halt_minutes':5,'distance':160},
            {'sequence':4,'station_code':'MID3','station_name':'MID3 STN','day':1,'arrival':'09:45','departure':'09:50','halt_minutes':5,'distance':230},
            {'sequence':5,'station_code':'DST','station_name':'DST JN','day':1,'arrival':'11:00','departure':None,'halt_minutes':0,'distance':300},
        ]
    }

async def fake_get_live(self, page, train_no):
    return {'train_no':train_no,'current_station':'MID','delay':'0','timestamp':'2026-02-15T00:00:00Z'}

NTESAgent.get_schedule = fake_get_schedule
NTESAgent.get_live_status = fake_get_live

async def main():
    runner = TestRunner(train_numbers=['99999'], concurrency=1, strict=True, save_artifacts=False)
    res = await runner.run()
    print(res)

if __name__ == '__main__':
    asyncio.run(main())