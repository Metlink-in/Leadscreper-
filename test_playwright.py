import asyncio
from playwright.async_api import async_playwright

async def run_dom_test():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            print("Playwright chromium not installed. Run 'playwright install chromium'")
            return
            
        page = await browser.new_page()
        
        print("1. Navigating to login...")
        await page.goto("http://localhost:8001/login")
        
        print("2. Logging in...")
        await page.fill("input[type='email']", "jiteshbawaskar05@gmail.com")
        await page.fill("input[type='password']", "Jitesh001@")
        await page.click("button[type='submit']")
        
        print("3. Waiting for dashboard...")
        await page.wait_for_url("http://localhost:8001/")
        
        print("4. Selecting criteria...")
        # Uncheck all categories
        await page.click("a:text('None')")
        # Check specific category
        await page.click("label:has-text('Startups & SMB Clients')")
        
        # Select country
        await page.select_option("#countrySelect", "United States")
        
        # Ensure AI is off for faster test (or leave it on)
        await page.uncheck("#aiToggle")
        
        print("5. Clicking search...")
        await page.click("#searchButton")
        
        print("6. Waiting for polling to finish (max 60s)...")
        # Wait for the loading overlay to be hidden
        await page.wait_for_selector("#loadingOverlay.hidden", timeout=60000)
        
        print("7. Verifying DOM table results...")
        # Get rows in the table body
        rows = await page.query_selector_all("#leadTableBody tr")
        print(f"Found {len(rows)} leads in the DOM.")
        
        if len(rows) > 0:
            for i, row in enumerate(rows[:3]):
                name = await row.eval_on_selector("td:first-child", "el => el.innerText")
                print(f"Lead {i+1} in DOM: {name}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_dom_test())
