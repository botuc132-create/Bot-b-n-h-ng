import os, re, secrets, logging, sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as K, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip(); DB_PATH=os.getenv('DB_PATH','bot_data.sqlite3')
ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD','huydz123')
ADMIN_IDS={int(x.strip()) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
BANK_ID=os.getenv('BANK_ID','ICB').strip(); BANK_ACCOUNT=os.getenv('BANK_ACCOUNT','102886882160').strip(); BANK_ACCOUNT_NAME=os.getenv('BANK_ACCOUNT_NAME','').strip()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s'); log=logging.getLogger('bot')

PLANS=[('1 Ngày • 20.000đ • CÒN 10',20000,10),('❌ 7 Ngày • HẾT HÀNG',70000,0),('❌ 30 Ngày • HẾT HÀNG',200000,0)]
PRODUCTS={k:{'name':n,'plans':PLANS} for k,n in [
 ('innova','🟢 iNNOVA Cheat'),('aim','🧟 Aim Hack - iOS/Android'),('migul_lite','🎮 Migul AOV Lite'),('boxvip','👑 Box ViP iMZ-Filza'),('aimkill','📱 iPA Aimkill Đình Hoàng'),('drip','🟣 Drip Wire - iOS/Android'),('flork_external','🐵 iPA Flork External'),('flork_tipa','🐵 Flork TiPA (iOS14-16.7.16)'),('migul_pro','🎮 Migul AOV Pro'),('migul_basic','📱 Migul Basic - VietNam Version')]}

def now(): return datetime.now(timezone.utc).isoformat()
def db():
 c=sqlite3.connect(DB_PATH,timeout=20); c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,balance INTEGER DEFAULT 0,total_deposit INTEGER DEFAULT 0,created_at TEXT)')
 c.execute("CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount INTEGER,code TEXT UNIQUE,status TEXT DEFAULT 'pending',created_at TEXT,completed_at TEXT)")
 c.execute('CREATE TABLE IF NOT EXISTS balance_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,admin_id INTEGER,amount INTEGER,action TEXT,note TEXT,created_at TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,product TEXT,plan TEXT,amount INTEGER,status TEXT,created_at TEXT)'); c.commit(); return c
def ensure(u):
 with db() as c: c.execute('INSERT INTO users VALUES(?,?,0,0,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username',(u.id,u.username or '',now()))
def getuser(uid):
 with db() as c: r=c.execute('SELECT * FROM users WHERE user_id=?',(uid,)).fetchone()
 return dict(r) if r else {'user_id':uid,'username':'','balance':0,'total_deposit':0}
def kb(rows): return K([[B(label,callback_data=cb) for label,cb in row] for row in rows])
def main_kb(): return kb([[('👤 TÀI KHOẢN','account'),('🛍 CỬA HÀNG','shop')],[('💰 NẠP TIỀN','deposit'),('📊 LỊCH SỬ','history')],[('📥 TẢI FILE','files'),('💬 HỖ TRỢ','support')],[('🌟 MỞ MINI APP','miniapp')]])
def back(target='home'): return kb([[('QUAY LẠI',target)]])
def admin_kb(): return kb([[('📊 THỐNG KÊ BOT','admin_stats')],[('➕ CỘNG TIỀN USER','admin_add_start'),('➖ TRỪ TIỀN USER','admin_sub_start')],[('🔎 KIỂM TRA USER','admin_check')],[('🏠 MENU CHÍNH','home')]])
def deposit_kb():
 amounts=[(10000,'10.000Đ'),(20000,'20.000Đ'),(50000,'50.000Đ'),(100000,'100.000Đ'),(200000,'200.000Đ'),(500000,'500.000Đ')]
 rows=[]
 for i in range(0,len(amounts),2): rows.append([(label,'amount:'+str(a)) for a,label in amounts[i:i+2]])
 rows.append([('✏️ SỐ TIỀN KHÁC','amount_custom'),('QUAY LẠI','home')]); return kb(rows)
