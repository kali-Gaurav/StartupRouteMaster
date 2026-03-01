import sys, os
sys.path.append(os.getcwd())
import pickle

path='snapshots/graph_snapshot_20260325.pkl'
if not os.path.exists(path):
    print('snapshot missing')
    sys.exit(1)

snap=pickle.load(open(path,'rb'))
tg=snap.transfer_graph
print('total stops with transfers', len(tg))
nonself=0
total_edges=0
for k,v in tg.items():
    for t in v:
        total_edges+=1
        # determine destination
        if hasattr(t,'to_stop_id'):
            dest = t.to_stop_id
        elif hasattr(t,'station_id'):
            dest = t.station_id
        else:
            dest = None
        if dest is not None and dest!=k:
            nonself+=1
print('total edges', total_edges)
print('nonself transfers', nonself)

# print some example nonself edges
count=0
for k,v in tg.items():
    for t in v:
        if hasattr(t,'to_stop_id'):
            dest = t.to_stop_id
            time = getattr(t,'total_time_minutes',None)
        else:
            dest = getattr(t,'station_id',None)
            time = getattr(t,'duration_minutes',None)
        if dest and dest!=k and count<10:
            print(k,'->',dest,'time',time)
            count+=1
