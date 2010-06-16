
def load_sof(source):
    if isinstance(source, str):
        return load_sof(str.split('\n'))
    elif isinstance(source, (file, list)):
        res = dict()
        for line in source:
            if line.startswith('#'):
                continue
            fn = line.split()[0]
            key = line.split()[1]
            if key not in  res:
                res[key] = fn
            elif isinstance(res[key], list):
                res[key].append(fn)
            else:
                res[key] = [ res[key], fn ]
        return res
    else:
        raise ValueError('Cannot assign type %s to framelist' % 
                         source.__class__.__name__)

def load_rc(source):
    if isinstance(source, str):
        return load_rc(source.split('\n'))
    elif isinstance(source, (file, list)):
        res = dict()
        for line in source:
            if not line or not line.strip() or line.startswith('#'):
                continue
            name = line.split('=', 1)[0]
            value = line.split('=', 1)[1]
            if name and value:
                res[name.strip()] = value.strip()
        return res
    else:
        raise ValueError('Cannot assign type %s to parameter list' % 
                         source.__class__.__name__)