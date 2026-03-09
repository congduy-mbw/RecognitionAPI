def remove_base64(obj):
    if isinstance(obj, dict):
        obj.pop("base64_image", None)
        for v in obj.values():
            remove_base64(v)
    elif isinstance(obj, list):
        for item in obj:
            remove_base64(item)