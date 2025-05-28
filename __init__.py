def classFactory(iface):
    from .overlap_resolver import OverlapResolver
    return OverlapResolver(iface) 