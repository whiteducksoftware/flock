

from flock.core.tools.zendesk_tools import get_comments_by_ticket_id, get_ticket_by_id, get_tickets


def test_get_tickets():
    tickets = get_tickets()
    assert len(tickets) > 0
    assert tickets[0]["id"] is not None
    assert tickets[0]["subject"] is not None
    
    
def test_get_ticket_by_id():
    ticket = get_ticket_by_id("366354")
    assert ticket["id"] is not None
    assert ticket["subject"] is not None
    

def test_get_comments_by_ticket_id():
    comments = get_comments_by_ticket_id("366354")
    assert len(comments) > 0
    assert comments[0]["id"] is not None
    assert comments[0]["body"] is not None
    
    




