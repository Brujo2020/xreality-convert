ORGANIC_DELIVERY_DEFAULTS = {
    "animal": {"profile": "xreal", "steps": 50, "octree_resolution": 256, "target_faces": 100000, "texture": True, "texture_size": "2K", "guidance": 7.5},
    "person": {"profile": "pcvr", "steps": 50, "octree_resolution": 256, "target_faces": 120000, "texture": True, "texture_size": "2K", "guidance": 7.0},
}


def normalize_generation_request(request):
    defaults = ORGANIC_DELIVERY_DEFAULTS.get(request.category)
    if request.profile != "lowpoly" or not defaults:
        return request
    if hasattr(request, "model_copy"):
        return request.model_copy(update=defaults)
    if hasattr(request, "copy"):
        return request.copy(update=defaults)
    values = dict(vars(request))
    values.update(defaults)
    return type(request)(**values)
