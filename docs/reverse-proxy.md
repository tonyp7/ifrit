# Reverse Proxy

The application container serves plain HTTP, redirected to 8081 in the example compose files. 
For a real deployment, put a reverse proxy or load balancer that terminates TLS in front of it (nginx, Caddy, Traefik, a cloud load balancer), and update the environment variables in `.env` accordingly:

```text
CORS_ORIGINS=["https://ifrit.mydomain.com"]
COOKIE_SECURE=true
```

- `CORS_ORIGINS` must list the exact origin users type in the browser, scheme included.
- `COOKIE_SECURE=true` makes the session cookies HTTPS-only. Leaving it `false` behind a TLS proxy
  would send session cookies without the `Secure` flag.

Your proxy must allow request bodies of at least 11 MB through, or uploads fail before they reach
the application (see [Uploads](configuration.md#uploads)).


## Nginx

### Simple NGINX configuration, with Let's Encrypt

This is a simple nginx configuration, with automated redirection from HTTP to HTTPS and a built-in certbot root for validating the let's encrypt challenge.

```conf
server {
    listen 80;
    listen [::]:80;
    server_name ifrit.mydomain.com

    # Let's Encrypt HTTP-01 challenge (certbot --webroot -w /var/www/certbot)
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name ifrit.mydomain.com;

    ssl_certificate     /etc/letsencrypt/live/ifrit.mydomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ifrit.mydomain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL_ifrit:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000" always;

    client_max_body_size 20m;

    # ifrit
    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

!!! note
    Before the certificates are issued, the files `fullchain.pem` and `privkey.pem` would not exist and the configuration would fail. On a first launch, the TLS certificates should be self-signed, and immediately swapped out for the proper certs once obtained.


## Traefik

Untested



