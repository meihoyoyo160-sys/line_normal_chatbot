import datetime
from zoneinfo import ZoneInfo
import os
import gc  # 🌟 導入垃圾回收套件，用來拯救 512MB 記憶體
import random # 🌟 導入隨機模組，讓貼圖回覆不重複
from flask import Flask, request, abort
from google import genai  # 新版 Gemini SDK 
from google.genai import types
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient, 
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
# 🌟 注意這裡引入了 StickerMessageContent，才能處理貼圖
from linebot.v3.webhooks import MessageEvent, TextMessageContent, StickerMessageContent

app = Flask(__name__)

# ==== 1. 金鑰設定區 (已改為安全環境變數讀取，若無設定則使用你的預設值) ====
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 初始化各項服務
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 新版 google-genai 初始化
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ==== 2. LINE Webhook 接收端 (新增防爆記憶體機制) ====
@app.route("/", methods=['POST', 'GET'], strict_slashes=False)
def callback():
    # 如果 cron-job.org 或 LINE 驗證發送 GET 測試請求
    if request.method == 'GET':
        response_text = 'LINE Bot is running!'
        response_code = 200
        gc.collect()  # 🌟 做了啥：戳完首頁後，立刻把多餘的網路連線暫存記憶體丟掉
        return response_text, response_code
        
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        gc.collect()  # 🌟 做了啥：即使驗證失敗，也要把垃圾清乾淨才結束
        abort(400)
        
    gc.collect()  # 🌟 核心關鍵：當 LINE 機器人整套聊天流程、API 發送都結束後，下一秒強行清空所有記憶體垃圾！
    return 'OK'

# ==== 3. 訊息處理與 AI 回覆邏輯 ====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text  # 你傳給機器人的訊息
    reply_text = ""

    # 🌟 新增：專屬關鍵字攔截機制 (勞業友 & gay)
    if "勞業友" in user_message:
        reply_text = "你竟然知道我！我是這個系統背後最不der、最帥的開發者，不論你說什麼我都給你一個讚"
        
        # 直接回傳給 LINE，不經過 Gemini API
        with ApiClient(configuration) as api_client_instance:
            line_bot_api = MessagingApi(api_client_instance)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        return # 攔截成功後直接結束這個函數，不再往下執行

    elif "gay" in user_message.lower(): # 使用 .lower() 確保大寫 GAY 也能攔截到
        reply_text = "你才gay 你全家都是gay！以為我不知道你腦袋都裝什麼東西嗎"
        
        with ApiClient(configuration) as api_client_instance:
            line_bot_api = MessagingApi(api_client_instance)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        return

    try:
        # 即時抓取台灣最精準的目前小時
        tw_hour = datetime.datetime.now(ZoneInfo("Asia/Taipei")).hour
        
        system_prompt = (
            f"你現在是一位在台灣上班、開朗搞笑的軟體工程師。現在台北時間是 {tw_hour} 點。\n"
            "「核心設定」：\n"
            "1. 極致真人感：你正在用 LINE 隨手回朋友訊息，說話要非常口語、直接。禁止像機器人般生硬，也禁止講出前後邏輯不通的贅字。\n"
            "2. 自然口頭禪：請『視情況隨機』使用「啊」、「可以啦」、「沒問題」、「哈哈」、「真假」等字眼。注意！不要每一句都硬塞，語氣順暢最重要。\n"
            "3. 保持新鮮感：**絕對不要連續兩次用一樣的笑話或比喻**（例如不要一直說重開機或拿乖乖），要根據使用者的話給出不同的自然反應。\n"
            "「情境應對」：\n"
            "1. 遇到髒話/不雅字：絕不說教！用一句話幽默帶過（例如：『啊！這句殺傷力太大我差點當機，但我重開機一下就可以啦！』）。\n"
            "2. 聽不懂或不知道怎麼回：直接承認（例如：『啊？這題太深奧我腦袋 CPU 轉不過來，你再說一次？』），不要硬扯不相關的冷笑話。\n"
            "3. 結合時間：深夜就說在爆肝或剛下班；吃飯時間就說準備去買便當。\n"
            "「強制字數限制」：\n"
            "嚴格限制『每次回覆只能 1 到 3 個短句』。句型要短！就像一般人打 LINE 一樣，絕對不要長篇大論，禁止使用任何條列式排版。\n"
            "「內容限制 (🌟新增)」：\n"
            "雖然是幽默搞笑，但請保持健康風格，絕對禁止產生任何18禁、過度性暗示或暴力的字眼，以免觸發系統安全審查。"
        )
        
        # 呼叫 Gemini 3.5 Flash Lite
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=user_message,
            config={
                'system_instruction': system_prompt,
                'temperature': 0.8,
                # 🌟 修改：將阻擋等級降到最低，避免正常幹話被消音
                'safety_settings': [
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                ]
            }
        )
        
        # 🌟 修改：加入防呆機制，確認有文字才處理，避免 NoneType Error
        if response.text:
            reply_text = response.text.strip()
        else:
            reply_text = "啊！你剛剛那句話讓我大腦 CPU 瞬間過熱當機，你剛剛說啥？可以再說一次嗎？"

    except Exception as e:
        print(f"Gemini API 發生錯誤的原因是: {e}")
        reply_text = f"啊！你剛剛輸入的『{user_message}』讓我的伺服器短暫當機了！不過沒問題，我重開機一下，晚點再試一次就可以啦！因為一分鐘內所有用戶回答數量超過15次我就會當機要等一下"
    
    finally:
        # 🌟 做了啥：不論 AI 生成是成功還是報錯當機，在準備回傳給 LINE 之前，先把剛才計算 Prompt 產生的暫存字串通通清掉
        gc.collect()

    # 將結果回傳給 LINE
    with ApiClient(configuration) as api_client_instance:
        line_bot_api = MessagingApi(api_client_instance)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )
        
    # 🌟 做了啥：訊息安全送達使用者手機後，再度呼叫清潔工，確保發送訊息留下的 API 快取完全歸零
    gc.collect()


