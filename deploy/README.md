# Going Digital deployment templates

Templates for Nginx + Gunicorn on a DigitalOcean droplet (or similar).

## Files

| Path | Purpose |
|------|---------|
| `env/.env.production.example` | Production `.env` checklist (placeholders only) |
| `env/.env.staging.example` | Staging `.env` checklist |
| `nginx/goingdigital.co.uk.conf` | Production vhost (www → apex) |
| `nginx/staging.goingdigital.co.uk.conf` | Staging vhost |
| `systemd/goingdigital.service` | Gunicorn unit |

Default app path in these files: `/var/www/going-digital`. Change if yours differs.

## Quick start (production)

1. **Code + venv**
   ```bash
   cd /var/www/going-digital
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment**
   ```bash
   cp deploy/env/.env.production.example .env
   # edit .env — real SECRET_KEY, DB, Stripe live keys, Mailgun, reCAPTCHA, etc.
   ```

3. **Database + static**
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

4. **Gunicorn**
   ```bash
   sudo cp deploy/systemd/goingdigital.service /etc/systemd/system/goingdigital.service
   # edit paths in the unit if needed
   sudo systemctl daemon-reload
   sudo systemctl enable --now goingdigital
   sudo systemctl status goingdigital
   ```

5. **Nginx + TLS**
   ```bash
   sudo cp deploy/nginx/goingdigital.co.uk.conf /etc/nginx/sites-available/goingdigital.co.uk
   sudo ln -sf /etc/nginx/sites-available/goingdigital.co.uk /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d goingdigital.co.uk -d www.goingdigital.co.uk
   ```

6. **Firewall (DigitalOcean Cloud Firewall or ufw)**  
   Inbound only: **22**, **80**, **443**.

7. **Stripe**  
   Dashboard webhook: `https://goingdigital.co.uk/payments/webhook/`  
   Put the endpoint’s `whsec_` in `.env` as `STRIPE_WEBHOOK_SECRET`, then:
   ```bash
   sudo systemctl restart goingdigital
   ```

## Staging

Same flow with `env/.env.staging.example` and `nginx/staging.goingdigital.co.uk.conf`.  
Use Stripe **test** keys and optionally `DEV_SITE_ACCESS_ENABLED=True`.

## Checklist before DNS cutover

- [ ] `DEBUG=False`, strong unique `SECRET_KEY`
- [ ] `SITE_URL=https://goingdigital.co.uk`
- [ ] Live Stripe keys + matching webhook secret
- [ ] Production reCAPTCHA keys
- [ ] SMTP working (`CONTACT_EMAIL` receives order BCCs)
- [ ] `collectstatic` done; `/media/` writable by gunicorn user
- [ ] Legacy redirects migrated (`website` 0023/0024)
- [ ] Cron for reminder / follow-up emails if used
- [ ] www and apex both resolve; HTTPS redirect OK
