# คู่มือเจ้าของโปรเจกต์: ทำให้คนอื่น Clone และเริ่มใช้งานได้ง่าย

เอกสารนี้เป็น checklist สำหรับเจ้าของ `nattakit2580/Agent-Invest` ก่อนส่งลิงก์
ให้ผู้ใช้หรือผู้พัฒนาคนอื่น

## 1. เลือกว่าใครควรเห็น source code

### ทางเลือก A: Public repository

เหมาะเมื่ออนุญาตให้ทุกคนเห็นและ clone source code ได้โดยไม่ต้องขอสิทธิ์

1. เปิดหน้า repository บน GitHub
2. ไปที่ **Settings**
3. เลื่อนลงไปที่ **Danger Zone**
4. เลือก **Change repository visibility**
5. เลือก **Make public** และยืนยันชื่อ repository

ก่อนทำ public ต้องตรวจว่า commit history ไม่มี API key, token, `.env`, ข้อมูลลูกค้า
หรือข้อมูลส่วนตัว เพราะการลบจากไฟล์ล่าสุดไม่ได้ลบข้อมูลออกจาก Git history เดิม

### ทางเลือก B: Private repository

เหมาะเมื่อให้เฉพาะทีม ลูกค้า หรือผู้ร่วมพัฒนาที่เลือกไว้เข้าถึง

1. เปิด **Settings**
2. ไปที่ **Collaborators** หรือ **Collaborators & teams**
3. กด **Add people**
4. ใส่ GitHub username หรืออีเมลของผู้ใช้
5. ให้ผู้ใช้กดรับคำเชิญจาก GitHub

ถ้าเป็น private repository ภายใต้ personal account ผู้ที่ถูกเพิ่มเป็น collaborator
จะมีสิทธิ์ร่วมแก้ไข repository ด้วย จึงควรเชิญเฉพาะคนที่ไว้ใจ

หากผู้ใช้เปิดลิงก์แล้วเห็น `404 Not Found` ให้ตรวจ visibility, คำเชิญ และบัญชี
GitHub ที่กำลัง login อยู่

## 2. เลือก License ก่อนเปิดให้ภายนอกใช้ต่อ

ตอนนี้ repository ยังไม่มี `LICENSE` หากต้องการอนุญาตให้คนนอกนำ source code ไปใช้
แก้ไข หรือแจกจ่าย ควรเลือก license ให้ชัดเจนก่อน

- MIT: ใช้งานและแก้ไขต่อได้กว้าง พร้อมคง copyright/license notice
- Apache-2.0: คล้าย MIT และมีข้อกำหนดด้านสิทธิบัตรเพิ่ม
- Proprietary/custom: เหมาะกับงานลูกค้าหรือ source ที่ไม่ต้องการเปิดสิทธิ์ทั่วไป

การเลือก license เป็นการตัดสินใจด้านสิทธิ์ของเจ้าของโปรเจกต์ ไม่ควรให้ agent เลือก
แทนโดยไม่มีคำยืนยัน

## 3. Push ชุด readiness ขึ้น GitHub

เอกสารและการแก้ไขสำหรับส่งมอบใน working tree ต้องถูก review, commit และ push ก่อน
ผู้ใช้ที่ clone จาก GitHub จึงจะได้รับไฟล์เหล่านี้

ไฟล์สำคัญที่ผู้ใช้ควรเห็นบน GitHub:

- `README.md`
- `QUICKSTART_TH.md`
- `run.bat`
- `setup.ps1` และ `start.ps1`
- `.env.example` และ `backend/.env.example`
- `CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md`, `HANDOFF.md`
- `.github/workflows/ci.yml`

หลัง push ให้รอ GitHub Actions ผ่านทั้ง backend และ frontend ก่อนประกาศให้ผู้ใช้
ดาวน์โหลด

## 4. ทดสอบเหมือนเป็นผู้ใช้ใหม่

1. เปิด repository ด้วย browser แบบ Incognito/Private
2. ยืนยันว่าผู้ใช้เป้าหมายมองเห็น repository
3. กด **Code → Download ZIP**
4. แตกไฟล์ลงโฟลเดอร์ที่ไม่ใช่ OneDrive
5. ดับเบิลคลิก `run.bat`
6. ตรวจ <http://localhost:3000>, <http://localhost:8000/health> และ
   <http://localhost:8000/docs>
7. ยืนยันว่าเริ่มระบบได้โดยไม่ต้องมี API key และ AI ทำงานหลังใส่ OpenRouter key

อย่าทดสอบด้วย `.env`, database หรือ dependency folders จากเครื่องพัฒนาเดิม เพราะ
จะไม่สะท้อนประสบการณ์ของผู้ใช้ที่ clone ใหม่จริง

## 5. จัดหน้า GitHub ให้เข้าใจง่าย

แนะนำให้ตั้งค่าช่อง **About** ของ repository:

- Description: `Self-hosted AI-assisted investment monitoring dashboard`
- Website: URL ของ frontend ที่ deploy แล้ว
- Topics: `fastapi`, `nextjs`, `investment`, `openrouter`, `telegram-bot`,
  `self-hosted`

ตั้ง `QUICKSTART_TH.md` เป็นลิงก์เด่นช่วงต้น README และใส่สถานะ CI หลัง workflow
รันผ่านแล้ว

## 6. ทำ Release สำหรับผู้ใช้ทั่วไป

เมื่อ `main` ผ่าน CI และทดสอบ clean setup แล้ว แนะนำสร้าง GitHub Release เช่น
`v1.0.0` พร้อมข้อความสั้น ๆ:

```text
Agent Invest v1.0.0

Windows quick start:
1. Download Source code (zip)
2. Extract outside OneDrive
3. Install Python 3.11+ and Node.js 20 LTS
4. Double-click run.bat

Full Thai guide: QUICKSTART_TH.md
```

Release ช่วยให้ผู้ใช้ดาวน์โหลด snapshot ที่ระบุเวอร์ชันชัดเจน แทนการดาวน์โหลด
branch ที่เปลี่ยนตลอดเวลา

## ข้อความพร้อมส่งให้ผู้ใช้

```text
ดาวน์โหลด Agent Invest ได้ที่:
https://github.com/nattakit2580/Agent-Invest

ถ้าไม่เคยใช้ Git ให้กด Code → Download ZIP แตกไฟล์ไว้นอก OneDrive แล้ว
ดับเบิลคลิก run.bat

คู่มือภาษาไทยอยู่ในไฟล์ QUICKSTART_TH.md
ต้องมี Python 3.11+ และ Node.js 20 LTS
```

## เอกสารอ้างอิงจาก GitHub

- [การตั้งค่า repository visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [การเชิญ collaborator](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository)
- [การดาวน์โหลด source code เป็น ZIP](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)
