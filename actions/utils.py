from urllib.parse import quote


def join_args(args):
    if not args:
        return ''
    arglist = []
    for key in sorted(args, key=lambda x: x.lower()):
        value = str(args[key])
        arglist.append(f"{key}={quote(value, safe='')}")
    return f"?{'&'.join(arglist)}"


def flatten(data):
    return [
        record
        for records
        in data
        for record
        in records
    ]
