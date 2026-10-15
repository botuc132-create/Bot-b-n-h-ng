import os, json, hmac, hashlib, time, sqlite3, secrets, urllib.request, urllib.parse
from urllib.parse import parse_qsl
from flask import Flask, jsonify, request, send_from_directory
from bot import TOKEN, DB_PATH, PRODUCTS, now, qr_url, parse_amount

app = Flask(__name__, static_folder="static")

def connect():
    c=sqlite3.connect(DB_PATH, timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=20000")
    return c

def telegram_user():
    raw=request.headers.get("X-Telegram-Init-Data","")
    if not TOKEN or not raw or len(raw)>8192:
        return None
    try:
        pairs=dict(parse_qsl(raw, keep_blank_values=True, strict_parsing=True))
        supplied=pairs.pop("hash")
        auth_date=int(pairs["auth_date"])
        if abs(time.time()-auth_date)>86400: return None
        check="\n".join(f"{k}={v}" for k,v in sorted(pairs.items()))
        secret=hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        expected=hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied): return None
        user=json.loads(pairs["user"])
        uid=int(user["id"])
        return {"id":uid,"username":user.get("username","")}
    except Exception:
        return None

def auth_required():
    u=telegram_user()
    if not u: return None, (jsonify({"error":"Phiên Telegram không hợp lệ. Hãy mở Mini App từ bot."}),401)
    with connect() as c:
        c.execute("INSERT INTO users(user_id,username,balance,total_deposit,created_at) VALUES(?,?,0,0,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",(u["id"],u["username"],now()))
    return u,None



