import json

def read_variable(string):
    return json.loads(string)


def show_variable(variable):
    return json.dumps(variable)

def read_string(string):
    """Try to transform string argument value to armonic primitive type"""
    if string.startswith('[') and string.endswith(']'):
        return [l.lstrip() for l in string[1:-1].split(",")]
    try:
        return int(string)
    except ValueError:
        return string


def require_validation_error(dct):
    """Take the return dict of provide_call_validate and return a list of
    tuple that contains (xpath, error_string)"""
    if dct['errors'] is False:
        return []
    errors = []
    provides = dct['requires']
    for p in provides:
        for r in p['requires']:
            for variables in r['variables']:
                for v in variables:
                    if v['error'] is not None:
                        errors.append((v['xpath'], v['error']))
    return errors
