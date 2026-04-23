import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    try:
        client = AsyncIOMotorClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
        db = client.get_database('leadscraper')
        user = await db.users.find_one({'email': 'jiteshbawaskar05@gmaiil.com'})
        print('User Keys:', {k: user.get(k) for k in ['search_api_key', 'gemini_api_key'] if user})
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
