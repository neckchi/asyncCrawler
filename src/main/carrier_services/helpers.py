from functools import cache
from thefuzz import process
from src.main import location_mapping
import os


this_folder = os.path.dirname(os.path.abspath(__file__))

def find_dictionaries_by_value(lst:list,key:str,value:str) :
    return [d for d in lst if d.get(key) == value]

def split_list_of_dicts(lst:list, key:str) -> dict[list]:
    result:dict={}
    for d in lst:
        value:dict = d.get(key)
        if value in result:
            result[value].append(d)
        else:
            result[value] = [d]
    return result

#Generate Order Sequence Number

@cache
def order_counter(i,type:str)->int:
    if type =='L':
        i = i * 2
    else: i = i * 2 +1
    return i

# Lookup the location code by name
@cache
def find_closest_location_code(query:str) -> str:
    match = process.extractOne(query.title(), location_mapping.location_dictionaries.keys())
    return location_mapping.location_dictionaries[match[0]]





