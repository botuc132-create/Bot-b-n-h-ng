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

@app.get("/")
def index(): return send_from_directory("static","index.html")

@app.get("/api/me")
def me():
    u,e=auth_required()
    if e:return e
    with connect() as c:
        user=dict(c.execute("SELECT user_id,username,balance,total_deposit,created_at FROM users WHERE user_id=?",(u["id"],)).fetchone())
    return jsonify(user)

@app.get("/api/products")
def products():
    u,e=auth_required()
    if e:return e
    out=[]
    for key,p in PRODUCTS.items():
        out.append({"key":key,"name":p["name"],"plans":[{"index":i,"label":label,"price":price,"stock":stock,"available":bool(stock)} for i,(label,price,stock) in enumerate(p["plans"])]})
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
    data=request.get_json(silent=True) or {}
    key=data.get("product"); idx=data.get("plan_index")
    p=PRODUCTS.get(key)
    if not p or not isinstance(idx,int) or idx<0 or idx>=len(p["plans"]):
        return jsonify({"error":"Sản phẩm hoặc gói không hợp lệ"}),400
    label,price,stock=p["plans"][idx]
    if stock<=0: return jsonify({"error":"Gói này đã hết hàng"}),409
    # The supplied bot source has no inventory/delivery records or fulfillment flow.
    # Do not debit users or create a falsely successful order without those guarantees.
    return jsonify({"error":"Chưa thể mua tự động an toàn: mã bot hiện chưa có kho hàng và quy trình giao Key/Tài khoản. Không có tiền nào bị trừ."}),409

@app.get("/health")
def health(): return jsonify({"ok":True})

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), threaded=True)
