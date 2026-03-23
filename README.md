# frps_accounting

A lightweight Django backend for `frps` plugin authentication and proxy lease accounting.

## What it does

This project provides a simple backend service for managing FRP users, access tokens, and proxy leases.

It is designed to:

- authenticate plugin requests from `frps`
- issue per-user access tokens
- validate whether a user or token is active
- track proxy lease lifecycle (`NewProxy` / `CloseProxy`)
- store basic user quota and policy settings

## Current structure

- `frps_proxy_backend/` — Django project
- `frps_proxy_backend/apps/core/` — core models, views, and service logic
- `frps_proxy_backend/apps/helloworld/` — example app

## Core models

- `User`
- `AccessToken`
- `ProxyLease`

The current data model already includes fields for user status, expiration, allowed proxy types, port range, bandwidth limits, average bandwidth window, and concurrent connection limits.

## API

### Plugin handler

```text
POST /handler?version=<version>&op=<operation>&reqid=<reqid>
````

Supported operations:

* `NewProxy`
* `CloseProxy`

### Token generation

```text
GET /generate_token?email=<user_email>
```

Returns a newly generated token for the given user when allowed.

## Development

```bash
python manage.py migrate
python manage.py runserver
```

## Author
- Umi

## License

GPL-3.0

