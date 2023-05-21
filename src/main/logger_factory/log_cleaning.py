from datetime import datetime
from pathlib import Path

def cleaning(clean_day:int = -30):
    today = datetime.today()
    for i in Path('logs/').rglob('*.log'):
        mtime = datetime.fromtimestamp(i.stat().st_mtime)
        filetime = mtime - today
        if filetime.days <= clean_day:
            i.unlink()

