# AutoReels — Website Setup Guide

## 1. Install website dependencies

Open PowerShell in the `website` folder and run:

```bash
pip install -r requirements.txt
```

## 2. Copy and fill in your .env

```bash
copy .env.example .env
notepad .env
```

You need the same OPENAI_API_KEY and PEXELS_API_KEY as before, plus Stripe keys.

## 3. Set up Stripe (for the $14.99 subscription)

1. Go to https://dashboard.stripe.com and create a free account
2. In the Stripe dashboard → **Products** → **Add product**
   - Name: "AutoReels Pro"
   - Price: $14.99 / month (recurring)
   - Click **Save product**
3. Copy the **Price ID** (looks like `price_1ABC...`) → paste into `.env` as `STRIPE_PRICE_ID`
4. Go to **Developers** → **API keys** → copy **Secret key** → paste as `STRIPE_SECRET_KEY`
5. Go to **Developers** → **Webhooks** → **Add endpoint**
   - URL: `http://localhost:8000/api/billing/webhook` (change to your domain later)
   - Events: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Copy the **Signing secret** → paste as `STRIPE_WEBHOOK_SECRET`

## 4. Start the server

```bash
cd website
py run.py
```

Then open **http://localhost:8000** in your browser.

## 5. Test the full flow

1. Go to http://localhost:8000 — you'll see the landing page
2. Click "Get started" → create an account
3. On the dashboard, click "Subscribe for $14.99/mo"
4. Use Stripe's test card: **4242 4242 4242 4242** (any future expiry, any CVC)
5. After subscribing, you're redirected back to the dashboard
6. Type a topic and generate your first video!

## 6. Go live (when ready)

To put this online so other people can use it:

1. Sign up at **https://railway.app** (free to start)
2. Connect your GitHub repo and deploy
3. Set all your `.env` variables in Railway's dashboard
4. Update `FRONTEND_URL` to your Railway domain
5. Update your Stripe webhook URL to your Railway domain
6. Done — your site is live!

## Folder structure

```
ai-video-generator/
├── pipeline/           ← The AI video engine
├── website/
│   ├── app.py          ← FastAPI backend (auth + Stripe + video API)
│   ├── run.py          ← Start the server with this
│   ├── requirements.txt
│   ├── .env            ← Your secret keys (never share this)
│   └── frontend/
│       ├── index.html  ← Landing page
│       ├── login.html  ← Login / signup
│       ├── dashboard.html ← Where users generate videos
│       └── style.css   ← All the styles
```
