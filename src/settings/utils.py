def pretty_compact_json(obj, _key: str = "root", _level: int = 0, _is_last: bool = False) -> list:
    """Saves a json-like structure in a semi-compact form to keep it human-readable.
       The function keeps structures as much as possible on one line. Exceptions:
       - If the items of a structure contain only "complex" (dict or list) values, each item will be written on a separate line.
       - Both rules can be overruled with the lists `treat_as_complex` and `treat_as_simple` (see code).

    Args:
        obj (Any): The root object of the structure.
        _key (str, optional): The key value of the item. Defaults "root". Only to be used in recursive call.
        _level (int, optional): nesting level, used for indenting. Defaults to 0. Only to be used in  recursive call.
        _is_last (bool, optional): last element of a list or dict. Defaults to False. Only to be used in  recursive call.

    Returns:
        list: _description_
    """
    indent = " " * 8
    treat_as_complex = _key in ["root", "markers", "highlight"]
    treat_as_simple = _key in []
    match obj:
        case None:
            return "null"
        case dict() | list():
            islist = isinstance(obj, list)
            b_, _b = ("[", "]") if islist else ("{", "}")

            if not obj:
                return b_ + _b

            if isinstance(obj, dict):
                lastkey = list(obj.items())[-1][0]
                items_to_str = [
                    f'"{key}": {pretty_compact_json(val, key, _level+1, key==lastkey)}' for key, val in obj.items()
                ]
            else:
                lastvalue = obj[-1]
                items_to_str = [pretty_compact_json(val, _key, _level + 1, val == lastvalue) for val in obj]

            is_complex = all(type(it) in [type(dict()), type(list())] for it in (obj if islist else obj.values()))
            is_complex = (is_complex or treat_as_complex) and not treat_as_simple
            # new line + level indent after last element
            sep0 = "\n" + indent * (_level) if is_complex and _is_last else ""  # new
            # new line + level-1 indent after closing bracket following last element
            sep_1 = "\n" + indent * max(_level - 1, 0) if is_complex and _is_last else ""
            # new line + level indent after any other element
            sep1 = "\n" + indent * (_level + 1) if is_complex else ""
            return f"{b_}{sep1}" + f", {sep1}".join(items_to_str) + f"{sep0}{_b}{sep_1}"
        case bool():
            return str(obj).lower()
        case int() | float():
            return f"{obj}"
        case str():
            return f'"{obj}"'


if __name__ == "__main__":
    from src.settings.settings import (
        get_midiplayer_content,
        get_run_settings,
        save_midiplayer_content,
    )

    settings = get_run_settings()
    content = get_midiplayer_content()
    save_midiplayer_content(content, "content_test.json")
