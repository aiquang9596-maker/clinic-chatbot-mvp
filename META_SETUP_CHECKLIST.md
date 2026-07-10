# Meta Setup Checklist — WhatsApp + Messenger

> Bạn cần tự làm phần này trong trình duyệt.  
> Mình không tự làm thay được vì cần tài khoản Meta cá nhân của bạn.

---

## BƯỚC 1 — Tạo Meta Developer App (15 phút)

1. Truy cập https://developers.facebook.com
2. Đăng nhập tài khoản Facebook cá nhân (nên là tài khoản admin của Page và Business)
3. Click **My Apps → Create App**
4. Chọn **Business** làm app type
5. Đặt tên app: ví dụ `ClinicChatbot-Dev`
6. Liên kết với **Meta Business Account** (nếu chưa có: tạo tại https://business.facebook.com)
7. Lưu lại: **App ID** và **App Secret** → điền vào `.env`

---

## BƯỚC 2 — Thêm WhatsApp product (20–30 phút)

1. Trong App dashboard → **Add Product → WhatsApp**
2. Click **Set Up** trong WhatsApp section
3. Bạn sẽ thấy **WhatsApp Business API** setup
4. Tạo hoặc liên kết **WhatsApp Business Account (WABA)**
5. Trong **Phone Numbers**, bạn có 2 lựa chọn:

### Lựa chọn 2a — Dùng số test của Meta (nhanh nhất, không cần SIM)
- Meta cấp sẵn 1 test phone number
- Bạn có thể thêm tới 5 số điện thoại thật để nhận test message
- **Dùng để: học API + test webhook trước**

### Lựa chọn 2b — Dùng số điện thoại thật của clinic
- Số phải KHÔNG đang dùng WhatsApp cá nhân hoặc WhatsApp Business App
- Nếu số đang dùng WhatsApp Business App: làm theo hướng dẫn migrate
- Xác nhận số qua SMS OTP

6. Sau khi có số: lưu lại **Phone Number ID** → điền vào `.env`
7. Tạo **temporary access token** (hết hạn 24h) để test
8. Trong production: tạo **System User token** bền vững hơn

> ⚠️ Xác nhận với Meta: số điện thoại bạn dùng phải là số riêng cho WhatsApp Business API, không thể đồng thời dùng trên WhatsApp cá nhân/app.

---

## BƯỚC 3 — Cấu hình WhatsApp Webhook (10 phút)

1. Trong app dashboard → WhatsApp → Configuration
2. **Callback URL**: dán URL tunnel của bạn + `/webhook/whatsapp`
   - Ví dụ: `https://abc123.trycloudflare.com/webhook/whatsapp`
3. **Verify Token**: điền giá trị bạn đặt trong `.env` cho `WHATSAPP_VERIFY_TOKEN`
4. Click **Verify and Save**
5. Subscribe events:
   - ✅ `messages`
   - ✅ `message_deliveries` (nếu cần audit)
   - ✅ `message_reads` (tùy chọn)

**Để test verify:**  
Mở terminal, chạy backend trước, rồi chạy tunnel, rồi mới verify.

---

## BƯỚC 4 — Thêm Messenger product (20 phút)

1. Trong App dashboard → **Add Product → Messenger**
2. Click **Set Up**
3. **Generate Page Access Token**:
   - Chọn Facebook Page của clinic
   - Grant permissions
   - Copy token → điền vào `.env` cho `MESSENGER_PAGE_ACCESS_TOKEN`
4. Trong **Webhooks**:
   - Callback URL: `https://abc123.trycloudflare.com/webhook/messenger`
   - Verify Token: giá trị `MESSENGER_VERIFY_TOKEN` trong `.env`
   - Click **Verify and Save**
5. Subscribe Page Events:
   - ✅ `messages`
   - ✅ `messaging_postbacks` (cho nút/quick replies sau này)
   - ✅ `message_deliveries` (tùy chọn)

---

## BƯỚC 5 — App Mode: Development vs Live

| Mode | Dùng được | Hạn chế |
|---|---|---|
| **Development** | Chỉ tài khoản trong app roles | Không nhận message từ khách thật |
| **Live** | Nhận message từ bất kỳ người dùng | Cần switch app sang Live + có thể cần App Review |

**Cho MVP pilot nội bộ:** Development mode đủ dùng.  
**Khi muốn nhận khách thật:** Switch sang Live (Messenger thường không cần App Review cho Page Messaging; WhatsApp cần WABA verified).

---

## BƯỚC 6 — Permissions / App Review

### WhatsApp
- Thường không cần App Review nếu chỉ nhận/gửi trong cùng WABA
- Cần Business Verification nếu muốn tăng messaging limit

### Messenger
- Basic messaging qua Page: thường không cần App Review
- Nếu cần `pages_messaging` advanced access: có thể cần submit App Review
- Check trong App Review → Permissions xem permissions hiện tại đang ở level nào

---

## BƯỚC 7 — Điền .env

Sau khi làm xong các bước trên, mở `backend/.env` và điền:

```
WHATSAPP_VERIFY_TOKEN=your_verify_token_here        # bạn tự đặt, phải khớp với webhook setup
WHATSAPP_ACCESS_TOKEN=EAAxxxx...                    # từ bước 2
WHATSAPP_PHONE_NUMBER_ID=1234567890                 # từ bước 2
WHATSAPP_WABA_ID=0987654321                         # từ bước 2

MESSENGER_VERIFY_TOKEN=your_verify_token_here       # bạn tự đặt, phải khớp với webhook setup
MESSENGER_PAGE_ACCESS_TOKEN=EAAxxxx...              # từ bước 4
MESSENGER_APP_SECRET=your_app_secret                # App → Settings → Basic → App Secret
```

---

## BƯỚC 8 — Test end-to-end

1. Chạy backend: `.\scripts\start_backend.ps1`
2. Chạy tunnel: `.\scripts\start_tunnel.ps1` → copy URL tunnel
3. Cập nhật webhook URL trong Meta dashboard với URL tunnel mới
4. Gửi 1 tin nhắn test từ WhatsApp/Messenger
5. Xem log backend: phải thấy `WA inbound` hoặc `Messenger inbound`
6. Kiểm tra DB: `D:\2nd Brain\chatbot-mvp\backend\data\chatbot.db`

---

## Links tham khảo chính thức

- WhatsApp Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- WhatsApp Webhooks: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks
- WhatsApp Pricing: https://developers.facebook.com/docs/whatsapp/pricing
- Messenger Platform: https://developers.facebook.com/docs/messenger-platform
- Messenger Webhooks: https://developers.facebook.com/docs/messenger-platform/webhooks
- Meta App Review: https://developers.facebook.com/docs/app-review
