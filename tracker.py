TRACKED_FIELDS = ("title", "description", "status_code", "content_type", "server_header",
                  "pages_scanned", "technology_hints", "pages")


def compare_with_previous(current: dict, previous_snapshot: dict | None) -> dict:
    if previous_snapshot is None:
        return {"previous_exists": False, "changed": False, "differences": {}}
    previous = previous_snapshot["content"]
    differences = {}
    for field in TRACKED_FIELDS:
        before, after = previous.get(field), current.get(field)
        if before != after:
            differences[field] = {"before": before, "after": after}
    return {"previous_exists": True, "changed": bool(differences), "differences": differences}
