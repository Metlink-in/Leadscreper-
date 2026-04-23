import asyncio
from app.services.db_service import db_service
from app.services.auth_service import get_password_hash
from app.config import settings

async def main():
    await db_service.connect()
    if db_service.db is None:
        print("Failed to connect to MongoDB Atlas.")
        return

    email = "jiteshbawaskar05@gmail.com"
    password = "Jitesh001@"

    # Check if user exists
    existing = await db_service.get_user_by_email(email)
    if existing:
        print(f"User {email} already exists in Atlas.")
        # Ensure keys are copied from .env if missing
        update_data = {}
        if not existing.get("search_api_key"):
            update_data["search_api_key"] = settings.search_api_key
        if not existing.get("gemini_api_key"):
            update_data["gemini_api_key"] = settings.gemini_api_key
        
        if update_data:
            await db_service.update_user(email, update_data)
            print("Updated user with API keys from .env")
    else:
        user_data = {
            "name": "Jitesh Bawaskar",
            "email": email,
            "password_hash": get_password_hash(password),
            "search_api_key": settings.search_api_key,
            "gemini_api_key": settings.gemini_api_key,
            "openai_api_key": None
        }
        success = await db_service.create_user(user_data)
        if success:
            print(f"User {email} successfully created in Atlas.")
        else:
            print(f"Failed to create user {email}.")

    # Also add the gmaiil.com typo just in case since they used it before
    email2 = "jiteshbawaskar05@gmaiil.com"
    existing2 = await db_service.get_user_by_email(email2)
    if not existing2:
        user_data2 = {
            "name": "Jitesh Bawaskar",
            "email": email2,
            "password_hash": get_password_hash(password),
            "search_api_key": settings.search_api_key,
            "gemini_api_key": settings.gemini_api_key,
            "openai_api_key": None
        }
        await db_service.create_user(user_data2)
        print(f"User {email2} successfully created in Atlas as fallback.")

    await db_service.disconnect()

asyncio.run(main())
