"""Small display helpers shared by the dashboard pages."""

STATUS_LABELS = {
    "action_needed": "✋ Your turn", "in_progress": "⏳ Waiting for them", "offer": "🎉 Offer",
    "ghosted": "👻 Ghosted", "rejected": "✕ Rejected", "expired": "⌛ Expired",
}
LABEL_TO_STATUS = {label: status for status, label in STATUS_LABELS.items()}

CATEGORY_LABELS = {
    "confirmation": "Confirmation", "rejection": "Rejection", "assessment": "Assessment",
    "interview": "Interview", "offer": "Offer",
}


def nice_name(name: str) -> str:
    # Extracted names are lowercase ("blablacar"); corrected ones keep your capitalization
    return name.title() if name == name.lower() and "." not in name else name
