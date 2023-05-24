import os

this_folder = os.path.dirname(os.path.abspath(__file__))

def find_dictionaries_by_value(lst:list,key:str,value:str):
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
def order_counter(i,type:str)->int:
    if type =='L':
        i = i * 2
    else: i = i * 2 +1
    return i

# Lookup the location code by name
def location_lookup(location: str) :
    port_code = os.path.join(this_folder, '../port_code.txt')
    with open(port_code, mode="r") as unloc:
        dict_loc_code: dict = {k: v for k, v in (map(str, line.split(";")) for line in unloc)}
        port_code: str = str(dict_loc_code.get(location)).strip()
    yield port_code
