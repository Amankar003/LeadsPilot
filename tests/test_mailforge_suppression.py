from modules.mailforge.suppression import MailForgeSuppressionService
from modules.database.db_init import init_db

def test_suppression_workflow():
    init_db()
    service = MailForgeSuppressionService()
    email = "unsubscribed-client@domain.com"
    
    # Assert not suppressed initially
    assert not service.is_suppressed(email)
    
    # Add suppression
    assert service.add_email(email, "unsubscribe", "Client clicked unsubscribe link.")
    
    # Assert suppressed now
    assert service.is_suppressed(email)
    
    # List suppressed
    all_sup = service.list_suppressed()
    assert any(x["email"] == email for x in all_sup)
    
    # Remove suppression
    assert service.remove_email(email)
    assert not service.is_suppressed(email)
