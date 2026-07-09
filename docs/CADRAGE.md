# VoltFlow — cadrage V1 (honnête)

VoltFlow boucle la chaîne Meridian (`GridPulse → FlexSlot → GreenOps → VoltFlow` = data → décision → action → €) en prouvant des compétences SaaS B2B « senior » — **metered billing**, webhooks Stripe, synchronisation d'abonnement — rares dans un portfolio junior.

Ce document liste **explicitement ce que V1 ne fait pas**, pour éviter toute confusion en entretien ou en démo.

## Ce que V1 livre

- 1 plan payant (**Pro**), 1 plan implicite (**Free**)
- Checkout Stripe (mode `subscription`) + Billing Portal — flux complet côté client
- Synchronisation d'abonnement via webhooks (`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`)
- 1 gate métier réelle côté GreenOps : export PDF illimité réservé au plan Pro (Free = 10 lignes max par section)
- Traçabilité d'usage : chaque création de `flex_slot` (org Pro) génère une ligne `billing_lines`
- Tout en **Stripe test mode** — aucune carte réelle, aucun argent réel

## Ce que V2 livre (actuel)

- **Moteur tarifaire simplifié** : `kWh` (puissance × durée) × prix unitaire dynamique
- **Signal GridPulse** : intensité carbone au moment du créneau (fallback score slot ou stub)
- **Bande HP/HC** : heures pleines / creuses (Europe/Paris, simplifié)
- **Idempotence** : une seule ligne par `flex_slot_id`
- **API lecture** : `GET /api/v1/billing-lines/{org_id}`, `GET /api/v1/usage/{org_id}`
- **UI GreenOps** : cards Free/Pro, compteur usage, tableau des lignes sur `/billing`

## Ce que V1 ne faisait PAS (limites V1, corrigées en V2 partiellement)

- **Pas de TVA internationale** — pas de calcul fiscal multi-pays, pas de facture légale certifiée (Stripe Tax non activé)
- **Pas de moteur tarifaire réel** — ~~le montant de chaque `billing_line` est un **stub fixe**~~ → **V2** : calcul kWh × tarif dynamique (voir ci-dessus)
- **Un seul plan payant** — pas de tiers multiples (Starter/Pro/Enterprise)
- **Pas d'essai gratuit (trial)** — aucune gestion de période d'essai en V1
- **Pas de facturation à l'usage Stripe native** (Metered Billing / Usage Records API) — les lignes d'usage sont stockées côté Supabase pour traçabilité produit, pas poussées vers un invoice item Stripe dynamique
- **Pas de dunning / relance impayés** avancée — le statut suit simplement les événements Stripe standard

## Pourquoi ce scope

L'objectif est de **prouver l'intégration bout en bout** (Checkout → webhook → sync DB → gate produit), pas de construire un système de facturation de production. Un vrai moteur tarifaire HP-HC/spot ou une conformité fiscale multi-pays représenterait plusieurs semaines de travail supplémentaires, hors scope d'un portfolio technique.

## Prochaine étape naturelle (V2+, hors scope V1)

- Stripe Usage Records API pour une facturation à l'usage native (au lieu du stub fixe)
- Tarification dynamique basée sur les signaux GridPulse (prix spot / HP-HC réel)
- Multi-tiers (Starter / Pro / Enterprise)
