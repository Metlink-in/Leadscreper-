import asyncio
from fastapi.testclient import TestClient
from app.main import app

def test_admin_update():
    client = TestClient(app)

    # Test GET admin page
    response = client.get("/admin")
    print(f"Admin page status: {response.status_code}")
    print(f"Admin page contains form: {'form' in response.text}")

    # Test POST admin update
    form_data = {
        "search_api_provider": "searchapi",
        "search_api_key": "test_updated_key",
        "serp_api_key": "",
        "gemini_api_key": "test_updated_gemini",
        "openai_api_key": "",
        "app_secret": "test_updated_secret"
    }

    response = client.post("/admin/update", data=form_data, follow_redirects=False)
    print(f"Admin update status: {response.status_code}")
    print(f"Redirect location: {response.headers.get('location', 'None')}")

    # Check if .env was updated
    try:
        with open(".env", "r") as f:
            env_content = f.read()
        print(f".env contains updated key: {'test_updated_key' in env_content}")
        print(f".env contains updated gemini: {'test_updated_gemini' in env_content}")
    except Exception as e:
        print(f"Error reading .env: {e}")

if __name__ == "__main__":
    test_admin_update()