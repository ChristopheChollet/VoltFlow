# VoltFlow — dev local & branchement GreenOps

Guide pratique pour tester VoltFlow en local depuis l’espace de travail **Meridian** (GridPulse · FlexSlot · GreenOps · VoltFlow · portfolio).

---

## Ai-je besoin de lancer VoltFlow en local ?

| Besoin | Suffit ? |
|--------|----------|
| Voir le plan Pro / Free, payer, gérer l’abo | **Oui — GreenOps `/billing` suffit** (appelle VoltFlow sur Railway) |
| Démo candidature / portfolio | **Oui — prod Railway + GreenOps** |
| Débugger le code VoltFlow, modifier un endpoint | **Non — lancer VoltFlow en local** |
| Explorer l’API (`/docs`, `/health`) sans toucher à la prod | **Non — lancer VoltFlow en local** |
| Développer une feature billing (V2 VoltFlow) | **Non — local + GreenOps pointé vers `localhost:8000`** |

**Rappel :** VoltFlow n’a pas de frontend. Pas de `npm run dev`, pas de page web dédiée. L’UI utilisateur = **GreenOps → `/billing`**.

---

## Prérequis (une fois)

- [ ] Migration Supabase appliquée : [`supabase/migrations/001_subscriptions.sql`](../supabase/migrations/001_subscriptions.sql) (déjà fait si le paiement test prod a marché)
- [ ] Compte Stripe **test mode** configuré (produit Pro, `price_id`, clés API)
- [ ] Python 3.12+ sur la machine

---

## 1. Configurer VoltFlow (`.env`)

```bash
cd VoltFlow
cp .env.example .env
```

Remplir au minimum (mêmes valeurs Supabase/Stripe que Railway si vous voulez le même comportement) :

```env
SUPABASE_URL=https://<votre-projet>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role GreenOps>

STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...

VOLTFLOW_INTEGRATION_SECRET=dev-integration-secret

CHECKOUT_SUCCESS_URL=http://localhost:3000/billing?checkout=success
CHECKOUT_CANCEL_URL=http://localhost:3000/billing?checkout=cancel
BILLING_PORTAL_RETURN_URL=http://localhost:3000/billing

CORS_ORIGINS=http://localhost:3000
```

---

## 2. Lancer VoltFlow

```bash
cd VoltFlow
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Vérifications :

- [http://localhost:8000/health](http://localhost:8000/health) → `supabase_configured: true`, `stripe_configured: true`
- [http://localhost:8000/docs](http://localhost:8000/docs) → Swagger (test manuel des endpoints)

---

## 3. Pointer GreenOps vers VoltFlow local

Dans `greenops/.env.local`, modifier **uniquement** :

```env
VOLTFLOW_API_URL=http://localhost:8000
VOLTFLOW_SERVICE_KEY=dev-integration-secret
```

`VOLTFLOW_SERVICE_KEY` (GreenOps) **doit être identique** à `VOLTFLOW_INTEGRATION_SECRET` (VoltFlow).

Puis redémarrer GreenOps :

```bash
cd greenops
npm run dev
```

Tester : [http://localhost:3000/billing](http://localhost:3000/billing)

---

## 4. Webhooks Stripe en local (optionnel)

Sans ça, Checkout peut s’ouvrir mais le plan **ne passera pas à Pro** après paiement (Stripe n’atteint pas `localhost` tout seul).

**Terminal dédié** (Stripe CLI installée) :

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Copier le `whsec_...` affiché par la CLI dans `VoltFlow/.env` → `STRIPE_WEBHOOK_SECRET`, puis relancer uvicorn.

---

## 5. Revenir à la prod (Railway)

Remettre dans `greenops/.env.local` :

```env
VOLTFLOW_API_URL=https://voltflow-production.up.railway.app
VOLTFLOW_SERVICE_KEY=<clé prod partagée avec Railway VOLTFLOW_INTEGRATION_SECRET>
```

Redémarrer `npm run dev`. Aucun changement côté utilisateur : `/billing` repointe sur Railway.

---

## Récap — 2 terminaux en mode local complet

| Terminal | Commande | Rôle |
|----------|----------|------|
| 1 | `uvicorn app.main:app --reload --port 8000` (dans VoltFlow) | API billing |
| 2 | `npm run dev` (dans greenops) | UI `/billing` |
| 3 (optionnel) | `stripe listen --forward-to localhost:8000/webhooks/stripe` | Webhooks test |

---

## Tests sans serveur

```bash
cd VoltFlow
pytest
```

19 tests — signature webhook, checkout, sync abonnement (mocks, pas de réseau).

---

## Liens

- Scope V1 : [`CADRAGE.md`](./CADRAGE.md)
- Setup prod (Railway + Stripe) : [`../README.md`](../README.md)
- Narration écosystème : [`christophe-portfolio/docs/ECOSYSTEM.md`](../../christophe-portfolio/docs/ECOSYSTEM.md)
