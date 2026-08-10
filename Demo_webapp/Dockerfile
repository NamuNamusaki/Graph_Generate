# 1 Base Image
FROM python:3.11-slim

#2 ตั้งค่า working directory
WORKDIR /app .

# 3 คัดลอกไฟล์ที่จะเป็น
COPY requirements.txt .

# ติดตั้ง library in image
RUN pip install --no-cache-dir -r requirements.txt

# 5 คัดลอกโค้ดเข้า Image
COPY . .

# 6 กำหนด port ที่ streamlitใช้
EXPOSE 8501

# 6 คำสั่งที่รันเมื่อ Container เริ่มทำงาน
CMD ["streamlit","run","app.py","--server.port=8501","--server.address=0.0.0.0"]