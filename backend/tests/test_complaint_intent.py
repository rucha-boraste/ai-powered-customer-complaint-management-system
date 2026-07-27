from backend.complain_management.services import choose_intent


def test_choose_intent_returns_update_for_follow_up_message():
    state = {
        "raw_text": "Please update the customer name to XYZ Pharma Pvt Ltd.",
        "file_bytes": None,
        "file_name": None,
        "extracted_text": "",
        "storage_path": None,
        "complaint": {},
        "current_complaint": {"customer_name": "ABC Pharma Pvt Ltd"},
    }

    assert choose_intent(state) == "update"


def test_choose_intent_keeps_new_extraction_flow_for_initial_request():
    state = {
        "raw_text": "A complaint was received about a damaged bottle.",
        "file_bytes": None,
        "file_name": None,
        "extracted_text": "",
        "storage_path": None,
        "complaint": {},
        "current_complaint": None,
    }

    assert choose_intent(state) == "extract"
