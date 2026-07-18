from scripts.init_db import Base, SessionLocal, engine, seed_database


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)
    print("预置项目与 10 条任务已就绪。")

