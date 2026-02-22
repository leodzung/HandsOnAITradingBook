# Quick Reference Card

## System Setup Status

✅ Python 3.9.6 installed
✅ All packages installed
✅ Project structure created
✅ Config files created
✅ Database ready
✅ Main program working

## What You Need Next

### REQUIRED to run:
1. **Amazon Seller Account** ($39.99/month)
   - Get SP-API credentials
   - Add to `config/config.yaml`

2. **Keepa API** ($19+/month) - Highly recommended
   - Sign up at keepa.com
   - Add API key to config

3. **Email for Alerts**
   - Gmail app password
   - Add to config

## Quick Start Commands

```bash
# Navigate to project
cd "10 E-Commerce Arbitrage System"

# Edit configuration (add your API keys)
nano config/config.yaml
# or
open -e config/config.yaml  # Opens in TextEdit

# Test the system
python3 main.py --show-deals

# Run your first scan (after adding credentials)
python3 main.py --scanner amazon

# View results
python3 main.py --show-deals --min-roi 30

# Send test report
python3 main.py --report
```

## Configuration File Locations

- Main config: `config/config.yaml`
- Environment variables: `.env`
- Database: `data/deals.db`
- Logs: `logs/arbitrage.log`

## Key Settings to Configure

Edit `config/config.yaml`:

```yaml
# 1. Amazon credentials (REQUIRED)
amazon:
  sp_api:
    refresh_token: "YOUR_TOKEN"
    client_id: "YOUR_CLIENT_ID"
    client_secret: "YOUR_SECRET"

# 2. Keepa API (HIGHLY RECOMMENDED)
keepa:
  api_key: "YOUR_KEEPA_KEY"

# 3. Email alerts
notifications:
  email:
    enabled: true
    sender_email: "your@gmail.com"
    sender_password: "YOUR_APP_PASSWORD"
    recipient_emails:
      - "your@gmail.com"

# 4. Deal filters
profit:
  min_roi: 30.0  # Adjust based on your strategy

filters:
  max_sales_rank:
    default: 50000
  max_number_of_sellers: 10
```

## Common Commands

| Task | Command |
|------|---------|
| Scan all sources | `python3 main.py --scan-all` |
| Scan Amazon only | `python3 main.py --scanner amazon` |
| Show deals | `python3 main.py --show-deals` |
| High ROI only | `python3 main.py --show-deals --min-roi 50` |
| Send report | `python3 main.py --report` |
| Open analysis | `jupyter notebook notebooks/analysis.ipynb` |

## Next Steps

1. **Read the full setup guide:**
   ```bash
   open SETUP_GUIDE.md
   ```

2. **Get Amazon SP-API credentials:**
   - Go to Amazon Seller Central
   - Apps & Services → Develop Apps
   - Create new app and get credentials

3. **Get Keepa API key:**
   - Visit https://keepa.com
   - Subscribe to API access
   - Copy API key

4. **Configure the system:**
   ```bash
   nano config/config.yaml
   ```

5. **Test it:**
   ```bash
   python3 main.py --show-deals
   ```

## Help & Documentation

- **Full setup**: `SETUP_GUIDE.md`
- **Quick start**: `QUICKSTART.md`
- **Full docs**: `README.md`
- **Command help**: `python3 main.py --help`

## Important URLs

- Amazon Seller Central: https://sellercentral.amazon.com
- Keepa: https://keepa.com
- Google App Passwords: https://myaccount.google.com/apppasswords

## Cost Summary

| Service | Cost | Required? |
|---------|------|-----------|
| Amazon Professional Seller | $39.99/mo | ✅ Yes |
| Keepa API | $19-149/mo | 🔶 Highly recommended |
| Best Buy API | Free | ❌ Optional |
| Walmart API | Free | ❌ Optional |

## Troubleshooting

**Can't find config file?**
```bash
ls config/config.yaml
```

**Need to reinstall packages?**
```bash
pip3 install -r requirements.txt
```

**Database not found?**
```bash
ls data/deals.db
python3 main.py --show-deals  # Creates it if missing
```

## Support

If you need help:
1. Check SETUP_GUIDE.md for detailed instructions
2. Verify API credentials are correct
3. Check logs: `tail -f logs/arbitrage.log`
4. Ensure YAML syntax is correct (no tabs, only spaces)

---

**Ready to start?** Open SETUP_GUIDE.md for step-by-step instructions!
