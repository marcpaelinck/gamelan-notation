def convert_str_to_numeric(val: str):
    if isinstance(val, str):
        numval = None
        try:
            numval = int(val)
        except:
            try:
                numval = float(val)
            except:
                numval = None
        return numval or val


def convert_str_and_list_to_numeric(val: str | list[str]):
    if isinstance(val, str):
        return convert_str_to_numeric(val)
    elif isinstance(val, list):
        return [convert_str_to_numeric(v) for v in val]
    else:
        return val