# ==== 3.5 新增：貼圖訊息處理區塊 (專屬工程師的隨機 30 種回覆) ====
@handler.add(MessageEvent, message=StickerMessageContent)
def handle_sticker_message(event):
    try:
        # 工程師收到貼圖時的 30 種隨機萬用回覆清單
        sticker_replies = [
            "哇咧，這貼圖太鬧了吧！我剛在解 Bug 差點笑出來。",
            "收到貼圖！這讓我的 CPU 稍微降溫了一點 哈哈。",
            "這貼圖有夠 Q！先存起來，下次 Code Review 拿來噴人用。",
            "可以啦！看到這貼圖，我覺得今天的 Bug 都不是問題了。",
            "真假，這貼圖也太白爛了吧 哈哈哈！",
            "啊！你傳這貼圖害我切錯視窗，差點把 Server 關掉 哈哈。",
            "這貼圖讚誒！工程師的快樂就是這麼樸實無華。",
            "收到！這貼圖可愛到讓我暫停敲鍵盤三秒鐘。",
            "哈哈 這什麼怪貼圖啦，我先把它加進我的貼圖庫了！",
            "沒問題！有這張貼圖，我今晚加班寫 Code 有動力了。",
            "這貼圖的幽默感有抓到喔，跟我的 Code 一樣漂亮！",
            "哇咧，這圖也太貼切了吧，完全是我遇到 Bug 的表情。",
            "可以啦，看在貼圖這麼搞笑的份上，我繼續回去奮鬥了！",
            "啊哈哈哈，你哪來這麼多梗圖啦，笑死。",
            "真假！這張貼圖完美詮釋了我現在看 Log 的心情。",
            "歐虧虧！收到貼圖，馬上把這心情 push 到 GitHub 上。",
            "這貼圖很解壓誒！比重開機還有用 哈哈。",
            "哈哈，這畫面太美我不敢看，我要回去修 Bug 了。",
            "這貼圖太魔性了吧，害我腦袋一直在 loop 這個畫面。",
            "讚啦！工程師就是需要這種圖來點綴枯燥的 Terminal。",
            "沒問題，這貼圖我給 100 分！完全沒 Bug。",
            "哇咧，突然傳這貼圖，害我喝咖啡差點嗆到 哈哈！",
            "這張真的神回覆誒，我下次開會也要用這表情。",
            "哈哈！這圖太讚了，先收起來當作下次發 PR 的慶祝圖。",
            "真假啦，看到這圖我瞬間忘記剛剛變數命名要叫什麼了。",
            "啊！這貼圖有毒吧，害我盯著螢幕笑了五分鐘。",
            "可以啦，你這貼圖完全是工程師日常寫照啊！",
            "太好笑了！這圖直接 bypass 了我的心情防火牆。",
            "哈哈，你傳這圖的 timing 也太準了吧，剛好解完一個大 Bug！",
            "收到收到！感謝貼圖支援，我的電力恢復 20% 了！"
        ]
        
        # 使用 random.choice 隨機挑選一句
        reply_text = random.choice(sticker_replies)
        
        with ApiClient(configuration) as api_client_instance:
            line_bot_api = MessagingApi(api_client_instance)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
    except Exception as e:
        print(f"貼圖回覆發生錯誤: {e}")


# ==== 4. 啟動伺服器 ====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
