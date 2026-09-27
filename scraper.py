import os
import time
import json
import csv
import random
import re
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
TARGET_URL = os.getenv("TARGET_URL", "https://www.threads.net/@instagram")
MAX_POSTS = int(os.getenv("MAX_POSTS", 30))
AUTH_FILE = "auth.json" # File penyimpan sesi cookies

def clean_text(text):
    if not text:
        return ""
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def parse_metrics(metric_str):
    if not metric_str:
        return 0
    metric_str = metric_str.lower().strip()
    match = re.search(r'([\d\,\.]+)\s*([krmbjt]*)', metric_str)
    if not match:
        return 0
    num_str = match.group(1).replace(',', '.')
    try:
        number = float(num_str)
    except ValueError:
        return 0
    suffix = match.group(2)
    if suffix in ['k', 'rb']:
        number *= 1000
    elif suffix in ['m', 'jt']:
        number *= 1000000
    return int(number)

def scrape_threads():
    extracted_data = []
    seen_urls = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Cek apakah file sesi login tersedia
        if os.path.exists(AUTH_FILE):
            print(f"🔐 Menggunakan sesi login dari {AUTH_FILE}...")
            context = browser.new_context(
                storage_state=AUTH_FILE,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                locale="id-ID"
            )
        else:
            print("⚠️ File auth.json tidak ditemukan! Melanjutkan sebagai Guest (rentan limit).")
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                locale="id-ID"
            )

        page = context.new_page()
        print(f"Menavigasi ke {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_selector('div[data-pressable-container="true"]', timeout=15000)
        
        scroll_attempts = 0
        MAX_SCROLL_ATTEMPTS = 6
        last_post_count = 0
        
        while len(extracted_data) < MAX_POSTS and scroll_attempts < MAX_SCROLL_ATTEMPTS:
            posts = page.query_selector_all('div[data-pressable-container="true"]')
            
            for post in posts:
                if len(extracted_data) >= MAX_POSTS:
                    break
                    
                try:
                    # 1. Tautan dan Username
                    a_tags = post.query_selector_all('a')
                    post_url = ""
                    username = ""
                    for a in a_tags:
                        href = a.get_attribute('href')
                        if href and '/post/' in href:
                            post_url = f"https://www.threads.net{href}"
                        elif href and '/@' in href and not username:
                            username = href.replace('/', '')

                    if not post_url or post_url in seen_urls:
                        continue
                        
                    # 2. Waktu Unggahan
                    time_elem = post.query_selector('time')
                    timestamp = ""
                    timestamp_raw = ""
                    if time_elem:
                        timestamp_raw = time_elem.get_attribute('datetime')
                        if timestamp_raw and 'T' in timestamp_raw:
                            try:
                                dt = datetime.strptime(timestamp_raw[:19], "%Y-%m-%dT%H:%M:%S")
                                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                timestamp = timestamp_raw
                        elif not timestamp:
                            timestamp = time_elem.get_attribute('title') or "Waktu tidak diketahui"
                    else:
                        timestamp = "Waktu tidak diketahui"
                        timestamp_raw = "Tidak ada atribut datetime"
                    
                    # 3. Konten Teks
                    spans_text = post.evaluate('''el => {
                        return Array.from(el.querySelectorAll('span[dir="auto"]'))
                                    .map(s => s.innerText || s.textContent)
                                    .map(t => t.trim())
                                    .filter(t => t.length > 0);
                    }''')
                    
                    clean_content = ""
                    time_ago = ""
                    
                    if len(spans_text) > 0:
                        content_parts = spans_text[1:] 
                        filtered_parts = []
                        ui_keywords = ['suka', 'balas', 'bagikan', 'likes', 'reply', 'share', 'repost', 'kirim']
                        
                        for i, part in enumerate(content_parts):
                            part_lower = part.lower()
                            if i <= 1 and re.match(r'^\d+\s*(detik|menit|jam|hari|minggu|d|h|m|s|w|j|mnt|dtk).*$', part_lower):
                                time_ago = re.sub(r'^(\d+)\s*([a-zA-Z]+.*)$', r'\1 \2', part)
                                continue 
                            if part_lower in ui_keywords:
                                continue
                            filtered_parts.append(part)
                            
                        while filtered_parts:
                            last_part = filtered_parts[-1].lower()
                            if re.match(r'^[\d\,\.]+\s*[krmbjt]*$', last_part):
                                filtered_parts.pop()
                            else:
                                break 
                                
                        raw_combined_content = " ".join(filtered_parts)
                        raw_combined_content = re.sub(r'(?i)\b(terjemahkan|translate|lihat terjemahan|see translation)\b', '', raw_combined_content)
                        clean_content = clean_text(raw_combined_content)
                    
                    # 4. Interaksi/Likes
                    like_count = 0
                    aria_val = ""
                    like_elements = post.query_selector_all('[aria-label*="Suka" i], [aria-label*="Like" i]')
                    for el in like_elements:
                        aria_val = el.get_attribute('aria-label') or ""
                        parsed_aria = parse_metrics(aria_val)
                        if parsed_aria > 0:
                            like_count = parsed_aria
                            break
                        parent_text = el.evaluate('el => el.parentElement ? (el.parentElement.innerText || "") : ""')
                        parsed_parent = parse_metrics(parent_text)
                        if parsed_parent > 0:
                            like_count = parsed_parent
                            break
                            
                    if like_count == 0:
                        full_text = post.evaluate('el => el.innerText')
                        if full_text:
                            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                            for line in reversed(lines[-5:]):
                                if re.match(r'^([\d\,\.]+)\s*([krmbjt]*)\s*(suka|likes)?$', line.lower()):
                                    parsed = parse_metrics(line)
                                    if parsed > 0:
                                        like_count = parsed
                                        aria_val = line
                                        break

                    # 5. Penyusunan Struktur Data
                    raw_spans_text = " ".join(spans_text[1:]) if len(spans_text) > 1 else ""
                    raw_post_data = {
                        "username": username,
                        "timestamp": timestamp_raw if timestamp_raw else timestamp,
                        "content": raw_spans_text,
                        "likes": aria_val if aria_val else str(like_count), 
                        "url": post_url
                    }
                    clean_post_data = {
                        "username": username,
                        "timestamp": timestamp,
                        "time_ago": time_ago,
                        "content": clean_content,
                        "likes": like_count,
                        "url": post_url
                    }
                    
                    extracted_data.append({
                        "raw": raw_post_data,
                        "clean": clean_post_data
                    })
                    seen_urls.add(post_url)
                    
                except Exception as e:
                    continue

            print(f"Terkumpul: {len(extracted_data)}/{MAX_POSTS} post...")
            
            if len(extracted_data) >= MAX_POSTS:
                break
                
            current_post_count = len(seen_urls)
            if current_post_count == last_post_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0 
                last_post_count = current_post_count

            # LOGIKA INFINITE SCROLL 
            previous_height = page.evaluate("document.body.scrollHeight")
            
            try:
                page.evaluate("""
                    () => {
                        let totalHeight = 0;
                        let distance = 300; 
                        let timer = setInterval(() => {
                            let scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if(totalHeight >= scrollHeight - window.innerHeight){
                                clearInterval(timer);
                            }
                        }, 150);
                    }
                """)
                time.sleep(2) 
            except Exception:
                pass

            page.keyboard.press('End')
            
            # Tunda adaptif
            delay = random.uniform(3.0, 5.0) if scroll_attempts > 0 else random.uniform(2.0, 3.5)
            time.sleep(delay)
            
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == previous_height and scroll_attempts > 1:
                page.keyboard.press('PageUp')
                time.sleep(1)
                page.keyboard.press('End')
                time.sleep(2)

        if len(extracted_data) < MAX_POSTS:
            print(f"\n⚠️ INFO: Pengumpulan terhenti. Akun hanya memiliki {len(extracted_data)} post yang tersedia untuk dimuat, tidak mencapai target {MAX_POSTS} post.")
        else:
            print(f"\n✅ Berhasil mengekstrak {MAX_POSTS} post sesuai target.")

        browser.close()
        
    return extracted_data

def save_data(extracted_data):
    if not extracted_data:
        print("Tidak ada data yang disimpan.")
        return
        
    raw_data = [item["raw"] for item in extracted_data]
    clean_data = [item["clean"] for item in extracted_data]
        
    with open('threads_dataset_raw.json', 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=4)
        
    raw_keys = raw_data[0].keys()
    with open('threads_dataset_raw.csv', 'w', encoding='utf-8', newline='') as f:
        dict_writer = csv.DictWriter(f, fieldnames=raw_keys)
        dict_writer.writeheader()
        dict_writer.writerows(raw_data)
        
    with open('threads_dataset_clean.json', 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=4)
        
    clean_keys = clean_data[0].keys()
    with open('threads_dataset_clean.csv', 'w', encoding='utf-8', newline='') as f:
        dict_writer = csv.DictWriter(f, fieldnames=clean_keys)
        dict_writer.writeheader()
        dict_writer.writerows(clean_data)
            
    print("Data mentah disimpan ke: threads_dataset_raw.json & .csv")
    print("Data bersih disimpan ke: threads_dataset_clean.json & .csv")

if __name__ == "__main__":
    data = scrape_threads()
    save_data(data)