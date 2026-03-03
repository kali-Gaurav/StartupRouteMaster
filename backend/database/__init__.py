from .session import SessionLocal, engine, get_db, init_db, Base, get_source_connection

# Backward compatibility aliases
engine_write = engine
engine_read = engine # In SQLite local mode, read/write use the same engine
close_db = lambda: None # Placeholder if needed
