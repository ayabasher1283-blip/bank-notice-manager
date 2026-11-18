from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# تفعيل الـ CORS لكي تسمح الواجهة بالاتصال بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "dbname": "bank_notifications_db",
    "user": "postgres",
    "password": "Ayota1283$",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("خطأ في الاتصال بقاعدة البيانات:", e)
        return None

class NoticeModel(BaseModel):
    transaction_date: str
    bank_name: str
    transaction_type: str
    amount: float
    sender_account: str = None
    receiver_account: str = None
    receiver_name: str = None
    created_by: str = None

@app.get("/api/notices")
def get_notices():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications ORDER BY id DESC;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"status": "success", "data": rows}

@app.post("/api/notices")
def create_notice(notice: NoticeModel):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    
    try:
        # فحص التكرار
        cursor.execute(
            """
            SELECT * FROM notifications 
            WHERE amount = %s AND transaction_date = %s AND bank_name = %s
            """,
            (notice.amount, notice.transaction_date, notice.bank_name)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            conn.close()
            return {"status": "duplicate", "message": "تنبيه: هذه المعاملة مسجلة مسبقاً في النظام ولا يمكن تكرارها!"}

        # إدخال البيانات مع تحديد اسم كل عمود صراحةً لمنع أي لخبطة في الترتيب
        cursor.execute(
            """
            INSERT INTO notifications 
            (transaction_date, bank_name, transaction_type, amount, sender_account, receiver_account, receiver_name, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                str(notice.transaction_date),
                str(notice.bank_name),
                str(notice.transaction_type),
                float(notice.amount),
                str(notice.sender_account or ''),
                str(notice.receiver_account or ''),
                str(notice.receiver_name or ''),
                str(notice.created_by or '')
            )
        )
        new_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "id": new_id}
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

    # التأكد من إنشاء جدول المستخدمين في قاعدة البيانات
# التأكد من إنشاء جدول المستخدمين في قاعدة البيانات
def init_users_table():
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users_list (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                role VARCHAR(50) DEFAULT 'مدير النظام',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    except Exception as e:
        print("خطأ في إنشاء جدول المستخدمين:", e)
    finally:
        cursor.close()
        conn.close()

# استدعاء الدالة لإنشاء الجدول أول ما يشتغل السيرفر
init_users_table()

class UserSchema(BaseModel):
    username: str
    role: str = "مدير النظام"

@app.post("/api/users")
def add_new_user(user: UserSchema):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users_list (username, role) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING;",
            (user.username, user.role)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "message": "تم حفظ المستخدم بنجاح"}
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/users")
def get_all_users():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users_list;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"status": "success", "data": rows}