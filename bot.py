import telebot
import sqlite3
from datetime import datetime

TOKEN = "8893654287:AAHo04e3_dVx2ldbeQTK5wO5HIEkiR-T6y4"
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect('jizhang.db', check_same_thread=False)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('''CREATE TABLE IF NOT EXISTS records (
             id INTEGER PRIMARY KEY, 
             chat_id TEXT,
             type TEXT,
             time TEXT,
             amount REAL,
             rate REAL,
             result REAL,
             note TEXT,
             date TEXT,
             timestamp REAL)''')
conn.commit()

bot_join_time = {}

# ================== 开始 / 结束 ==================
@bot.message_handler(commands=['start', '开始'])
def start_bot(message):
    cid = str(message.chat.id)
    bot_join_time[cid] = datetime.now().timestamp()
    bot.reply_to(message, "🚀 记账已开始！现在可以记账了")

@bot.message_handler(commands=['stop', '结束', '停止'])
def stop_bot(message):
    cid = str(message.chat.id)
    if cid in bot_join_time:
        del bot_join_time[cid]
    bot.reply_to(message, "⏹️ 记账已结束")

# ================== 删除功能（回复 + 取消/删除） ==================
@bot.message_handler(func=lambda m: True)
def handle(message):
    cid = str(message.chat.id)
    if cid not in bot_join_time:
        return

    text = (message.text or "").strip()

    # 删除功能
    if message.reply_to_message and ("取消" in text or "删除" in text):
        delete_last_record(message)
        return

    if not text or text[0] not in ['+', '➕', '-', '➖']:
        return

    # 正常记账逻辑（省略中间部分，与之前一致）
    is_incoming = text[0] in ['+', '➕']
    text = text[1:].strip()

    user = message.from_user
    auto_name = (user.first_name or "") + (" " + (user.last_name or ""))
    auto_name = auto_name.strip() or "未知用户"

    note = auto_name
    custom_rate = None

    try:
        if '*' in text:
            amt_str, rate_str = [x.strip() for x in text.split('*', 1)]
            amount = float(amt_str)
            custom_rate = float(rate_str)
        else:
            parts = text.split(maxsplit=1)
            amount = float(parts[0])
            if len(parts) > 1:
                note = parts[1] + " " + auto_name
    except:
        return

    rate = custom_rate if custom_rate is not None else 7.25
    fee = 0.05

    if is_incoming:
        result = round(amount * rate * (1 - fee), 2)
        ttype = "入款"
    else:
        result = round(amount * rate, 2)
        ttype = "下发"

    msg_time = datetime.fromtimestamp(message.date)
    cur_time = msg_time.strftime("%H:%M")

    cur = conn.cursor()
    cur.execute("""INSERT INTO records (chat_id, type, time, amount, rate, result, note, date, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cid, ttype, cur_time, amount, rate, result, note, msg_time.strftime("%Y-%m-%d"), message.date))
    conn.commit()
    cur.close()

    bot.reply_to(message, f"✅ {ttype} 已记录\n{cur_time} {amount:.2f} → {result:.2f} 元 {note}")
    today_stats(message)

# 删除最近一条记录
def delete_last_record(message):
    cid = str(message.chat.id)
    cur = conn.cursor()
    cur.execute("DELETE FROM records WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (cid,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()

    if deleted > 0:
        bot.reply_to(message, "✅ 已删除最近一条记录")
        today_stats(message)
    else:
        bot.reply_to(message, "❌ 没有找到可删除的记录")

# 清除今日
@bot.message_handler(commands=['clear', '清除今日', '清除'])
def clear_today(message):
    cid = str(message.chat.id)
    if cid not in bot_join_time:
        bot.reply_to(message, "请先发送 开始")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    cur = conn.cursor()
    cur.execute("DELETE FROM records WHERE chat_id=? AND date=?", (cid, today))
    conn.commit()
    cur.close()
    bot.reply_to(message, "✅ 已清除今日所有记录")

# 统计
@bot.message_handler(commands=['today', '今日', '统计'])
def today_stats(message):
    cid = str(message.chat.id)
    if cid not in bot_join_time:
        bot.reply_to(message, "⚠️ 请先发送 开始")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    start_ts = bot_join_time[cid]

    cur = conn.cursor()
    cur.execute("""SELECT type, time, amount, result, note 
                   FROM records 
                   WHERE chat_id=? AND date=? AND timestamp >= ? 
                   ORDER BY id""", (cid, today, start_ts))
    records = cur.fetchall()
    cur.close()

    in_lines = []
    out_lines = []
    total_in = 0.0
    total_out = 0.0

    for typ, t, amt, res, note in records:
        note_str = f" {note}" if note else ""
        if typ == "入款":
            line = f"{t}  {amt:.2f} * (5%) = {res:.2f}{note_str}"
            in_lines.append(line)
            total_in += res
        else:
            line = f"{t}  {amt:.2f}{note_str}"
            out_lines.append(line)
            total_out += amt

    in_text = "\n".join(in_lines) if in_lines else "暂无入款"
    out_text = "\n".join(out_lines) if out_lines else "暂无下发"

    reply = f"""📅 {today} 统计
今日入款（{len(in_lines)}笔）
{in_text}
今日下发（{len(out_lines)}笔）
{out_text}
────────────────
总入款：{total_in:.2f}
汇率：7.25
交易费率：5%
应下发：{total_in:.2f}
已下发：{total_out:.2f}
余额：{total_in - total_out:.2f}"""
    bot.reply_to(message, reply)

print("🚀 完整版机器人已启动（支持删除）...")
bot.infinity_polling(none_stop=True)
