import datetime
from zoneinfo import ZoneInfo
import os
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
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# ==== 1. 金鑰設定區 ====
LINE_CHANNEL_ACCESS_TOKEN = '9wnF8AgyP1Otdaol15CI0gQmg9LSptY4vRmJ7w5AFlwxUQcBmgr93f5ENEZbP7XOUfh0baXWcwPFvDFJZA8/xH8k9S4zhQx481IX00bKCqsMsN1rsos0YMLj7BEiKD+YicKjHYev1NzHY/AlDCiJ+wdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '35ceb4b586e28bbdf222e77ab84feb45'
GEMINI_API_KEY = 'AQ.Ab8RN6Lvj_WtwVkJobUTkuHhflN9WiAkgE0GdOWuN-j45OV8hg'

# 初始化各項服務
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 🌟 核心修正點 1：2026 新版 SDK 初始化 Client 的正確寫法
# 新版 google-genai 規定，如果要在初始化時直接帶入 API Key，必須將參數名稱精準寫為「api_key」
# （不可使用舊版 client_options 或 types 物件包裝，否則會在底層直接死機丟出 Exception）
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ==== 2. LINE Webhook 接收端 (直撞首頁大門萬用版) ====
@app.route("/", methods=['POST', 'GET'], strict_slashes=False)
def callback():
    # 如果 LINE 驗證按鈕發送 GET 測試請求，直接回傳 200 給它，解除驗證失敗！
    if request.method == 'GET':
        return 'LINE Bot is running!', 200
        
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ==== 3. 訊息處理與 AI 回覆邏輯 (100% 全 AI 暢聊版) ====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text  # 你傳給機器人的訊息
    reply_text = ""

    # 🌟 徹底丟棄死板的關鍵字與早午晚時間死規則！直接啟動大頭兵男友 AI 聊天！
    try:
        # 💡 即時抓取台灣最精準的目前小時，並塞給 Gemini 讓他自己判斷！
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
            "嚴格限制『每次回覆只能 1 到 3 個短句』。句型要短！就像一般人打 LINE 一樣，絕對不要長篇大論，禁止使用任何條列式排版。"
        )
        
        # 🌟 核心修正點 2：2026 新版 SDK 呼叫大腦的黃金字典語法
        # 新版 SDK 為了簡化開發，在 generate_content 中可以直接透過單一字典型態傳遞
        # 參數名稱必須精準呼應 'system_instruction' 與 'temperature'
        # 這可以 100% 繞過舊版從 google.genai 引入 types 物件時，在免費雲端（Render）上產生的環境縮排判定與型態不匹配崩潰
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=user_message,
            config={
                'system_instruction': system_prompt,
                'temperature': 0.8,
                'safety_settings': [
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH")
                ]
            }
        )
        reply_text = response.text.strip()

    except Exception as e:
        print(f"Gemini API 發生錯誤的原因是: {e}")
        reply_text = f"啊！你剛剛輸入的『{user_message}』讓我的伺服器短暫當機了！不過沒問題，我重開機一下，晚點再試一次就可以啦！"

    # (3) 將結果回傳給 LINE
    with ApiClient(configuration) as api_client_instance:
        line_bot_api = MessagingApi(api_client_instance)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

# ==== 4. 啟動伺服器 ====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