async def show(q,text,markup):
 await q.answer()
 try: await q.edit_message_text(text,reply_markup=markup)
 except Exception: await q.message.reply_text(text,reply_markup=markup)
def qr_url(amount,code):
 if not (BANK_ID and BANK_ACCOUNT): return None
 url=f'https://img.vietqr.io/image/{quote(BANK_ID)}-{quote(BANK_ACCOUNT)}-vietqr_pro.svg?amount={amount}&addInfo={quote(code)}'
 if BANK_ACCOUNT_NAME: url+='&accountName='+quote(BANK_ACCOUNT_NAME)
 return url
async def create_deposit(context,chat_id,user,amount):
 code='NAP'+str(user.id)+secrets.token_hex(3).upper()
 with db() as c: c.execute("INSERT INTO deposits(user_id,amount,code,status,created_at) VALUES(?,?,?,'pending',?)",(user.id,amount,code,now()))
 url=qr_url(amount,code)
 text=f'💰 NẠP TIỀN TỰ ĐỘNG\n\n💵 Số tiền: {amount:,}đ\n🧾 Nội dung chuyển khoản: {code}\n'
 if BANK_ID and BANK_ACCOUNT: text+=f'🏦 Ngân hàng: {BANK_ID}\n💳 STK: {BANK_ACCOUNT}\n'+(f'👤 Chủ tài khoản: {BANK_ACCOUNT_NAME}\n' if BANK_ACCOUNT_NAME else '')
 else: text+='⚠️ Admin chưa cấu hình BANK_ID, BANK_ACCOUNT và BANK_ACCOUNT_NAME trên Railway nên chưa tạo được QR.\n'
 text+='\nChuyển khoản đúng số tiền và nội dung. Đơn đang chờ xác nhận. QR tự tạo không tự xác minh giao dịch; muốn tự cộng trong 1 phút cần tích hợp API/webhook đối soát ngân hàng.'
 try:
  if url: await context.bot.send_photo(chat_id,photo=url,caption=text)
  else: await context.bot.send_message(chat_id,text)
 except Exception as e: log.warning('QR send failed: %s',e); await context.bot.send_message(chat_id,text)
 admins=set(ADMIN_IDS); aid=os.getenv('ADMIN_CHAT_ID','').strip()
 if aid.isdigit(): admins.add(int(aid))
 created_local=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%d/%m/%Y %H:%M:%S')
 admin_text=f'🆕 YÊU CẦU NẠP TIỀN\nUser ID: {user.id}\nUsername: @{user.username or "không có"}\nSố tiền: {amount:,}đ\nNội dung chuyển khoản: {code}\nThời gian tạo: {created_local} (GMT+7)\nTrạng thái: CHỜ XÁC NHẬN\n\nHãy kiểm tra biến động số dư ngân hàng trước khi bấm xác nhận.'
 admin_k=kb([[('✅ XÁC NHẬN ĐÃ NHẬN TIỀN','admin_deposit_ok:'+code),('❌ TỪ CHỐI','admin_deposit_no:'+code)]])
 for aid in admins:
  try: await context.bot.send_message(aid,admin_text,reply_markup=admin_k)
  except Exception as e: log.warning('Admin notification failed: %s',e)
def parse_amount(raw):
 s=raw.lower().replace('đ','').replace('vnd','').replace(' ','').strip()
 if not s: raise ValueError
 if s.endswith('k'):
  amount=int(float(s[:-1].replace(',','.'))*1000)
 else:
  amount=int(re.sub(r'[.,]','',s))
 if amount < 10000 or amount > 50000000: raise ValueError
 return amount

