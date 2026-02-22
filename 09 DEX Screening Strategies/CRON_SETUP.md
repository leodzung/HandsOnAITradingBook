# Cron Job Setup for Automated DEX Scanner

This guide will set up automated hourly scanning during peak trading hours with email alerts to **ltd@bu.edu**.

---

## 🚀 Quick Setup (5 Minutes)

### Step 1: Set Up Email Configuration

You need a Gmail account to send emails. Here's how to set it up:

#### Option A: Use Your Existing Gmail

1. **Enable 2-Factor Authentication** (if not already enabled)
   - Go to: https://myaccount.google.com/security
   - Enable "2-Step Verification"

2. **Create App Password** (Required for Gmail)
   - Go to: https://myaccount.google.com/apppasswords
   - Select app: "Mail"
   - Select device: "Mac" or "Other (Custom name)"
   - Click "Generate"
   - **Copy the 16-character password** (looks like: xxxx xxxx xxxx xxxx)

3. **Edit email_config.json**
   ```bash
   cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
   nano email_config.json
   ```

   Update these fields:
   ```json
   {
     "email_settings": {
       "to_email": "ltd@bu.edu",
       "from_email": "YOUR_GMAIL@gmail.com",
       "smtp_server": "smtp.gmail.com",
       "smtp_port": 587,
       "smtp_password": "xxxx xxxx xxxx xxxx",  // <- Your App Password
       "subject_prefix": "[DEX Scanner]"
     }
   }
   ```

   Save: Press `Ctrl+O`, then `Enter`, then `Ctrl+X`

#### Option B: Create New Gmail Account (Recommended for Security)

1. Create new Gmail: https://accounts.google.com/signup
2. Use it ONLY for these alerts
3. Follow steps above to get App Password

---

### Step 2: Test Email Functionality

Make sure emails work before setting up cron:

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
python3 run_with_email_alerts.py
```

**Expected output:**
```
✅ Email configuration loaded
🔍 Running DEX scanner...
... (scanning results) ...
✅ Scan complete
📧 Sending email to ltd@bu.edu...
✅ Email sent successfully!
```

**Check your email at ltd@bu.edu!**

If you see errors:
- Check Gmail credentials
- Verify App Password is correct (no spaces when entering)
- Make sure 2FA is enabled on Gmail account

---

### Step 3: Make Script Executable

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
chmod +x run_with_email_alerts.py
```

---

### Step 4: Set Up Cron Job

#### Create the cron job file:

```bash
# Open crontab editor
crontab -e
```

#### Add these lines:

```cron
# DEX Scanner - Runs hourly during peak trading hours (UTC)
# Peak hours: 9AM-6PM UTC (covers US & Europe markets)

# Set the base directory
SCANNER_DIR=/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies

# Run every hour from 9AM to 6PM UTC, Monday-Friday
0 9-18 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1

# Alternative: Run every 2 hours (less frequent)
# 0 9,11,13,15,17 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1

# Alternative: Run 24/7 every hour (not recommended - API limits)
# 0 * * * * cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1
```

**Save and exit:**
- Press `Esc`
- Type `:wq`
- Press `Enter`

Or if using nano:
- Press `Ctrl+O`, `Enter`, `Ctrl+X`

---

## 📅 Cron Schedule Explained

### Current Schedule: `0 9-18 * * 1-5`

```
0       - Run at minute 0 (top of the hour)
9-18    - Run hours 9AM through 6PM
*       - Every day of month
*       - Every month
1-5     - Monday through Friday only
```

**Times in UTC:**
- 9AM UTC = 4AM EST / 1AM PST
- 12PM UTC = 7AM EST / 4AM PST
- 3PM UTC = 10AM EST / 7AM PST
- 6PM UTC = 1PM EST / 10AM PST

### Alternative Schedules:

**Every 2 hours (recommended to start):**
```cron
0 9,11,13,15,17 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1
```

**Every 4 hours:**
```cron
0 9,13,17 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1
```

**Twice a day (9AM and 3PM UTC):**
```cron
0 9,15 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1
```

**24/7 every hour (high API usage):**
```cron
0 * * * * cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1
```

---

## ✅ Verify Cron Job is Active

### Check if cron job was added:
```bash
crontab -l
```

You should see your DEX Scanner entry.

### View cron logs:
```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
tail -f cron_log.txt
```

Press `Ctrl+C` to exit.

### Check if cron job ran:
```bash
ls -lth cron_log.txt
```

If file exists and is recent, cron is working!

---

## 📧 What Emails Look Like

### Subject Line:
```
[DEX Scanner] Found 3 High-Quality Tokens!
```

### Email Content:
- 🚨 Header with timestamp
- 📊 Each opportunity with:
  - Composite score (highlighted green if ≥80)
  - Safety & Opportunity scores
  - Liquidity and volume
  - Price changes
  - Direct links to:
    - DexScreener chart
    - Honeypot checker
    - BSCScan contract
- ⚠️ Warning section with safety reminders

### When You'll Get Emails:

**You'll receive an email when:**
- Scanner finds tokens with composite score ≥ 70 (configurable)
- Maximum 5 tokens per email (configurable)
- Only during scheduled hours

