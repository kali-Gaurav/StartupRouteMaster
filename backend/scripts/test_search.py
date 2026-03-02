import requests

dates = ['2026-03-02','2026-03-03']
for src,dst in [('KOTA','JP'),('NDLS','BCT')]:
    for date in dates:
        r = requests.post('http://127.0.0.1:8000/api/search/', json={'source':src,'destination':dst,'date':date})
        print(src,'->',dst,'date',date,'status',r.status_code)
        try:
            print(r.json())
        except Exception:
            print(r.text)
        print('-'*60)
