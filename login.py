from playwright.sync_api import sync_playwright

def login_and_save_state():
    with sync_playwright() as p:
        # Headless dimatikan agar Anda bisa mengetik username/password & melewati CAPTCHA
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="id-ID"
        )
        page = context.new_page()

        print("Menavigasi ke halaman Threads...")
        page.goto("https://www.threads.net/login")

        print("\n" + "="*50)
        print("SILAKAN LOGIN SECARA MANUAL DI BROWSER YANG TERBUKA.")
        print("Jika sudah berhasil masuk dan melihat halaman feed utama,")
        print("kembali ke terminal ini dan tekan ENTER.")
        print("="*50 + "\n")
        
        # Menunggu konfirmasi user
        input("Tekan ENTER di sini jika sudah berhasil login...")

        # Simpan sesi (cookies & local storage) ke file JSON
        context.storage_state(path="auth.json")
        print("✅ Status sesi (cookies) berhasil disimpan di 'auth.json'.")
        
        browser.close()

if __name__ == "__main__":
    login_and_save_state()