**You won't get emails when:**
- No opportunities found
- All opportunities score < 70
- Scanner encounters errors (you'll get error email instead)

---

## ⚙️ Configuration Options

Edit `email_config.json`:

### Change alert threshold:
```json
"min_score_to_alert": 70,  // Change to 75 or 80 for stricter
```

### Change max alerts per email:
```json
"max_alerts_per_run": 5,  // Increase to 10 if you want more
```

### Change email subject prefix:
```json
"subject_prefix": "[DEX Scanner]"  // Change to anything you want
```

---

## 🔍 Monitoring & Troubleshooting

### View Recent Logs:
```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
tail -100 cron_log.txt
```

### View Logs in Real-Time:
```bash
tail -f cron_log.txt
```

### Check for Errors:
```bash
grep -i error cron_log.txt
grep -i failed cron_log.txt
```

### Test Manually:
```bash
python3 run_with_email_alerts.py
```

### Common Issues:

**1. No emails received**
- Check cron_log.txt for errors
- Verify cron job is active: `crontab -l`
- Check spam folder in ltd@bu.edu
- Verify email credentials in email_config.json

**2. Authentication errors**
- Make sure you're using App Password, not regular password
- Verify 2FA is enabled on Gmail
- Try regenerating App Password

**3. Cron not running**
- Check system time: `date`
- Verify cron service is running: `ps aux | grep cron`
- Check absolute paths in crontab

**4. "Permission denied" errors**
- Run: `chmod +x run_with_email_alerts.py`
- Check file permissions: `ls -la run_with_email_alerts.py`

---

## 🛑 Stop/Pause the Cron Job

### Temporarily disable:
```bash
crontab -e
# Add # at start of line to comment it out
# #0 9-18 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3...
```

### Completely remove:
```bash
crontab -r  # Removes ALL cron jobs!
```

### Remove just DEX scanner job:
```bash
crontab -e
# Delete the DEX Scanner line
# Save and exit
```

---

## 📊 Expected Results

### Good Market (Active Trading):
- 2-5 alerts per day
- Scores typically 70-85
- 1-2 high-quality opportunities (≥80)

### Slow Market:
- 0-1 alerts per day
- May go days without emails (this is normal!)

### Bull Market:
- 5-10+ alerts per day
- Many scores ≥80
- More opportunities but also more scams!

---

## 🎯 Best Practices

### Start Conservative:
1. **Week 1:** Run every 4 hours, min_score=75
2. **Week 2:** If working well, run every 2 hours
3. **Week 3:** Adjust min_score based on results
4. **Month 2:** Consider hourly during peak times

### Monitor Performance:
```bash
# Count how many times scanner ran
grep "Scan completed successfully" cron_log.txt | wc -l

# Count how many alerts sent
grep "Alert sent successfully" cron_log.txt | wc -l

# Calculate alert rate
# alerts / scans = hit rate
```

### Adjust Thresholds:
- **Too many emails?** Increase `min_score_to_alert` to 75 or 80
- **No emails?** Lower to 65 or 70
- **Still no emails?** Check if scanner is finding any opportunities in logs

---

## 📱 Advanced: Add SMS Alerts

If you want SMS in addition to email, you can use:

### Option 1: Email-to-SMS Gateway
Many carriers provide email-to-SMS:
- Verizon: `5551234567@vtext.com`
- AT&T: `5551234567@txt.att.net`
- T-Mobile: `5551234567@tmomail.net`

Just add to `email_config.json`:
```json
"to_email": "ltd@bu.edu,5551234567@vtext.com"
```

### Option 2: Twilio (Paid)
1. Sign up: https://www.twilio.com/
2. Get API credentials
3. Modify script to use Twilio API

---

## 🔐 Security Notes

### Protect Your Credentials:
```bash
# Make config file readable only by you
chmod 600 email_config.json

# Never commit credentials to Git
echo "email_config.json" >> .gitignore
```

### Use Dedicated Email:
- Create separate Gmail just for alerts
- Don't use your main personal email
- Easier to disable if compromised

### Monitor Access:
- Check Gmail security: https://myaccount.google.com/security
- Review "Recent security activity"
- Revoke App Password if needed

---

## 📋 Complete Checklist

Before going live, verify:

- [ ] Email config updated with your Gmail
- [ ] App Password generated and added
- [ ] Test email sent successfully
- [ ] Script made executable (`chmod +x`)
- [ ] Cron job added (`crontab -e`)
- [ ] Cron job verified (`crontab -l`)
- [ ] Logs directory writable
- [ ] Absolute paths in crontab
- [ ] Schedule matches your timezone preference
- [ ] First test email received at ltd@bu.edu

---

## 🎉 You're All Set!

Your DEX scanner will now:
- ✅ Run automatically every hour during peak trading times
- ✅ Scan for high-quality token opportunities
- ✅ Email you at ltd@bu.edu when found
- ✅ Include direct links to verify tokens
- ✅ Log all activity for monitoring

**Next Steps:**
1. Wait for first scheduled run
2. Check cron_log.txt after scheduled time
3. Check ltd@bu.edu for alert emails
4. Verify and trade on promising opportunities
5. Track your results!

---

## 🆘 Need Help?

**Check logs:**
```bash
tail -100 cron_log.txt
```

**Test manually:**
```bash
python3 run_with_email_alerts.py
```

**Verify cron:**
```bash
crontab -l
```

**Check email config:**
```bash
cat email_config.json
```

---

**Good luck finding those gems! 💎**

*Remember: 90% of tokens fail. The scanner helps you find the 10% worth considering.*

---

*Last Updated: 2024-11-02*
