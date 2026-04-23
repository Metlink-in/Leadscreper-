import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def check():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client.get_default_database()
    search = await db.searches.find_one({'search_id': '92bd68663990470d8280d44506fc220a'})
    if not search:
        print("Search not found")
    else:
        print(f"Leads count: {len(search.get('leads', []))}")
        if search.get('leads'):
            print("First lead category:", search['leads'][0].get('category'))
            print("First lead industry:", search['leads'][0].get('industry'))
    client.close()

if __name__ == "__main__":
    asyncio.run(check())
