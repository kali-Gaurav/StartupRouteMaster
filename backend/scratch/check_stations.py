from database.session import SessionTransit
from database.models import Stop

with SessionTransit() as db:
    # Check if ALJN and NDLS exist
    aljn = db.query(Stop).filter(Stop.code == "ALJN").first()
    ndls = db.query(Stop).filter(Stop.code == "NDLS").first()
    blr = db.query(Stop).filter(Stop.code == "BLR").first()
    
    print(f"ALJN: {aljn.name if aljn else 'Missing'} ({aljn.latitude if aljn else 'N/A'}, {aljn.longitude if aljn else 'N/A'})")
    print(f"NDLS: {ndls.name if ndls else 'Missing'} ({ndls.latitude if ndls else 'N/A'}, {ndls.longitude if ndls else 'N/A'})")
    print(f"BLR: {blr.name if blr else 'Missing'} ({blr.latitude if blr else 'N/A'}, {blr.longitude if blr else 'N/A'})")
