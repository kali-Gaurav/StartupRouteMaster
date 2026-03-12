from .session import (
    SessionLocal, 
    SessionUser, 
    SessionTransit, 
    SessionAuth, 
    engine, 
    get_db, 
    init_db, 
    Base, 
    get_source_connection,
    initialize_database_pools
)

# Backward compatibility aliases
engine_write = engine
engine_read = engine # In SQLite local mode, read/write use the same engine
close_db = lambda: None # Placeholder if needed
