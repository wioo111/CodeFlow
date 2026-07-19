from backend.database import Base, engine
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("CodeFlow 审校数据库已初始化。请通过导入页面添加 Schema 和数据。")
