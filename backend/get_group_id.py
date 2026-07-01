"""
ดึง chat ID ของกลุ่ม Telegram ทั้งหมดที่บอทเห็น
วิธีใช้:  python get_group_id.py <BOT_TOKEN>
ก่อนรัน: 1) เพิ่มบอทเข้ากลุ่ม  2) พิมพ์ข้อความอะไรก็ได้ในกลุ่ม 1 ครั้ง
"""
import sys
import json
import urllib.request

def main():
    token = sys.argv[1] if len(sys.argv) > 1 else input("วาง BOT TOKEN: ").strip()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)

    if not data.get("ok"):
        print("ERROR:", data)
        return

    seen = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member") or {}
        chat = msg.get("chat")
        if chat:
            seen[chat["id"]] = chat

    if not seen:
        print("ยังไม่เจอกลุ่ม — เพิ่มบอทเข้ากลุ่มแล้วพิมพ์ข้อความในกลุ่ม 1 ครั้ง แล้วรันใหม่")
        return

    print("\n=== กลุ่ม/แชทที่บอทเห็น ===")
    for cid, chat in seen.items():
        title = chat.get("title") or chat.get("username") or chat.get("first_name") or "?"
        print(f"  chat_id = {cid}   |   ชนิด: {chat.get('type')}   |   ชื่อ: {title}")

if __name__ == "__main__":
    main()
