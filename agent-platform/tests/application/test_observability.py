from agent_platform.application.observability import trace_id_or_new


def test_trace_id_or_new_is_non_empty():
    value=trace_id_or_new()
    assert isinstance(value,str)
    assert len(value)>=16
