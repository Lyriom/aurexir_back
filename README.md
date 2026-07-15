# AUREXIR API

Backend de **AUREXIR** — e-commerce de perfumería masculina (fragancias de
diseñador y nicho) para el mercado de EE. UU., con base en Nueva York.

El frontend (repo `aurexir`, Vue 3 + Vite) funciona también sin backend como
catálogo con pedidos por WhatsApp/Instagram; este API añade auth con roles,
checkout con Stripe, historial de pedidos, inventario auditado y métricas.

**Stack**: Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 ·
Pydantic v2 · JWT + argon2 · Stripe · pytest · ruff · Docker.

## Arranque rápido (Docker)

```bash
cp .env.example .env      # completa JWT_SECRET, ADMIN_PASSWORD y claves de Stripe
docker compose up --build
```

El servicio `api` aplica las migraciones (`alembic upgrade head`), ejecuta el
seed (admin + 20 productos, idempotente) y levanta Uvicorn en
<http://localhost:8000>. Docs OpenAPI en <http://localhost:8000/docs>.

Conecta el front creando `aurexir/.env` con:

```
VITE_API_URL=http://localhost:8000
```

## Desarrollo local (sin Docker)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Postgres solo en Docker; el API en local
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://aurexir:aurexir@localhost:5432/aurexir

alembic upgrade head        # migraciones
python -m app.seed          # admin + catálogo (idempotente)
uvicorn app.main:app --reload
```

## Probar Stripe en local

1. Usa claves de **modo test** (`sk_test_...`) en `.env`.
2. Reenvía los webhooks a tu máquina:

   ```bash
   stripe listen --forward-to localhost:8000/webhooks/stripe
   ```

   Copia el `whsec_...` que imprime a `STRIPE_WEBHOOK_SECRET` en `.env` y
   reinicia el API.
3. Flujo completo: regístrate desde el front → carrito → checkout → paga con la
   tarjeta de prueba `4242 4242 4242 4242` (cualquier fecha futura y CVC). El
   webhook marca la orden `paid`, descuenta stock y la orden aparece en
   `/orders/mine` y en las métricas de admin.

> **Stripe Tax**: el checkout se crea con `automatic_tax` habilitado (registro
> en NY). Si la cuenta no tiene Stripe Tax activo, la sesión se reintenta sin
> impuestos y `Order.tax` queda en 0.

## Tests y lint

```bash
pytest        # SQLite in-memory; no necesita Postgres ni red
ruff check . && ruff format --check .
```

## Endpoints

### Público
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Alta de cliente → `{access_token, user}` |
| POST | `/auth/login` | Login (rate-limited) → `{access_token, user}` |
| GET | `/auth/me` | Usuario actual (Bearer) |
| GET | `/products` | Catálogo activo (forma idéntica a `products.js` del front) |
| GET | `/products/{slug}` | Detalle de producto |
| POST | `/shipping/quote` | `{items, method}` → subtotal, envío y total estimado |
| POST | `/newsletter` | Alta idempotente (201 nueva, 200 repetida); genera un código de 15% (uno por email) y lo envía vía Resend |
| POST | `/discounts/validate` | `{code}` → `{valid, code, percent}` (siempre 200) |
| GET | `/health` | Healthcheck |

### Cliente autenticado
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/checkout/session` | Crea Order `pending` + Stripe Checkout → `{checkout_url}`; acepta `discount_code` (15% sobre el subtotal, cupón en Stripe; el webhook lo consume al pagar) |
| GET | `/orders/mine` | Historial propio con items, más reciente primero |

### Webhook
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/webhooks/stripe` | `checkout.session.completed` → `paid` + descuento de stock; `expired` → `canceled`. Firma verificada. |

### Admin (role=admin; si no, 403)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/metrics?days=30` | Ingresos, nº pedidos, AOV, serie por día, top productos, bajo stock, clientes nuevos |
| GET | `/admin/orders?status=` | Todos los pedidos, filtrables |
| PATCH | `/admin/orders/{id}` | Cambio de estado (paid→shipped→delivered; cancelar repone stock) |
| GET | `/admin/products` | Catálogo completo, incluidos inactivos |
| POST | `/admin/products` | Crear producto |
| PATCH | `/admin/products/{id}` | Editar campos (acepta uuid o slug) |
| PATCH | `/admin/products/{id}/stock` | Fijar stock; el delta queda en `InventoryMovement` |

## Reglas de negocio clave

- **Precios**: el cliente envía solo `{id, qty}`; los importes salen siempre de
  la base de datos y van a Stripe en centavos (USD).
- **Envío** (solo EE. UU., tarifa plana sin ZIP): gratis si subtotal ≥
  `FREE_SHIPPING_THRESHOLD` ($200); si no, `standard` $20 o `eco` $30 (envío
  ecológico). La misma función (`app/services/shipping.py`) alimenta el quote
  y la Checkout Session.
- **Stock**: se valida al crear la sesión pero se descuenta **solo** cuando el
  webhook confirma el pago. Todo cambio pasa por `app/services/inventory.py` y
  deja un `InventoryMovement` (`sale | restock | manual | cancel`).
- **Invitados**: el catálogo, el quote y la newsletter son públicos; solo
  `/checkout/session` y `/orders/mine` requieren sesión.

## Estructura

```
app/
├── main.py            # create_app: CORS, rate-limit, routers, /health
├── config.py          # Settings (pydantic-settings, .env)
├── database.py        # engine, SessionLocal, get_db
├── security.py        # argon2, JWT, get_current_user, require_admin
├── seed.py            # admin + catálogo (python -m app.seed)
├── models/            # User, Product, InventoryMovement, Order(+Item), Newsletter
├── schemas/           # Pydantic por dominio (forma camelCase del front)
├── routers/           # auth, products, shipping, checkout, orders, newsletter, admin, webhooks
└── services/          # shipping, cart, inventory, orders, stripe_service, metrics
```

El catálogo del seed (`app/data/products_seed.json`) se genera desde
`../aurexir/src/data/products.js`; para regenerarlo:

```bash
node --input-type=module -e "
import { products } from '../aurexir/src/data/products.js'
import { writeFileSync } from 'node:fs'
writeFileSync('app/data/products_seed.json', JSON.stringify(products, null, 2) + '\n')"
```
