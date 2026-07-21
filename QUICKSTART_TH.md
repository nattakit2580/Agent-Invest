# เริ่มใช้งาน Agent Invest สำหรับมือใหม่ (Windows)

คู่มือนี้สำหรับผู้ใช้ที่ไม่เคยใช้ Git หรือรันโปรเจกต์ Python/Node.js มาก่อน
วิธีง่ายที่สุดคือดาวน์โหลด ZIP แล้วดับเบิลคลิก `run.bat`

คู่มือ one-click นี้รองรับ Windows หากใช้ macOS หรือ Linux ให้ดูขั้นตอน manual
setup ใน `README.md`

## ก่อนเริ่ม

เตรียมสิ่งต่อไปนี้:

- Windows 10 หรือ 11
- อินเทอร์เน็ตสำหรับดาวน์โหลดโปรแกรมและ dependencies ครั้งแรก
- พื้นที่ว่างอย่างน้อยประมาณ 2 GB
- [Python 3.11 หรือใหม่กว่า](https://www.python.org/downloads/)
  ตอนติดตั้งให้เลือก **Add python.exe to PATH**
- [Node.js 20 LTS](https://nodejs.org/)

ถ้าใช้วิธี Download ZIP ไม่จำเป็นต้องติดตั้ง Git

> แนะนำให้เก็บโปรเจกต์ไว้ที่ `C:\Projects\Agent-Invest` หรือโฟลเดอร์ local
> ปกติ ไม่ควรเก็บใน OneDrive เพราะอาจทำให้ `node_modules` และ `.venv` เสียหาย

## วิธีที่ง่ายที่สุด: Download ZIP

1. เปิด <https://github.com/nattakit2580/Agent-Invest>
2. กดปุ่มสีเขียว **Code**
3. เลือก **Download ZIP**
4. คลิกขวาไฟล์ ZIP แล้วเลือก **Extract All...**
5. ย้ายโฟลเดอร์ที่แตกแล้วไปไว้ที่ `C:\Projects\Agent-Invest`
6. เปิดโฟลเดอร์ แล้วดับเบิลคลิก `run.bat`
7. รอการติดตั้งครั้งแรก อาจใช้เวลาหลายนาทีตามความเร็วอินเทอร์เน็ต
8. เมื่อพร้อม ระบบจะเปิดหน้าเว็บที่ <http://localhost:3000>

จะมีหน้าต่าง command สองหน้าต่างสำหรับ backend และ frontend อย่าปิดระหว่าง
ใช้งาน หาก Windows แสดงคำเตือน ให้ตรวจสอบว่าไฟล์มาจาก repository นี้ก่อนอนุญาต
ให้ทำงาน

ถ้าเปิดลิงก์ GitHub แล้วเจอ `404 Not Found` แปลว่า repository ยังเป็น private
หรือบัญชีของคุณยังไม่ได้รับสิทธิ์ ให้เจ้าของ repository เชิญบัญชี GitHub ของคุณ
ก่อน หรือให้เจ้าของเปลี่ยน repository เป็น public

## การเปิดใช้งานครั้งต่อไป

เปิดโฟลเดอร์เดิมแล้วดับเบิลคลิก `run.bat` อีกครั้ง ระบบจะใช้ environment ที่
ติดตั้งไว้แล้ว ไม่ต้องดาวน์โหลดทุกอย่างใหม่

URL หลัก:

- Dashboard: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- API documentation: <http://localhost:8000/docs>

ถ้า port 3000 ถูกโปรแกรมอื่นใช้อยู่ Next.js อาจเลือก 3001 หรือ port ถัดไป ให้ดู
URL ที่แสดงในหน้าต่าง `Agent Invest - Frontend`

## เปิดใช้ AI analysis (ไม่บังคับ)

Dashboard และฟังก์ชันที่ไม่ใช้ AI สามารถเริ่มได้โดยไม่มี API key แต่การวิเคราะห์
ด้วย AI ต้องใช้ OpenRouter key:

1. สมัครและสร้าง key ที่ <https://openrouter.ai/keys>
2. เปิดไฟล์ `backend\.env` ด้วย Notepad
3. ใส่ key หลังเครื่องหมายเท่ากับในบรรทัดนี้:

```env
OPENROUTER_API_KEY=ใส่_key_ของคุณที่นี่
```

4. บันทึกไฟล์ แล้วปิดและเปิด `run.bat` ใหม่

ห้ามส่งไฟล์ `backend\.env` ให้ผู้อื่น ห้ามโพสต์ API key ใน GitHub รูปภาพ หรือ
ข้อความแชต

## วิธี Clone สำหรับคนที่จะพัฒนาต่อ

ติดตั้ง [Git](https://git-scm.com/download/win) แล้วเปิด PowerShell:

```powershell
cd C:\Projects
git clone https://github.com/nattakit2580/Agent-Invest.git
cd Agent-Invest
.\run.bat
```

ถ้า repository เป็น private ต้องรับคำเชิญและ login GitHub ก่อน ระหว่าง clone
Git Credential Manager อาจเปิด browser เพื่อให้ยืนยันบัญชี

ข้อดีของการ clone คืออัปเดตโปรเจกต์ภายหลังได้ง่าย:

```powershell
cd C:\Projects\Agent-Invest
git pull
.\run.bat
```

ถ้าดาวน์โหลดด้วย ZIP และต้องการอัปเดต ให้ดาวน์โหลด ZIP รุ่นใหม่และแตกเป็น
โฟลเดอร์ใหม่ อย่าคัดลอก `backend\.env` ไปเผยแพร่หรืออัปโหลด

## วิธีหยุดระบบ

ปิดหน้าต่าง `Agent Invest - Backend` และ `Agent Invest - Frontend` หรือกด
`Ctrl+C` ในแต่ละหน้าต่าง

## แก้ปัญหาเบื้องต้น

### ขึ้นว่า Python was not found

ติดตั้ง Python ใหม่และเลือก **Add python.exe to PATH** จากนั้น restart เครื่อง
หรือออกจากระบบ Windows แล้วเข้าใหม่

### ขึ้นว่า Node.js was not found

ติดตั้ง Node.js 20 LTS แล้วเปิด `run.bat` ใหม่

### npm หรือการติดตั้งค้าง/ล้มเหลว

- ตรวจอินเทอร์เน็ตและพื้นที่ว่าง
- ย้ายโปรเจกต์ออกจาก OneDrive
- ดาวน์โหลดหรือ clone โปรเจกต์ใหม่ลง `C:\Projects`
- เปิด `run.bat` อีกครั้ง

### หน้าเว็บไม่เปิด

- รอให้หน้าต่าง frontend แสดงว่า ready
- ดูว่า frontend เปลี่ยนไปใช้ <http://localhost:3001> หรือไม่
- ตรวจว่าไม่ได้ปิดหน้าต่าง backend/frontend

### ต้องการเริ่มใหม่แบบสะอาด

วิธีปลอดภัยที่สุดสำหรับมือใหม่คือเก็บ `backend\.env` ไว้เป็นการส่วนตัว แล้ว
ดาวน์โหลดหรือ clone โปรเจกต์เป็นโฟลเดอร์ใหม่ที่อยู่นอก OneDrive

## ข้อควรรู้

โปรเจกต์นี้เป็น single-tenant dashboard สำหรับ self-host หรือใช้ในทีมที่ไว้ใจ
กัน ยังไม่มีระบบบัญชีผู้ใช้และการแยกข้อมูลหลาย tenant ไม่ควรเปิด backend ให้คน
ทั่วไปบนอินเทอร์เน็ตโดยไม่มีระบบยืนยันตัวตนและ rate limiting เพิ่มเติม