async def nap_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 u=update.effective_user
 ensure(u)
 if not context.args:
  await update.message.reply_text('Cách dùng: /nap 15000 hoặc /nap 15k\\nSố tiền tối thiểu 10.000đ.')
  return
 try:
  amount=parse_amount(''.join(context.args))
 except Exception:
  await update.message.reply_text('Số tiền không hợp lệ. Ví dụ: /nap 15000 hoặc /nap 15k (tối thiểu 10.000đ).')
  return
 await create_deposit(context,update.effective_chat.id,u,amount)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
 u=update.effective_user; ensure(u); bal=getuser(u.id)['balance']
 await update.message.reply_text('Chào Mừng Đến Với Bot MinhOS - Store Hack Auto Bán Hàng Tự Động 24/7\n\n📢 Kênh thông báo: @minhiosbanhacks1\n🌨 Admin: @minhiosne\n━━━━━━━━━━━━━━\n📌 Tổng nạp: 0đ\n🏅 Tổng nạp tháng: 0đ\n🏦 Số dư: {:,}đ\n\nVui lòng chọn chức năng bên dưới.'.format(bal),reply_markup=main_kb())
async def admin_cmd(update,context):
 if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
  await update.message.reply_text('⛔ Bạn không có quyền admin. Hãy kiểm tra ADMIN_IDS trên Railway: nhập Telegram ID dạng số, không phải username.'); return
 context.user_data['await_pass']=True; await update.message.reply_text('🔐 Nhập mật khẩu admin:')
async def report(update,uid):
 u=getuser(uid)
 with db() as c:
  ds=c.execute('SELECT amount,code,status FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 10',(uid,)).fetchall(); ps=c.execute('SELECT product,plan,amount,status FROM purchases WHERE user_id=? ORDER BY id DESC LIMIT 10',(uid,)).fetchall(); logs=c.execute('SELECT amount,action,note FROM balance_logs WHERE user_id=? ORDER BY id DESC LIMIT 10',(uid,)).fetchall()
 lines=[f'🔎 THÔNG TIN USER\nUID: {uid}\nUsername: @{u["username"] or "không có"}\nSố dư: {u["balance"]:,}đ\nTổng nạp đã xác nhận: {u["total_deposit"]:,}đ','','💰 LỊCH SỬ NẠP:']
 lines += [f'• {r["amount"]:,}đ | {r["status"]} | {r["code"]}' for r in ds] or ['• Chưa có']; lines+=['','🛍 LỊCH SỬ MUA:']; lines += [f'• {r["product"]} | {r["plan"]} | {r["amount"]:,}đ | {r["status"]}' for r in ps] or ['• Chưa có']; lines+=['','🧾 LỊCH SỬ CỘNG/TRỪ:']; lines += [f'• {r["action"]} {r["amount"]:,}đ | {r["note"] or ""}' for r in logs] or ['• Chưa có']
 await update.message.reply_text('\n'.join(lines),reply_markup=kb([[('➕ CỘNG TIỀN',f'admin_add:{uid}'),('➖ TRỪ TIỀN',f'admin_sub:{uid}')],[('QUAY LẠI ADMIN','admin_home')]]))
