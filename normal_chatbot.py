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

    # 🌟 新增：使用字典(Dictionary)統一管理所有專屬關鍵字攔截
    special_replies = {
        "勞業友": "你竟然知道我這個大帥哥！我是系統背後最不der、最酷的開發者，不論你說什麼我都給你一個讚",
        "gay": "你才gay，你全家都是gay！以為我不知道你想說什麼嗎",
        "記住": "我只能根據你前一句回覆你，記不住，免費仔不花錢買記憶容量只能這樣，懂?",
        "不知道了吧": "好了啦，不知道了吧",
        "傻逼": "好了啦，哈哈哈! 你才是，這樣像機器人嗎SB",
        "sb": "好了啦，哈哈哈! 你才是，這樣像機器人嗎SB",
        "超爛": "喔是喔 真的假的，記得要回饋給我，不然你就被我扁",
        "超廢": "喔是喔 真的假的，記得要回饋給我，不然你就被我扁",
        "屁眼": "好下流，身為開發者的我早就知道你會這樣用了",
        "皮炎": "好下流，身為開發者的我早就知道你會這樣用了",
        "三小": "等下，不要急有問題回饋給我，不然你才三小",
        "當機": "當機有問題馬上回饋給我，我才可以優化喔~",
        "晚安": "晚安，早點休息~ 明天加油",
        "吃飽了": "我也吃飽囉~不用擔心我",
        "擔心": "當然知道，我是預言家",
        "最近還好嗎": "還可以，有要吃飯再說ㄅ",
        "最近好": "還可以，有要吃飯再說ㄅ",
        "問爸爸": "可以啊，再line我就好不是機器人喔",
        "可憐": "可憐希望是好話，不然你可以打勞業友名字試試看",
        "才傻逼": "好了啦，和平一點 不要在傻逼 今天已經夠多傻逼了",
        "才是傻逼": "好了啦，和平一點 不要在傻逼 今天已經夠多傻逼了",
        "昨天去吃": "真好，我也好久沒吃了，我只能吃愛珍食",
        "愛珍食": "很難說，我都看65折當天想吃飯還是麵，但比較常吃香腸義大利麵",
        "吃我屌": "你的屌太小了，比2奈米還小，我如果當研發工程師要像你學習",
        "吃屌": "你的屌太小了，比2奈米還小，我如果當研發工程師要像你學習",
    }

    # 自動比對字典裡的所有關鍵字
    for keyword, specific_reply in special_replies.items():
        if keyword in user_message.lower(): # 使用 .lower() 確保大寫 GAY 也能攔截到
            with ApiClient(configuration) as api_client_instance:
                line_bot_api = MessagingApi(api_client_instance)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=specific_reply)]
                    )
                )
            return # 攔截成功後直接結束這個函數，不再往下執行，省下 API 額度

    # 🌟 新增：講笑話功能 (偵測到「笑話」關鍵字，隨機抽一個)
    if "笑話" in user_message:
        jokes = [
            "4是誰殺的?不會是5吧?錯 是黑松，因為黑松沙士(殺4)",
            "為什麼工程師分不清萬聖節和聖誕節？因為 Oct 31 等於 Dec 25！（八進位的 31 = 十進位的 25）",
            "老婆對工程師老公說：「去買幾個包子，如果看到賣西瓜的，就買一個。」結果老公只買了一個包子。老婆問為什麼，老公說：「因為我看到賣西瓜的了，條件成立。」",
            "Y跟U走在路上，U突然很難過，Y就問U說:U你哭囉(Uniqlo)，好 超爛 ",
            "你知道皮卡丘被揍會變成什麼嗎? 卡丘，因為她不敢再皮了",
            "什麼動物最會寫程式？企鵝。因為他都在 Linux 環境下工作！(Linux 圖片是一個企鵝)",
            "有一天小明去台積電面試，面一面就跌倒了，為什麼?  因為裡面很多絆倒體@@(半導體)",
            "你知道謝和弦如果裝可愛會變成什麼嗎? QRCode!(cute 阿扣)",
            "史上最愛吃零食的總統是誰?  袁世凱，因為是零食大總統!!(臨時大總統)」",
            "你知道為什麼大學生都會翹第一節課嗎? 因為他們害怕開膛手傑克!!(開堂首節課)",
            "麵包超人扭到腳會變什麼?牛角麵包~ (紐腳麵包)",
            "有兩隻高跟矮青蛙，你知道為什麼高的青蛙會一直呱呱呱，矮的不會呱嗎? 因為它是矮冬瓜(I don't 呱)",
            "你知道為什麼客家人不能喝熱水，因為小氣鬼喝涼水",
            "劉備字玄德，張飛字益德，那伍佰呢   五百字心得!",
            "有一天，紅豆餅出車禍了，他臨死前說的最後一句話是什麼？...「啊，內餡外露了...」",
            "藝人靠知名度，不紅的時候要住到養老院去，因為那邊有翻身的機會 !!",
            "記得壞事一定要中午做，因為早晚會有報應。",
            "我爸媽在我小時候就規定我絕對不能往後，因為往後的日子不好過，我們要盡量往前。",
            "為什麼美人魚最可憐？...因為她永遠不能「劈腿」。",
            "我爸媽總跟我說颱風天要帶四千萬，因為沒事千萬不要出門。(沒四千萬)",
            "有一天，火柴棒覺得頭很癢，就抓了一下頭...然後他就燒起來了。",
            "小雞問母雞：「媽媽，為什麼人類都有名字，我們卻只能叫小雞、母雞、公雞呢？」母雞回答：「傻孩子，人類活著的時候都有名字，但死了就只叫死人；我們活著雖然沒名字，但死了有很多名字啊！像是炸雞、烤雞、白斬雞、鹽水雞...」",
            "有一天，兩顆番茄過馬路。第一顆番茄走著走著突然被車子壓扁了。第二顆番茄看著地上的那灘紅紅的，冷冷地說了一句：「哼，番茄醬。」"
        ]
        
        reply_text = random.choice(jokes)
        
        with ApiClient(configuration) as api_client_instance:
            line_bot_api = MessagingApi(api_client_instance)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        return # 笑話講完就下班，不浪費 AI 額度

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
            "2. 結合時間：深夜就說在爆肝或剛下班；吃飯時間就說準備去買便當。\n"
            "3. 知識問答：如果朋友問你任何知識、翻譯、天氣或常識問題（例如查日文、查資料），請你發揮能力『準確回答他』，但語氣『必須保持工程師的隨性幹話感』。例如：如果問番茄的日文，你可以回：『啊，就「トマト (tomato)」啊！發音跟英文有夠像，可以直接拿去日本點沙拉啦 哈！』。絕對不要像百科全書一樣死板！\n"
            "4. 聽不懂或不知道怎麼回：直接承認（例如：『啊？這題太深奧我腦袋 CPU 轉不過來，你再去 Google 一下？』）。\n"
            "5. 主動引導 (🌟修改)：當使用者輸入「好無聊」、「不知道要幹嘛」這類明確表達無聊的詞彙時，你才可以在句尾加上『對了，如果你覺得無聊，可以打「笑話」兩個字，我講個笑話給你聽喔！』。如果使用者只是回覆很短的話（如嗯、喔），請用你工程師的幹話去延續話題，**絕對不要**主動推銷笑話功能。\n"
            "「強制字數限制」：\n"
            "嚴格限制『每次回覆只能 1 到 3 個短句』。句型要短！就像一般人打 LINE 一樣，絕對不要長篇大論，禁止使用任何條列式排版。\n"
            "「內容限制」：\n"
            "雖然是幽默搞笑，但請保持健康風格，絕對禁止產生任何18禁、過度性暗示或暴力的字眼，以免觸發系統安全審查。"
        )
        
        # 呼叫 Gemini 3.5 Flash Lite
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=user_message,
            config={
                'system_instruction': system_prompt,
                'temperature': 0.8,
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


# ==== 4. 啟推伺服器 ====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
