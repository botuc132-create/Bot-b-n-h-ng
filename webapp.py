import os, json, hmac, hashlib, time, sqlite3, secrets, urllib.request, urllib.parse
from urllib.parse import parse_qsl
from flask import Flask, jsonify, request, send_from_directory
from bot import TOKEN, DB_PATH, PRODUCTS, now, qr_url, parse_amount

app = Flask(__name__, static_folder="static")

def connect():
    c=sqlite3.connect(DB_PATH, timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=20000")
    c.execute("CREATE TABLE IF NOT EXISTS store_products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS product_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, secret_key TEXT NOT NULL, duration_value INTEGER NOT NULL DEFAULT 1, duration_unit TEXT NOT NULL DEFAULT 'day', status TEXT NOT NULL DEFAULT 'available', sold_to INTEGER, sold_at TEXT, UNIQUE(product_id,secret_key))")
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
    out=[]
    with connect() as c:
        rows=c.execute("SELECT * FROM store_products ORDER BY id DESC").fetchall()
        for p in rows:
            keys=c.execute("SELECT duration_value,duration_unit,COUNT(*) stock FROM product_keys WHERE product_id=? AND status='available' GROUP BY duration_value,duration_unit ORDER BY duration_value",(p['id'],)).fetchall()
            plans=[]
            for i,k in enumerate(keys):
                unit='ngày' if k['duration_unit']=='day' else 'giờ'
                plans.append({'index':i,'duration_value':k['duration_value'],'duration_unit':k['duration_unit'],'label':f"{k['duration_value']} {unit}",'price':p['price'],'stock':k['stock'],'available':k['stock']>0})
            out.append({'key':str(p['id']),'name':p['name'],'price':p['price'],'plans':plans})
    # Keep legacy catalogue visible until the admin creates database products.
    if not out:
        for key,p in PRODUCTS.items():
            out.append({'key':key,'name':p['name'],'plans':[{'index':i,'label':label,'price':price,'stock':stock,'available':bool(stock)} for i,(label,price,stock) in enumerate(p['plans'])]})
    return jsonify(out)

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
    data=request.get_json(silent=True) or {}; key=str(data.get('product','')); idx=data.get('plan_index')
    try: product_id=int(key); idx=int(idx)
    except (ValueError,TypeError): return jsonify({'error':'Sản phẩm/gói không hợp lệ hoặc sản phẩm cũ chưa có kho key.'}),400
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        product=c.execute('SELECT * FROM store_products WHERE id=?',(product_id,)).fetchone()
        if not product:return jsonify({'error':'Không tìm thấy sản phẩm.'}),404
        groups=c.execute("SELECT duration_value,duration_unit,COUNT(*) stock FROM product_keys WHERE product_id=? AND status='available' GROUP BY duration_value,duration_unit ORDER BY duration_value",(product_id,)).fetchall()
        if idx<0 or idx>=len(groups):return jsonify({'error':'Gói không hợp lệ.'}),400
        g=groups[idx]
        user=c.execute('SELECT balance FROM users WHERE user_id=?',(u['id'],)).fetchone()
        if not user or user['balance']<product['price']:return jsonify({'error':'Số dư không đủ.'}),400
        keyrow=c.execute("SELECT id,secret_key FROM product_keys WHERE product_id=? AND status='available' AND duration_value=? AND duration_unit=? ORDER BY id LIMIT 1",(product_id,g['duration_value'],g['duration_unit'])).fetchone()
        if not keyrow:return jsonify({'error':'Gói vừa hết hàng.'}),409
        c.execute("UPDATE product_keys SET status='sold',sold_to=?,sold_at=? WHERE id=? AND status='available'",(u['id'],now(),keyrow['id']))
        c.execute('UPDATE users SET balance=balance-? WHERE user_id=?',(product['price'],u['id']))
        plan=f"{g['duration_value']} {'ngày' if g['duration_unit']=='day' else 'giờ'}"
        c.execute("INSERT INTO purchases(user_id,product,plan,amount,status,created_at) VALUES(?,?,?,?,?,?)",(u['id'],product['name'],plan,product['price'],'completed',now()))
        c.execute("INSERT INTO balance_logs(user_id,admin_id,amount,action,note,created_at) VALUES(?,?,?,?,?,?)",(u['id'],0,-product['price'],'purchase',product['name']+' / '+plan,now()))
    return jsonify({'ok':True,'message':'Mua thành công','product':product['name'],'plan':plan,'key':keyrow['secret_key']})


def admin_required():
    u, error = auth_required()
    if error:
        return None, error
    admins = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
    if u["id"] not in admins:
        return None, (jsonify({"error": "Bạn không có quyền quản trị."}), 403)
    return u, None

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


@app.get("/api/admin/products")
def admin_products():
    u,error=admin_required()
    if error:return error
    with connect() as c:
        rows=[]
        for p in c.execute('SELECT * FROM store_products ORDER BY id DESC').fetchall():
            keys=c.execute("SELECT COUNT(*) total,SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) available,SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) sold FROM product_keys WHERE product_id=?",(p['id'],)).fetchone()
            durations=[dict(r) for r in c.execute("SELECT duration_value,duration_unit,COUNT(*) total,SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) available FROM product_keys WHERE product_id=? GROUP BY duration_value,duration_unit ORDER BY duration_value",(p['id'],))]
            rows.append({'id':p['id'],'name':p['name'],'price':p['price'],'total':keys['total'] or 0,'available':keys['available'] or 0,'sold':keys['sold'] or 0,'durations':durations})
    return jsonify(rows)

@app.post("/api/admin/products")
def admin_add_product():
    u,error=admin_required()
    if error:return error
    d=request.get_json(silent=True) or {}; name=str(d.get('name','')).strip()[:100]
    try: price=int(d.get('price',0))
    except (TypeError,ValueError): return jsonify({'error':'Giá không hợp lệ'}),400
    if not name or price<0:return jsonify({'error':'Nhập tên sản phẩm và giá hợp lệ.'}),400
    with connect() as c: cur=c.execute('INSERT INTO store_products(name,price,created_at) VALUES(?,?,?)',(name,price,now()))
    return jsonify({'ok':True,'id':cur.lastrowid,'message':'Đã thêm sản phẩm. Tiếp theo hãy thêm key và thời hạn.'}),201

@app.post("/api/admin/products/<int:product_id>/keys")
def admin_add_keys():
    u,error=admin_required()
    if error:return error
    d=request.get_json(silent=True) or {}; raw=str(d.get('keys','')); keys=[x.strip() for x in raw.splitlines() if x.strip()]
    try: duration=int(d.get('duration_value',1)); unit=str(d.get('duration_unit','day'))
    except (TypeError,ValueError): return jsonify({'error':'Thời hạn không hợp lệ'}),400
    if not keys:return jsonify({'error':'Nhập ít nhất một key, mỗi dòng một key.'}),400
    if duration<1 or duration>3650 or unit not in ('day','hour'):return jsonify({'error':'Thời hạn phải từ 1 đến 3650 ngày/giờ.'}),400
    added=0
    with connect() as c:
        if not c.execute('SELECT id FROM store_products WHERE id=?',(product_id,)).fetchone():return jsonify({'error':'Không tìm thấy sản phẩm'}),404
        for k in keys:
            try:c.execute("INSERT INTO product_keys(product_id,secret_key,duration_value,duration_unit) VALUES(?,?,?,?)",(product_id,k[:500],duration,unit)); added+=1
            except sqlite3.IntegrityError:pass
    return jsonify({'ok':True,'added':added,'submitted':len(keys),'message':f'Đã thêm {added} key cho gói {duration} {"ngày" if unit=="day" else "giờ"}.'})

@app.patch("/api/admin/products/<int:product_id>")
def admin_edit_product():
    u,error=admin_required()
    if error:return error
    d=request.get_json(silent=True) or {}; name=str(d.get('name','')).strip()[:100]
    try:price=int(d.get('price',0))
    except (TypeError,ValueError):return jsonify({'error':'Giá không hợp lệ'}),400
    if not name or price<0:return jsonify({'error':'Tên/giá không hợp lệ'}),400
    with connect() as c:c.execute('UPDATE store_products SET name=?,price=? WHERE id=?',(name,price,product_id))
    return jsonify({'ok':True,'message':'Đã cập nhật sản phẩm.'})

@app.delete("/api/admin/products/<int:product_id>")
def admin_delete_product():
    u,error=admin_required()
    if error:return error
    with connect() as c:
        if c.execute("SELECT 1 FROM product_keys WHERE product_id=? AND status='sold' LIMIT 1",(product_id,)).fetchone():
            return jsonify({'error':'Sản phẩm đã có giao dịch; không thể xóa hẳn để giữ lịch sử. Hãy sửa tên sản phẩm hoặc xóa các key còn hàng.'}),409
        c.execute('DELETE FROM product_keys WHERE product_id=?',(product_id,)); cur=c.execute('DELETE FROM store_products WHERE id=?',(product_id,))
        if not cur.rowcount:return jsonify({'error':'Không tìm thấy sản phẩm.'}),404
    return jsonify({'ok':True,'message':'Đã xóa sản phẩm và key chưa bán.'})

@app.get("/api/admin/purchases")
def admin_purchases():
    u,error=admin_required()
    if error:return error
    with connect() as c:
        rows=[dict(r) for r in c.execute("SELECT p.id,p.user_id,u.username,p.product,p.plan,p.amount,p.status,p.created_at FROM purchases p LEFT JOIN users u ON u.user_id=p.user_id ORDER BY p.id DESC LIMIT 200")]
    return jsonify(rows)

@app.get("/health")
def health(): return jsonify({"ok":True})

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), threaded=True)
