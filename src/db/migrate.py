from src.db.models import Base, engine
from sqlalchemy import inspect

def migrate_db():
    """Создает только новые таблицы, не трогая существующие"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print("🔍 Checking database tables...")
    
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            print(f"✅ Creating new table: {table_name}")
            table.create(engine)
        else:
            print(f"ℹ️  Table '{table_name}' already exists")
    
    print("\n✅ Migration completed successfully")

if __name__ == "__main__":
    migrate_db()