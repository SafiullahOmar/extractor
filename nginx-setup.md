# Nginx Setup for Production

## Installation

1. Install nginx:
```bash
sudo apt-get update
sudo apt-get install nginx
```

2. Copy nginx config:
```bash
sudo cp nginx.conf /etc/nginx/sites-available/pdf-extraction
sudo ln -s /etc/nginx/sites-available/pdf-extraction /etc/nginx/sites-enabled/
```

3. Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Access URLs

- API: `http://your-server/api/`
- Airflow: `http://your-server/airflow/`
- Qdrant: `http://your-server/qdrant/`

## SSL Setup (Optional)

For HTTPS, use Let's Encrypt:
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```
