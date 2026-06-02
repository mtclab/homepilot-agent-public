# SMTP Alert Configuration for Zabbix

## Current State
- Matrix Webhook (ID 72) is the only **active** media type
- Email (ID 1) and Email HTML (ID 4) are **disabled**, pointing to `mail.example.com`
- Gmail and Office365 types exist but are disabled

## Setup Options

### Option A: Gmail SMTP Relay (Simplest)
1. Enable a Gmail App Password for your Google account
2. Update Gmail media type (ID 34):
   - SMTP server: smtp.gmail.com:587
   - Username: your-email@gmail.com
   - Password: app-password
   - Enable status: 0 (enabled)

### Option B: Self-hosted Postfix (Recommended for Production)
1. Deploy Postfix on the dev server as a relay-only MTA
2. Configure DKIM, SPF, and rDNS for the domain
3. Update Email media type (ID 1) to point to localhost:25

### Option C: SendGrid/Mailgun Transactional Email
1. Sign up for a free SendGrid account (100 emails/day free)
2. Update Email media type:
   - SMTP: smtp.sendgrid.net:587
   - Auth: apikey:SG.xxxxx

## Zabbix Configuration

### Add Email Address to Admin User
1. Go to Users → Admin
2. Add media: Type=Email, Send to=alerts@yourdomain.com
3. Enable for all severities

### Create Alert Action
1. Go to Configuration → Actions → Trigger actions
2. Create new action "Send alerts via Email"
3. Conditions: Severity >= High
4. Operations: Send to User groups → Administrators via Email
5. Recovery operations: Send recovery message

## Quick Setup (Gmail)
```bash
# Via Zabbix API — replace placeholders with your credentials
ZABBIX_URL="http://your-server.local:8084"
ZABBIX_AUTH=$(curl -s -X POST "$ZABBIX_URL/api_jsonrpc.php" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"user.login","params":{"user":"Admin","password":"<ZABBIX_ADMIN_PASSWORD>"},"id":1}' | python3 -c "import json,sys; print(json.load(sys.stdin)['result'])")

# Update Gmail media type (requires Gmail app password)
curl -s -X POST "$ZABBIX_URL/api_jsonrpc.php" \
  -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"mediatype.update\",\"params\":{\"mediatypeid\":\"34\",\"status\":\"0\",\"smtp_server\":\"smtp.gmail.com\",\"smtp_port\":\"587\",\"smtp_email\":\"YOUR_EMAIL@gmail.com\",\"smtp_helo\":\"gmail.com\",\"userid\":\"1\",\"passwd\":\"<GMAIL_APP_PASSWORD>\"},\"auth\":\"$ZABBIX_AUTH\",\"id\":1}"
```
