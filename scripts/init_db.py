from backend.database import Base, SessionLocal, engine
from backend.services.seed import seed_database


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)
    print("CodeFlow 数据库已初始化。")

