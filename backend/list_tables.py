from database.session import SessionTransit
from sqlalchemy import text
s = SessionTransit()
res = s.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
for r in res:
    print(r[0])
s.close()
