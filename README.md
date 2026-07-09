# VoltFlow

Micro-service de **facturation à l'usage** pour l'écosystème Meridian : Stripe Checkout, Billing Portal, webhooks d'abonnement et suivi d'usage.

4e brique Meridian — boucle la chaîne data → décision → action → € :

```
GridPulse  →  FlexSlot  →  GreenOps  →  VoltFlow
  data         décision       action        €
```

Pas de frontend dédié : l'UI billing (badge plan, page `/billing`, bouton upgrade/manage) vit dans [GreenOps](https://github.com/ChristopheChollet/GreenOps). VoltFlow reste un service API pur — comme [GridPulse/backend](https://github.com/ChristopheChollet/GridPulse), il diversifie la stack (Python/FastAPI) face aux 3 autres apps Next.js.

## Architecture

```
GreenOps (Next.js) ──service key──▶ VoltFlow (FastAPI) ──▶ Stripe (test mode)
                                         │
                                         ▼
                          Supabase (projet partagé GreenOps)
                          subscriptions · billing_lines
```

| Couche | Stack |
|--------|-------|
| API | Python 3.12, FastAPI, httpx |
| Paiement | Stripe (test mode) — Checkout Sessions, Billing Portal, Webhooks |
| DB | Supabase PostgreSQL — **même projet** que GreenOps/FlexSlot (pas de projet dédié) |
| Déploiement | Railway (Dockerfile) |

## Démarrage local

Guide pas-à-pas (GreenOps local, switch prod/local, webhooks Stripe CLI) : [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md).

### 1. Supabase

Aucun nouveau projet : VoltFlow lit/écrit sur le **même projet Supabase que GreenOps**. Exécuter [`supabase/migrations/001_subscriptions.sql`](supabase/migrations/001_subscriptions.sql) dans le SQL Editor de ce projet (après les migrations GreenOps, dont il dépend : `organizations`, `flex_slots`, `user_org_ids()`).

### 2. Stripe (test mode)

1. Créer un compte Stripe (ou utiliser un compte existant) et rester en **mode test**
2. Products → créer **"VoltFlow Pro"** avec un prix récurrent mensuel → copier le `price_id`
3. Developers → API keys → copier la clé secrète test (`sk_test_...`)
4. Developers → Webhooks → ajouter un endpoint `https://<url-voltflow>/webhooks/stripe` avec les événements :
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   → copier le secret de signature (`whsec_...`)
5. Customer Portal (Settings → Billing → Customer portal) → activer

En local, utiliser le [Stripe CLI](https://stripe.com/docs/stripe-cli) pour forwarder les webhooks :

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

### 3. Variables d'environnement

```bash
cp .env.example .env
```

Renseigner `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (mêmes valeurs que GreenOps), `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO`, `VOLTFLOW_INTEGRATION_SECRET` (même valeur que `VOLTFLOW_SERVICE_KEY` côté GreenOps).

### 4. Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Vérifier : [http://localhost:8000/health](http://localhost:8000/health).

## API

| Endpoint | Rôle |
|----------|------|
| `GET /health` | Ping — configuré Stripe/Supabase oui/non |
| `POST /checkout/session` | Crée une Checkout Session Stripe pour un org (`{ org_id, email? }`, header `X-VoltFlow-Service-Key`) |
| `POST /billing/portal` | Crée une Billing Portal Session pour un org (`{ org_id }`) |
| `GET /api/v1/subscriptions/{org_id}` | Statut d'abonnement de l'org (plan, status, période) |
| `POST /usage/record` | Enregistre une ligne d'usage stub (`{ org_id, flex_slot_id }`) — 402 si l'org n'est pas Pro |
| `POST /webhooks/stripe` | Vérifie la signature Stripe, gère `checkout.session.completed`, `customer.subscription.updated/deleted` → upsert `subscriptions` |

Toutes les routes sauf `/health` et `/webhooks/stripe` exigent le header `X-VoltFlow-Service-Key` (secret partagé avec GreenOps).

## Tests

```bash
pytest
```

Couvre : vérification de signature webhook Stripe (HMAC, sans appel réseau), création de Checkout Session / Billing Portal (SDK Stripe mocké), logique de synchronisation d'abonnement et d'enregistrement d'usage (client Supabase mocké).

## Déploiement (Railway)

- `railway.toml` + `Dockerfile` à la racine
- Variables Railway : `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO`, `VOLTFLOW_INTEGRATION_SECRET`, `CHECKOUT_SUCCESS_URL`, `CHECKOUT_CANCEL_URL`, `BILLING_PORTAL_RETURN_URL`, `CORS_ORIGINS`
- Une fois déployé, enregistrer l'URL Railway comme endpoint webhook dans le dashboard Stripe (test mode) et reporter le `STRIPE_WEBHOOK_SECRET` généré

## Limites assumées (V1)

Voir [`docs/CADRAGE.md`](docs/CADRAGE.md) pour le détail honnête du scope V1.

## Licence

MIT — Christophe Chollet