async def messages(update:Update,context:ContextTypes.DEFAULT_TYPE):
 u=update.effective_user; text=(update.message.text or '').strip()
 if context.user_data.pop('await_pass',False):
  if secrets.compare_digest(text,ADMIN_PASSWORD): context.user_data['admin_ok']=True; await update.message.reply_text('✅ Đăng nhập admin thành công.',reply_markup=admin_kb())
  else: await update.message.reply_text('❌ Sai mật khẩu admin.')
  return
 action=context.user_data.get('admin_action')
 if context.user_data.get('admin_ok') and action:
  if action in ('add_amount','sub_amount'):
   try: amount=int(re.sub(r'[.,\s]','',text)); assert amount>0
   except Exception: await update.message.reply_text('Số tiền không hợp lệ, nhập số nguyên dương:'); return
   context.user_data['admin_amount']=amount; context.user_data['admin_action']='add_uid' if action=='add_amount' else 'sub_uid'; await update.message.reply_text('Nhập Telegram ID người dùng:'); return
  if action in ('add_uid','sub_uid'):
   try: uid=int(text)
   except ValueError: await update.message.reply_text('ID không hợp lệ, nhập ID dạng số:'); return
   amount=context.user_data.pop('admin_amount',0); delta=amount if action=='add_uid' else -amount
   with db() as c:
    c.execute('INSERT OR IGNORE INTO users(user_id,username,balance,total_deposit,created_at) VALUES(?,"",0,0,?)',(uid,now())); old=c.execute('SELECT balance FROM users WHERE user_id=?',(uid,)).fetchone()['balance']; new=old+delta
    if new<0: context.user_data.pop('admin_action',None); await update.message.reply_text('Không thể trừ tiền vì số dư sẽ âm.',reply_markup=admin_kb()); return
    c.execute('UPDATE users SET balance=? WHERE user_id=?',(new,uid)); c.execute('INSERT INTO balance_logs(user_id,admin_id,amount,action,note,created_at) VALUES(?,?,?,?,?,?)',(uid,u.id,amount,'admin_add' if delta>0 else 'admin_subtract','Điều chỉnh bởi admin',now()))
   context.user_data.pop('admin_action',None); await update.message.reply_text(f'✅ Đã cập nhật ID {uid}. Số dư mới: {new:,}đ',reply_markup=admin_kb())
   try: await context.bot.send_message(uid,f'💳 Số dư được admin điều chỉnh. Số dư mới: {new:,}đ')
   except Exception: pass
   return
  if action=='check_uid':
   try: uid=int(text)
   except ValueError: await update.message.reply_text('ID không hợp lệ, nhập ID dạng số:'); return
   context.user_data.pop('admin_action',None); await report(update,uid); return
 if context.user_data.get('custom_amount'):
  context.user_data['custom_amount']=False
  try: amount=parse_amount(text)
  except Exception: await update.message.reply_text('Số tiền không hợp lệ. Nhập từ 10.000đ trở lên, ví dụ 50000 hoặc 50k.'); return
  await create_deposit(context,update.effective_chat.id,u,amount)
