import csv
import os
from schemas.service_loops import Services



class FileManager:
    def __init__(self,mode,scac):
        self.scac = scac
        self.filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'{self.scac}_port_rotation.csv')
        self.mode = mode
        self.file = None

    def __enter__(self):
        self.file = open(self.filename, mode = self.mode, encoding="utf-8", newline='')
        self.writer = csv.DictWriter(self.file,fieldnames=list(Services.schema()['properties'].keys()))
        self.writer.writeheader()
        return self.writer
    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.file.close()








    