def ensure_catalog():
    """Shared SQLite catalogue and one-time migration for the bot + Mini App."""
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS catalog_products(
            id TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'key',
            name TEXT NOT NULL, image TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS catalog_plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL,
            label TEXT NOT NULL, price INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(product_id) REFERENCES catalog_products(id) ON DELETE CASCADE)""")
        c.execute("""CREATE TABLE IF NOT EXISTS inventory_keys(
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL,
            plan_id INTEGER NOT NULL, secret TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available',
            buyer_id INTEGER, purchase_id INTEGER, created_at TEXT NOT NULL, sold_at TEXT,
            UNIQUE(plan_id,secret))""")
        cols={r['name'] for r in c.execute("PRAGMA table_info(purchases)")}
        if 'delivered_key' not in cols: c.execute("ALTER TABLE purchases ADD COLUMN delivered_key TEXT")
        if 'plan_id' not in cols: c.execute("ALTER TABLE purchases ADD COLUMN plan_id INTEGER")
        if not c.execute("SELECT 1 FROM catalog_products LIMIT 1").fetchone():
            for key,p in PRODUCTS.items():
                c.execute("INSERT OR IGNORE INTO catalog_products(id,kind,name,image,active,created_at) VALUES(?,?,?,?,1,?)",
                          (key,'key',p['name'],'',now()))
                for i,(label,price,stock) in enumerate(p['plans']):
                    # Keep original labels/price; real stock comes from inventory keys.
                    c.execute("INSERT INTO catalog_plans(product_id,label,price,sort_order) VALUES(?,?,?,?)",(key,label,price,i))
        c.commit()

def is_admin_user(uid):
    return int(uid) in {int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}

def admin_required():
    u, error = auth_required()
    if error: return None, error
    if not is_admin_user(u["id"]):
        return None, (jsonify({"error":"Bạn không có quyền quản trị."}),403)
    expected=os.getenv("ADMIN_PASSWORD","Huydz123")
    supplied=request.headers.get("X-Admin-Password","")
    if not expected or not hmac.compare_digest(supplied, expected):
        return None, (jsonify({"error":"Mật khẩu admin không đúng hoặc chưa đăng nhập."}),401)
    return u,None

def catalog_rows():
    ensure_catalog()
    with connect() as c:
        products=c.execute("SELECT * FROM catalog_products WHERE active=1 ORDER BY rowid").fetchall()
        result=[]
        for p in products:
            plans=c.execute("""SELECT p.id,p.label,p.price,
                (SELECT COUNT(*) FROM inventory_keys k WHERE k.plan_id=p.id AND k.status='available') stock
                FROM catalog_plans p WHERE p.product_id=? ORDER BY p.sort_order,p.id""",(p['id'],)).fetchall()
            result.append({"key":p['id'],"kind":p['kind'],"name":p['name'],"image":p['image'],
                           "plans":[{"id":pl['id'],"index":i,"label":pl['label'],"price":pl['price'],
                                     "stock":pl['stock'],"available":pl['stock']>0} for i,pl in enumerate(plans)]})
        return result

ensure_catalog()

@app.get("/")
def index(): return send_from_directory("static","index.html")

@app.get("/api/me")
def me():
    u,e=auth_required()
    if e:return e
    with connect() as c:
        user=dict(c.execute("SELECT user_id,username,balance,total_deposit,created_at FROM users WHERE user_id=?",(u["id"],)).fetchone())
    user["is_admin"] = u["id"] in {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
    return jsonify(user)

@app.get("/api/products")
def products():
    u,e=auth_required()
    if e:return e
    return jsonify(catalog_rows())

@app.get("/api/history")
def history():
    u,e=auth_required()
    if e:return e
    with connect() as c:
        deposits=[dict(r) for r in c.execute("SELECT amount,code,status,created_at,completed_at FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 50",(u["id"],))]
        purchases=[dict(r) for r in c.execute("SELECT product,plan,amount,status,created_at FROM purchases WHERE user_id=? ORDER BY id DESC LIMIT 50",(u["id"],))]
        logs=[dict(r) for r in c.execute("SELECT amount,action,note,created_at FROM balance_logs WHERE user_id=? ORDER BY id DESC LIMIT 50",(u["id"],))]
    return jsonify({"deposits":deposits,"purchases":purchases,"balance_logs":logs})

@app.post("/api/deposits")
def create_deposit():
    u,e=auth_required()
    if e:return e
    data=request.get_json(silent=True) or {}
    try: amount=int(data.get("amount",0))
    except (ValueError,TypeError): return jsonify({"error":"Số tiền không hợp lệ"}),400
    if amount<10000 or amount>50000000: return jsonify({"error":"Số tiền phải từ 10.000đ đến 50.000.000đ"}),400
    code="NAP"+str(u["id"])+secrets.token_hex(4).upper()
    with connect() as c:
        c.execute("INSERT INTO deposits(user_id,amount,code,status,created_at) VALUES(?,?,?,'pending',?)",(u["id"],amount,code,now()))
    # Send the same manual-review request to the configured admins, never credit here.
    admins={int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
    aid=os.getenv("ADMIN_CHAT_ID","").strip()
    if aid.isdigit(): admins.add(int(aid))
    if TOKEN and admins:
        markup={"inline_keyboard":[[{"text":"✅ XÁC NHẬN ĐÃ NHẬN TIỀN","callback_data":"admin_deposit_ok:"+code},{"text":"❌ TỪ CHỐI","callback_data":"admin_deposit_no:"+code}]]}
        msg=f"🆕 YÊU CẦU NẠP TIỀN (Mini App)\\nUser ID: {u['id']}\\nSố tiền: {amount:,}đ\\nNội dung chuyển khoản: {code}\\nTrạng thái: CHỜ XÁC NHẬN\\n\\nKiểm tra giao dịch ngân hàng trước khi xác nhận."
        for admin_id in admins:
            try:
                payload=urllib.parse.urlencode({"chat_id":admin_id,"text":msg,"reply_markup":json.dumps(markup)}).encode()
                urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data=payload),timeout=5).read()
            except Exception:
                app.logger.exception("Cannot notify admin %s",admin_id)
    bank=os.getenv("BANK_ID","ICB"); account=os.getenv("BANK_ACCOUNT","102886882160"); name=os.getenv("BANK_ACCOUNT_NAME","")
    return jsonify({"amount":amount,"code":code,"status":"pending","qr_url":qr_url(amount,code),"bank_id":bank,"account":account,"account_name":name,"message":"Đang chờ admin xác minh. Không tự cộng tiền khi mở QR."}),201

@app.post("/api/purchase")
def purchase():
    u,e=auth_required()
    if e:return e
    ensure_catalog()
    data=request.get_json(silent=True) or {}
    product_id=str(data.get("product",""))
    plan_id=data.get("plan_id")
    if not isinstance(plan_id,int):
        try: plan_id=int(plan_id)
        except (TypeError,ValueError): return jsonify({"error":"Gói không hợp lệ"}),400
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        plan=c.execute("""SELECT pl.*,pr.name product_name,pr.kind FROM catalog_plans pl
                          JOIN catalog_products pr ON pr.id=pl.product_id
                          WHERE pl.id=? AND pl.product_id=? AND pr.active=1""",(plan_id,product_id)).fetchone()
        if not plan:return jsonify({"error":"Không tìm thấy sản phẩm/gói"}),404
        key=c.execute("SELECT * FROM inventory_keys WHERE plan_id=? AND status='available' ORDER BY id LIMIT 1",(plan_id,)).fetchone()
        if not key:return jsonify({"error":"Gói này đã hết key trong kho."}),409
        user=c.execute("SELECT balance FROM users WHERE user_id=?",(u["id"],)).fetchone()
        if not user or user["balance"]<plan["price"]:
            return jsonify({"error":"Số dư không đủ. Vui lòng nạp tiền."}),402
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?",(plan["price"],u["id"]))
        cur=c.execute("INSERT INTO purchases(user_id,product,plan,amount,status,created_at,delivered_key,plan_id) VALUES(?,?,?,?,?,?,?,?)",
            (u["id"],plan["product_name"],plan["label"],plan["price"],"completed",now(),key["secret"],plan_id))
        c.execute("UPDATE inventory_keys SET status='sold',buyer_id=?,purchase_id=?,sold_at=? WHERE id=? AND status='available'",
                  (u["id"],cur.lastrowid,now(),key["id"]))
        c.execute("INSERT INTO balance_logs(user_id,admin_id,amount,action,note,created_at) VALUES(?,?,?,?,?,?)",
                  (u["id"],0,plan["price"],"purchase",plan["product_name"]+" / "+plan["label"],now()))
    return jsonify({"ok":True,"message":"Mua thành công. Key đã được cấp.","key":key["secret"],"product":plan["product_name"],"plan":plan["label"],"amount":plan["price"]}),201


@app.get("/api/admin")
def admin_stats():
    u, error = admin_required()
    if error: return error
    with connect() as c:
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        balance = c.execute("SELECT COALESCE(SUM(balance),0) n FROM users").fetchone()["n"]
        confirmed = c.execute("SELECT COALESCE(SUM(amount),0) n FROM deposits WHERE status='confirmed'").fetchone()["n"]
        pending_count = c.execute("SELECT COUNT(*) n FROM deposits WHERE status='pending'").fetchone()["n"]
        pending_amount = c.execute("SELECT COALESCE(SUM(amount),0) n FROM deposits WHERE status='pending'").fetchone()["n"]
    return jsonify({"users":users,"balance":balance,"confirmed":confirmed,"pending_count":pending_count,"pending_amount":pending_amount})

@app.get("/api/admin/deposits")
def admin_deposits():
    u, error = admin_required()
    if error: return error
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT id,user_id,amount,code,status,created_at,completed_at FROM deposits ORDER BY id DESC LIMIT 100")]
    return jsonify(rows)

@app.post("/api/admin/deposit")
def admin_decide_deposit():
    u, error = admin_required()
    if error: return error
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", ""))[:100]
    status = data.get("status")
    if not code or status not in ("confirmed", "rejected"):
        return jsonify({"error":"Yêu cầu không hợp lệ."}), 400
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r = c.execute("SELECT * FROM deposits WHERE code=?", (code,)).fetchone()
        if not r:
            return jsonify({"error":"Không tìm thấy giao dịch."}), 404
        if r["status"] != "pending":
            return jsonify({"error":"Giao dịch đã được xử lý trước đó."}), 409
        c.execute("UPDATE deposits SET status=?,completed_at=? WHERE code=? AND status='pending'", (status, now(), code))
        if status == "confirmed":
            c.execute("UPDATE users SET balance=balance+?,total_deposit=total_deposit+? WHERE user_id=?", (r["amount"], r["amount"], r["user_id"]))
            c.execute("INSERT INTO balance_logs(user_id,admin_id,amount,action,note,created_at) VALUES(?,?,?,?,?,?)", (r["user_id"],u["id"],r["amount"],"deposit",code,now()))
    return jsonify({"ok":True,"message":"Đã xác nhận và cộng tiền." if status == "confirmed" else "Đã từ chối yêu cầu nạp."})


@app.post("/api/admin/products")
def admin_add_product():
    u,error=admin_required()
    if error:return error
    data=request.get_json(silent=True) or {}
    name=str(data.get("name","")).strip()[:120]
    kind=str(data.get("kind","key"))
    image=str(data.get("image",""))
    if not name:return jsonify({"error":"Vui lòng nhập tên sản phẩm."}),400
    if kind not in ("key","certificate","account"):return jsonify({"error":"Loại sản phẩm không hợp lệ."}),400
    if len(image)>1500000:return jsonify({"error":"Ảnh quá lớn, hãy chọn ảnh nhỏ hơn 1 MB."}),413
    pid="p_"+secrets.token_hex(6)
    with connect() as c:
        c.execute("INSERT INTO catalog_products(id,kind,name,image,active,created_at) VALUES(?,?,?,?,1,?)",(pid,kind,name,image,now()))
        label=str(data.get("plan_label","1 Key")).strip()[:80] or "1 Key"
        try: price=max(0,int(data.get("price",0)))
        except (TypeError,ValueError): return jsonify({"error":"Giá không hợp lệ."}),400
        c.execute("INSERT INTO catalog_plans(product_id,label,price,sort_order) VALUES(?,?,?,0)",(pid,label,price))
        plan_id=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        keys=data.get("keys",[])
        if isinstance(keys,str): keys=keys.splitlines()
        clean=list(dict.fromkeys(str(k).strip() for k in keys if str(k).strip()))
        if len(clean)>5000:return jsonify({"error":"Tối đa 5000 key mỗi lần."}),400
        for secret in clean:
            c.execute("INSERT OR IGNORE INTO inventory_keys(product_id,plan_id,secret,status,created_at) VALUES(?,?,?,'available',?)",(pid,plan_id,secret,now()))
    return jsonify({"ok":True,"message":f"Đã thêm sản phẩm và {len(clean)} key.","product_id":pid,"keys_added":len(clean)}),201

@app.patch("/api/admin/products/<product_id>")
def admin_edit_product(product_id):
    u,error=admin_required()
    if error:return error
    data=request.get_json(silent=True) or {}
    with connect() as c:
        p=c.execute("SELECT id FROM catalog_products WHERE id=?",(product_id,)).fetchone()
        if not p:return jsonify({"error":"Không tìm thấy sản phẩm."}),404
        if "name" in data:
            name=str(data["name"]).strip()[:120]
            if not name:return jsonify({"error":"Tên không được để trống."}),400
            c.execute("UPDATE catalog_products SET name=? WHERE id=?",(name,product_id))
        if "image" in data:
            image=str(data["image"])
            if len(image)>1500000:return jsonify({"error":"Ảnh quá lớn."}),413
            c.execute("UPDATE catalog_products SET image=? WHERE id=?",(image,product_id))
        if "active" in data:c.execute("UPDATE catalog_products SET active=? WHERE id=?",(1 if data["active"] else 0,product_id))
        if "plan_id" in data:
            try: price=max(0,int(data.get("price",0)))
            except (TypeError,ValueError):return jsonify({"error":"Giá không hợp lệ."}),400
            c.execute("UPDATE catalog_plans SET price=? WHERE id=? AND product_id=?",(price,int(data["plan_id"]),product_id))
    return jsonify({"ok":True,"message":"Đã cập nhật."})

@app.delete("/api/admin/products/<product_id>")
def admin_delete_product(product_id):
    u,error=admin_required()
    if error:return error
    with connect() as c:
        exists=c.execute("SELECT 1 FROM catalog_products WHERE id=?",(product_id,)).fetchone()
        if not exists:return jsonify({"error":"Không tìm thấy sản phẩm."}),404
        c.execute("UPDATE catalog_products SET active=0 WHERE id=?",(product_id,))
    return jsonify({"ok":True,"message":"Đã ẩn/xóa sản phẩm khỏi cửa hàng."})

@app.post("/api/admin/products/<product_id>/keys")
def admin_add_keys(product_id):
    u,error=admin_required()
    if error:return error
    data=request.get_json(silent=True) or {}
    keys=data.get("keys","")
    if isinstance(keys,str):keys=keys.splitlines()
    clean=list(dict.fromkeys(str(k).strip() for k in keys if str(k).strip()))
    if not clean:return jsonify({"error":"Chưa nhập key nào."}),400
    with connect() as c:
        p=c.execute("SELECT id FROM catalog_products WHERE id=? AND active=1",(product_id,)).fetchone()
        if not p:return jsonify({"error":"Không tìm thấy sản phẩm."}),404
        plan_id=data.get("plan_id")
        if plan_id:
            plan=c.execute("SELECT id FROM catalog_plans WHERE id=? AND product_id=?",(int(plan_id),product_id)).fetchone()
        else:plan=c.execute("SELECT id FROM catalog_plans WHERE product_id=? ORDER BY sort_order,id LIMIT 1",(product_id,)).fetchone()
        if not plan:return jsonify({"error":"Sản phẩm chưa có gói."}),400
        added=0
        for secret in clean:
            cur=c.execute("INSERT OR IGNORE INTO inventory_keys(product_id,plan_id,secret,status,created_at) VALUES(?,?,?,'available',?)",(product_id,plan["id"],secret,now()))
            added+=cur.rowcount
    return jsonify({"ok":True,"keys_added":added,"message":f"Đã thêm {added} key."})

@app.get("/api/admin/buyer-history")
def admin_buyer_history():
    u,error=admin_required()
    if error:return error
    with connect() as c:
        rows=[dict(r) for r in c.execute("""SELECT pu.id,pu.user_id,u.username,pu.product,pu.plan,pu.amount,pu.status,
            pu.created_at,pu.delivered_key FROM purchases pu LEFT JOIN users u ON u.user_id=pu.user_id
            ORDER BY pu.id DESC LIMIT 200""")]
    return jsonify(rows)

@app.get("/api/admin/catalog")
def admin_catalog():
    u,error=admin_required()
    if error:return error
    return jsonify(catalog_rows())

@app.get("/health")
def health(): return jsonify({"ok":True})

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), threaded=True)