async def cb(update:Update,context:ContextTypes.DEFAULT_TYPE):
 q=update.callback_query; d=q.data; u=update.effective_user; ensure(u)
 if d.startswith('admin_') and ADMIN_IDS and u.id not in ADMIN_IDS: await q.answer('Bạn không có quyền admin.',show_alert=True); return
 if d.startswith('admin_') and not context.user_data.get('admin_ok'): await q.answer('Hãy đăng nhập bằng /admin trước.',show_alert=True); return
 if d=='home': await show(q,'🏠 MENU CHÍNH\n\nVui lòng chọn chức năng:',main_kb())
 elif d=='account':
  x=getuser(u.id); await show(q,f'👤 THÔNG TIN CÁ NHÂN\n\n🆔 UID: {u.id}\n🍊 Username: @{x["username"] or "chưa_có_username"}\n💰 Số dư: {x["balance"]:,}đ\n🌐 Ngôn ngữ: TIẾNG VIỆT 🇻🇳',back())
 elif d=='shop': await show(q,'🛍 CỬA HÀNG\n\nChọn mục bạn muốn mua:',kb([[('🔑 MUA KEY','buy_key')],[('🛍 MUA TÀI KHOẢN','buy_account')],[('QUAY LẠI','home')]]))
 elif d in ('buy_account','buy_key'):
  rows=[[(p['name'],'app:'+key)] for key,p in PRODUCTS.items()]+[[('QUAY LẠI','shop')]]; await show(q,('📱 CHỌN ỨNG DỤNG' if d=='buy_account' else '🔑 CHỌN LOẠI KEY')+'\n\nChọn sản phẩm bạn muốn mua:',kb(rows))
 elif d.startswith('app:'):
  key=d.split(':',1)[1]; p=PRODUCTS.get(key)
  if not p: await show(q,'Không tìm thấy sản phẩm.',back('buy_account')); return
  rows=[[(label, f'plan:{key}:{i}' if stock else 'soldout')] for i,(label,price,stock) in enumerate(p['plans'])]+[[('QUAY LẠI','buy_account')]]; await show(q,p['name']+'\n\nChọn gói bạn muốn mua:',kb(rows))
 elif d.startswith('plan:'):
  _,key,i=d.split(':'); label,price,stock=PRODUCTS[key]['plans'][int(i)]
  if not stock: await show(q,'❌ Gói này hiện đã hết hàng.',back('app:'+key)); return
  with db() as c: c.execute('INSERT INTO purchases(user_id,product,plan,amount,status,created_at) VALUES(?,?,?,?,?,?)',(u.id,PRODUCTS[key]['name'],label,price,'pending',now()))
  await show(q,f'🛒 YÊU CẦU MUA ĐÃ GHI NHẬN\n\n{PRODUCTS[key]["name"]}\n{label}\nGiá: {price:,}đ\n\nBản mẫu chưa kết nối thanh toán/kho hàng tự giao.',kb([[('QUAY LẠI','app:'+key)],[('VỀ CỬA HÀNG','shop')]]))
 elif d=='soldout': await show(q,'❌ Gói này hiện đã hết hàng.',back('buy_account'))
 elif d=='deposit': await show(q,'💰 NẠP TIỀN TỰ ĐỘNG\n\nChọn số tiền muốn nạp (tối thiểu 10.000đ).\nChuyển khoản xong hệ thống chỉ tự cộng khi đã tích hợp API/webhook xác minh giao dịch.',deposit_kb())
 elif d.startswith('amount:'): await q.answer(); await create_deposit(context,q.message.chat_id,u,int(d.split(':')[1]))
 elif d=='amount_custom': await q.answer(); context.user_data['custom_amount']=True; await q.message.reply_text('✏️ Nhập số tiền muốn nạp (tối thiểu 10.000đ).\nVí dụ: 50000 hoặc 50k')
 elif d=='history':
  with db() as c: ds=c.execute('SELECT amount,status FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 5',(u.id,)).fetchall(); ps=c.execute('SELECT product,amount,status FROM purchases WHERE user_id=? ORDER BY id DESC LIMIT 5',(u.id,)).fetchall()
  lines=['📊 LỊCH SỬ CỦA BẠN','','💰 Nạp tiền:']+[f'• {r["amount"]:,}đ — {r["status"]}' for r in ds]+['','🛍 Mua hàng:']+[f'• {r["product"]} — {r["amount"]:,}đ — {r["status"]}' for r in ps]; await show(q,'\n'.join(lines),back())
 elif d=='files': await show(q,'📥 TẢI FILE\n\nChưa cấu hình file tải xuống.',back())
 elif d=='support': await show(q,'💬 HỖ TRỢ\n\nLiên hệ admin: @'+os.getenv('ADMIN_USERNAME','minhiosne').lstrip('@'),back())
 elif d=='miniapp': await show(q,'🌟 MINI APP\n\nChưa cấu hình WEBAPP_URL.',back())
 elif d=='admin_home': await show(q,'🛠 MENU ADMIN',admin_kb())
 elif d=='admin_stats':
  with db() as c:
   users=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']; dep=c.execute("SELECT COALESCE(SUM(amount),0) n FROM deposits WHERE status='confirmed'").fetchone()['n']; pending=c.execute("SELECT COUNT(*) n FROM deposits WHERE status='pending'").fetchone()['n']; pendamt=c.execute("SELECT COALESCE(SUM(amount),0) n FROM deposits WHERE status='pending'").fetchone()['n']; buys=c.execute('SELECT COUNT(*) n FROM purchases').fetchone()['n']; bal=c.execute('SELECT COALESCE(SUM(balance),0) n FROM users').fetchone()['n']
  await show(q,f'📊 THỐNG KÊ BOT\n\n👥 Tổng người dùng: {users}\n💰 Tổng nạp đã xác nhận: {dep:,}đ\n⏳ Đơn nạp chờ: {pending} ({pendamt:,}đ)\n🛍 Tổng đơn mua ghi nhận: {buys}\n🏦 Tổng số dư user: {bal:,}đ',admin_kb())
 elif d in ('admin_add_start','admin_sub_start'):
  context.user_data['admin_action']='add_amount' if d=='admin_add_start' else 'sub_amount'; await q.answer(); await q.message.reply_text('Nhập số tiền cần '+('cộng' if d=='admin_add_start' else 'trừ')+' (VNĐ):')
 elif d=='admin_check': context.user_data['admin_action']='check_uid'; await q.answer(); await q.message.reply_text('🔎 Nhập Telegram ID người dùng cần kiểm tra:')
 elif d.startswith('admin_add:') or d.startswith('admin_sub:'):
  uid=int(d.split(':')[1]); context.user_data['admin_target']=uid; context.user_data['admin_action']='add_amount' if d.startswith('admin_add:') else 'sub_amount'; await q.answer(); await q.message.reply_text(f'Nhập số tiền cần {"cộng" if d.startswith("admin_add:") else "trừ"} cho ID {uid}:')
 elif d.startswith('admin_deposit_ok:'):
  code=d.split(':',1)[1]
  with db() as c:
   r=c.execute('SELECT * FROM deposits WHERE code=?',(code,)).fetchone()
   if not r: await q.answer('Không tìm thấy đơn.',show_alert=True); return
   if r['status']!='pending': await q.answer('Đơn đã xử lý.',show_alert=True); return
   c.execute("UPDATE deposits SET status='confirmed',completed_at=? WHERE code=?",(now(),code)); c.execute('UPDATE users SET balance=balance+?,total_deposit=total_deposit+? WHERE user_id=?',(r['amount'],r['amount'],r['user_id'])); c.execute('INSERT INTO balance_logs(user_id,admin_id,amount,action,note,created_at) VALUES(?,?,?,?,?,?)',(r['user_id'],u.id,r['amount'],'deposit',code,now())); bal=c.execute('SELECT balance FROM users WHERE user_id=?',(r['user_id'],)).fetchone()['balance']
  await q.answer('Đã xác nhận.'); await q.edit_message_text(f'✅ Đã xác nhận {code}: {r["amount"]:,}đ cho user {r["user_id"]}.')
  try: await context.bot.send_message(r['user_id'],f'✅ Nạp tiền thành công: {r["amount"]:,}đ. Số dư mới: {bal:,}đ')
  except Exception: pass
 elif d.startswith('admin_deposit_no:'):
  code=d.split(':',1)[1]
  with db() as c:
   r=c.execute('SELECT * FROM deposits WHERE code=?',(code,)).fetchone()
   if not r: await q.answer('Không tìm thấy đơn.',show_alert=True); return
   if r['status']!='pending': await q.answer('Đơn đã xử lý.',show_alert=True); return
   c.execute("UPDATE deposits SET status='rejected',completed_at=? WHERE code=?",(now(),code))
  await q.answer('Đã từ chối.'); await q.edit_message_text(f'❌ Đã từ chối đơn {code}.')
  try: await context.bot.send_message(r['user_id'],'❌ Yêu cầu nạp tiền bị từ chối. Liên hệ admin nếu cần.')
  except Exception: pass
 else: await show(q,'Chức năng chưa được cấu hình.',back())
async def err(update,context): log.exception('Bot error',exc_info=context.error)
def main():
 if not TOKEN: raise RuntimeError('Thiếu BOT_TOKEN trong Railway Variables.')
 with db(): pass
 app=Application.builder().token(TOKEN).build(); app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('nap',nap_cmd)); app.add_handler(CommandHandler('admin',admin_cmd)); app.add_handler(CallbackQueryHandler(cb)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,messages)); app.add_error_handler(err); app.run_polling(drop_pending_updates=True)
if __name__=='__main__': main()
