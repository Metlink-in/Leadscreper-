import asyncio
from app.services.db_service import db_service

async def check_last_search():
    await db_service.connect()
    if db_service.db is None:
        print("Failed to connect to MongoDB.")
        return

    email = "jiteshbawaskar05@gmail.com"
    user = await db_service.get_user_by_email(email)
    if not user:
        print(f"User {email} not found.")
        return

    user_id = str(user["_id"])
    print(f"Checking searches for user_id: {user_id}")
    
    # Get the latest search
    cursor = db_service.db.searches.find({"user_id": user_id}).sort("created_at", -1).limit(1)
    results = await cursor.to_list(length=1)
    
    if not results:
        print("No searches found for this user.")
    else:
        search = results[0]
        print(f"Latest search ID: {search['_id']}")
        print(f"Status: {search.get('status')}")
        print(f"Lead count: {len(search.get('leads', []))}")
        if search.get('error'):
            print(f"Error: {search.get('error')}")

    await db_service.disconnect()

if __name__ == "__main__":
    asyncio.run(check_last_search())
