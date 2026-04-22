import asyncio, motor.motor_asyncio
client = motor.motor_asyncio.AsyncIOMotorClient('mongodb+srv://jiteshbawaskar_db_user:Jitesh001%40@testingdb.uhk0s36.mongodb.net/')
db = client.leadscraper
async def main():
    print(await db.users.find_one({'email': 'jiteshbawaskar05@gmail.com'}))
asyncio.run(main())