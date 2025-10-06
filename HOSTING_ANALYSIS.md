# DinkyDash Hosted Platform: Architecture & Hosting Analysis

## Executive Summary

This document outlines the strategy for transforming DinkyDash from a single-tenant Raspberry Pi application into a multi-tenant hosted platform while maintaining Pi compatibility.

**Recommended Stack**: Next.js 14 + Supabase (PostgreSQL) + Vercel
**Estimated MVP Cost**: $0-25/month
**Development Time**: 8-12 weeks

---

## Current Architecture Analysis

### Existing System
- **Type**: Single-tenant, file-based
- **Stack**: Python Flask + YAML config + Local images
- **Deployment**: Raspberry Pi (local network)
- **Auth**: None
- **Data Model**:
  - Recurring items (daily rotation based on day-of-year)
  - Countdowns (date-based events)

### Key Constraints
1. Must remain easy to deploy on Raspberry Pi
2. Lightweight enough for low-powered devices
3. Simple configuration (current YAML approach works well)

---

## Transformation Strategy

### Core UX Principles

#### 1. Dual-Mode Experience
- **View Mode**: Clean, distraction-free dashboard (current experience)
- **Edit Mode**: Visual configuration interface with drag-and-drop
- **Toggle**: Single button to switch modes (authenticated users only)

#### 2. Progressive Complexity
- **Level 1**: Template gallery (pre-configured dashboards)
- **Level 2**: Simple customization (change names, dates, emojis)
- **Level 3**: Advanced editing (add/remove cards, reorder, upload images)

#### 3. Raspberry Pi Compatibility Strategy
- **Hybrid Architecture**: Dashboard works both online and offline
- **Sync Model**: Python script pulls config from API, caches locally
- **Fallback Mode**: Existing file-based config still works (backward compatible)

---

## Hosting Options Analysis

### Option 1: Firebase (Google Cloud) 🔥

#### What You Get
- App hosting (Cloud Functions + Firebase Hosting)
- Firestore (NoSQL database)
- Authentication (email, OAuth, magic links)
- Cloud Storage (images)
- Global CDN

#### Infrastructure Management
**Complexity**: ⭐⭐⭐⭐⭐ (Easiest - ~5% management)

**What Firebase Manages**:
- ✅ Auto-scaling (zero config)
- ✅ SSL certificates (automatic)
- ✅ CDN/edge caching (built-in)
- ✅ Database backups (automatic)
- ✅ DDoS protection
- ✅ Monitoring & logs

**What You Manage**:
- Security rules (Firestore access control)
- Billing alerts

#### Pricing
- **Free Tier (Spark)**: 1GB storage, 10GB bandwidth/month, 50K reads/day
- **Paid (Blaze)**: Pay-as-you-go, ~$5-20/month at moderate scale

#### Pros & Cons
**Pros**:
- 🚀 Zero DevOps (deploy and forget)
- 🌍 Global CDN included
- 🔐 Built-in auth
- 📱 Real-time database (live updates)
- 🔧 Single platform for everything

**Cons**:
- 📦 Vendor lock-in (hard to migrate)
- 🗄️ NoSQL only (Firestore is document-based)
- 💰 Can get expensive at scale
- 🔍 Query limitations

---

### Option 2: Supabase + Vercel 💚⚡ **[RECOMMENDED]**

#### What You Get
**Supabase**:
- PostgreSQL database (managed)
- Authentication (same features as Firebase)
- Storage (S3-compatible)
- Auto-generated REST + GraphQL APIs
- Row-level security (database-level auth)

**Vercel**:
- Next.js hosting (serverless + edge)
- Automatic deployments (git push)
- Preview environments
- CDN & caching

#### Infrastructure Management
**Complexity**: ⭐⭐⭐⭐ (Very Easy - ~20% management)

**What's Managed**:
- ✅ PostgreSQL (Supabase: upgrades, backups, scaling)
- ✅ Connection pooling (Supabase: automatic)
- ✅ Next.js hosting (Vercel: builds, deploys, CDN)
- ✅ SSL & monitoring (both platforms)

**What You Manage**:
- Database schema migrations (via Supabase CLI)
- Row-level security policies (SQL-based)
- Environment variables (one-time setup)

#### Pricing
**Supabase Free Tier**:
- 500MB database
- 1GB file storage
- 50K monthly active users
- Unlimited API requests
- **Note**: Projects pause after 7 days inactivity (Pro plan fixes this)

**Supabase Pro**: $25/month
- 8GB database
- 100GB storage
- No pausing
- Daily backups

**Vercel Free Tier**:
- 100GB bandwidth
- Unlimited deployments
- Serverless functions

**Vercel Pro**: $20/month (team features, more bandwidth)

**Total MVP Cost**: $0 (free tiers) → $25-45/month (paid)

#### Pros & Cons
**Pros**:
- 🗄️ PostgreSQL (full SQL, relational data, powerful queries)
- 🔓 Open source (can self-host if needed)
- 🛠️ Excellent developer experience (auto-generated APIs, type-safe)
- 🔐 Row-level security (database enforces auth rules)
- 📊 Built-in SQL editor
- 🚀 Vercel's superior Next.js integration (streaming, edge, previews)

**Cons**:
- 🏗️ Two platforms to configure (Supabase + Vercel)
- 📚 Learning curve (Postgres + RLS policies)
- 💾 Free tier pauses (need Pro for always-on)

#### Database Schema Example
```sql
CREATE TABLE dashboards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users NOT NULL,
  slug text UNIQUE NOT NULL,
  name text NOT NULL,
  recurring jsonb DEFAULT '[]',
  countdowns jsonb DEFAULT '[]',
  settings jsonb DEFAULT '{}',
  is_public boolean DEFAULT false,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Row-level security
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own dashboards"
  ON dashboards FOR SELECT
  USING (auth.uid() = user_id OR is_public = true);

CREATE POLICY "Users can update their own dashboards"
  ON dashboards FOR UPDATE
  USING (auth.uid() = user_id);
```

---

### Option 3: DigitalOcean (App Platform) 🌊

#### What You Get
- App Platform (managed container hosting)
- Managed PostgreSQL/MySQL/Redis
- Spaces (S3-compatible storage + CDN)

#### Infrastructure Management
**Complexity**: ⭐⭐⭐ (Moderate - ~40% management)

**What's Managed**:
- ✅ Container orchestration
- ✅ Database backups (daily)
- ✅ SSL certificates
- ✅ Load balancing
- ✅ Auto-scaling (with manual config)

**What You Manage**:
- Database connection setup (manual)
- Environment variables
- Scaling plan upgrades
- Auth implementation (DIY - use NextAuth)

#### Pricing
**No Free Tier** - Minimum costs:
- **App Platform Basic**: $5/month (512MB RAM)
- **Managed Postgres**: $15/month (1GB RAM, 10GB storage)
- **Spaces Storage**: $5/month (250GB + 1TB bandwidth)

**Total MVP Cost**: ~$25/month minimum

#### Pros & Cons
**Pros**:
- 🏢 Traditional VPS-style hosting
- 💪 Full control (SSH access if needed)
- 📦 Single vendor (app + DB + storage)
- 💰 Predictable flat pricing
- 🔧 Flexible (any runtime, any database)

**Cons**:
- 💸 No free tier ($25/month from day 1)
- 🛠️ More manual configuration
- 📈 Manual scaling (upgrade plans yourself)
- 🚫 No built-in auth (need NextAuth.js)
- ⏱️ Slower deployments (not instant like Vercel)

---

### Option 4: Railway (Simplified PaaS)

#### What You Get
- App hosting (any runtime)
- PostgreSQL/MySQL/Redis (managed)
- Persistent volumes (for SQLite if desired)
- Auto-deploy from GitHub

#### Infrastructure Management
**Complexity**: ⭐⭐⭐⭐ (Easy - ~25% management)

**Pricing**:
- **Free Tier**: $5 credit/month (runs small apps)
- **Paid**: Pay-as-you-go (~$10-20/month for small apps)

#### Pros & Cons
**Pros**:
- 🎯 Simplest traditional hosting (like Heroku)
- 🔧 Support for SQLite + any other DB
- 📊 Nice dashboard UI
- 🚀 Git-based auto-deploy

**Cons**:
- 🌍 Single region (no global edge)
- 💰 Credits run out on free tier
- 🔐 No built-in auth

---

## Comparison Matrix

| Factor | Firebase | Supabase + Vercel | DigitalOcean | Railway |
|--------|----------|-------------------|--------------|---------|
| **Setup Time** | 10 min | 30 min | 1-2 hours | 20 min |
| **Infrastructure Management** | ~5% | ~20% | ~40% | ~25% |
| **Free Tier** | ✅ Generous | ✅ Good* | ❌ None | ✅ Limited |
| **Database** | NoSQL (Firestore) | PostgreSQL | PostgreSQL | Any |
| **Built-in Auth** | ✅ Yes | ✅ Yes | ❌ DIY | ❌ DIY |
| **Auto-scaling** | ✅ Yes | ✅ Yes (app) | ⚠️ Manual | ✅ Yes |
| **Global CDN/Edge** | ✅ Yes | ✅ Yes (Vercel) | ✅ Spaces CDN | ❌ No |
| **Vendor Lock-in** | ⚠️ High | ✅ Low (OSS) | ✅ Low | ✅ Low |
| **Real-time Database** | ✅ Native | ✅ Native | ❌ DIY | ❌ DIY |
| **Cost at Scale** | $$$ | $$ | $$ | $$ |
| **Best For** | Zero DevOps | SQL + Modern DX | Full control | Simple PaaS |

*Supabase free tier pauses after 7 days inactivity

---

## Recommended Tech Stack

### **Primary Recommendation: Supabase + Vercel**

#### Why This Combination?
1. **Best developer experience**:
   - Type-safe database with Prisma or Supabase client
   - Vercel's instant deployments & preview environments
   - Auto-generated APIs from database schema

2. **Optimal cost structure**:
   - Start free (both platforms)
   - Scale incrementally ($25/month for Supabase Pro, $20/month for Vercel Pro)
   - No surprise bills (clear pricing tiers)

3. **Production-ready features**:
   - PostgreSQL (relational data, complex queries)
   - Row-level security (database-enforced auth)
   - Edge caching (Vercel CDN)
   - Real-time subscriptions (if needed later)

4. **Minimal infrastructure management**:
   - Supabase: Just write SQL migrations
   - Vercel: Just git push
   - Both handle scaling, backups, SSL, monitoring

5. **Future-proof**:
   - Open source (Supabase) = can self-host if needed
   - Standard Postgres = easy to migrate
   - Next.js = industry standard

#### Full Stack
```
Frontend:  Next.js 14 (App Router) + React Server Components
UI:        shadcn/ui (Radix UI + Tailwind CSS)
Backend:   Next.js API Routes / Server Actions
Database:  Supabase (PostgreSQL)
Auth:      Supabase Auth (magic link + OAuth)
Storage:   Supabase Storage (S3-compatible)
Hosting:   Vercel (serverless + edge)
ORM:       Prisma or Supabase Client (type-safe)
```

#### Development Workflow
```bash
# Setup (5 minutes)
npx create-next-app@latest dinkydash --app
cd dinkydash
npx supabase init

# Local development
supabase start          # Local Postgres in Docker
npm run dev            # Next.js dev server

# Deploy
git push origin main   # Vercel auto-deploys
supabase db push       # Deploy schema changes
```

---

### **Alternative: Firebase** (If All-in-One Preferred)

Choose Firebase if:
- You want absolute simplest setup (single vendor)
- NoSQL data model fits your needs
- You plan to add real-time collaboration
- You prefer Google Cloud ecosystem

#### Full Stack
```
Frontend:  Next.js 14
Backend:   Firebase Cloud Functions (Node.js)
Database:  Firestore (NoSQL)
Auth:      Firebase Auth
Storage:   Firebase Storage
Hosting:   Firebase Hosting
```

---

## Raspberry Pi Integration Strategy

### Hybrid Architecture Approach

#### Option A: API Sync (Recommended)
**How it works**:
1. User creates dashboard on web app
2. Dashboard gets unique URL: `dinkydash.com/john/family`
3. Raspberry Pi runs lightweight Python sync script
4. Script pulls config via API every hour
5. Local Flask app displays dashboard (current code, minimal changes)
6. Works offline with cached config

**Implementation**:
```python
# pi_sync.py - Runs on Raspberry Pi
import requests
import yaml
import schedule
import time

DASHBOARD_URL = "https://dinkydash.com/api/dashboards/john/family"
LOCAL_CONFIG = "/home/pi/dinkydash/config.yaml"

def sync_dashboard():
    response = requests.get(DASHBOARD_URL)
    if response.ok:
        config = response.json()
        with open(LOCAL_CONFIG, 'w') as f:
            yaml.dump(config, f)
        print("Dashboard synced")

# Sync every hour
schedule.every(1).hours.do(sync_dashboard)

# Initial sync
sync_dashboard()

while True:
    schedule.run_pending()
    time.sleep(60)
```

**API Endpoint** (Next.js):
```typescript
// app/api/dashboards/[username]/[slug]/route.ts
export async function GET(
  request: Request,
  { params }: { params: { username: string; slug: string } }
) {
  const { username, slug } = params

  const dashboard = await supabase
    .from('dashboards')
    .select('*')
    .eq('slug', slug)
    .eq('is_public', true)
    .single()

  if (!dashboard) {
    return Response.json({ error: 'Not found' }, { status: 404 })
  }

  // Return in YAML-compatible format
  return Response.json({
    recurring: dashboard.recurring,
    countdowns: dashboard.countdowns
  })
}
```

#### Option B: Local-Only Mode (Backward Compatible)
- Keep existing file-based `config.yaml` approach
- No cloud dependency
- For users who don't want hosted version

#### Setup Script
```bash
# One-command Pi setup
curl -sSL https://get.dinkydash.com | bash

# Interactive prompts:
# 1. Cloud-synced or local-only?
# 2. If cloud: Enter dashboard URL
# 3. Install dependencies, configure systemd service
```

---

## Feature Roadmap

### Phase 1: MVP (4-6 weeks)
**Core Infrastructure**:
- [ ] User authentication (magic link email)
- [ ] Database schema & migrations
- [ ] Dashboard CRUD operations
- [ ] Public/private toggle
- [ ] Image upload to cloud storage

**Dashboard Editor**:
- [ ] Create new dashboard with unique slug
- [ ] Add/edit/delete recurring items
- [ ] Add/edit/delete countdowns
- [ ] Upload images (drag & drop)
- [ ] Preview before publishing

**Dashboard View**:
- [ ] Responsive card layout (current design)
- [ ] Auto-refresh (60 seconds)
- [ ] Public URL sharing

### Phase 2: Enhanced UX (3-4 weeks)
- [ ] Template gallery (pre-built dashboards)
- [ ] Duplicate dashboard feature
- [ ] Drag-and-drop reordering
- [ ] Theme customization (fonts, colors, card styles)
- [ ] QR code generation (for Pi setup)
- [ ] Dashboard analytics (view count)

### Phase 3: Raspberry Pi Integration (2-3 weeks)
- [ ] Public API endpoint (`GET /api/dashboards/{username}/{slug}`)
- [ ] Python sync script for Pi
- [ ] Offline fallback (cached config)
- [ ] One-click setup script
- [ ] Migration tool (YAML → hosted)
- [ ] Documentation & tutorials

### Phase 4: Advanced Features (Future)
- [ ] Multiple dashboards per user
- [ ] Collaboration (share edit access)
- [ ] Custom widgets (weather, calendar, custom HTML)
- [ ] Mobile app (PWA or React Native)
- [ ] Webhooks & integrations
- [ ] Premium themes

---

## User Experience Flows

### New User Journey (Web)
1. **Landing page** → "Create Your Dashboard" CTA
2. **Sign up** → Magic link email (passwordless)
3. **Template gallery** → Choose starter or blank
4. **Guided setup**:
   - Add family members (upload photos)
   - Add first countdown (birthday picker)
   - Customize theme
5. **Preview** → See dashboard before publishing
6. **Publish** → Get URL + QR code for Pi

### Raspberry Pi User Journey
1. **One-line install**: `curl -sSL get.dinkydash.com | bash`
2. **Setup wizard**:
   - Mode: Cloud-synced or local-only?
   - If cloud: Enter dashboard URL or scan QR
   - Configure display settings
3. **Auto-start**: Dashboard launches on boot
4. **Sync**: Updates hourly from web dashboard

### Dashboard Editing Flow
1. **View mode** (default): Clean display
2. **Click "Edit"** → Enter edit mode
3. **Visual editor**:
   - Drag to reorder cards
   - Click card to edit inline
   - Upload images via drag-drop
   - Add new items with "+" button
4. **Save** → Returns to view mode
5. **Pi auto-syncs** within 1 hour

---

## Technical Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│          Web Application (Next.js)              │
│                                                 │
│  ┌──────────────┐      ┌────────────────────┐  │
│  │ Public View  │      │ Authenticated      │  │
│  │ Dashboard    │◄─────┤ Editor             │  │
│  │              │      │ (Drag & Drop)      │  │
│  └──────────────┘      └────────────────────┘  │
│         │                        │              │
│         ▼                        ▼              │
│  ┌──────────────────────────────────────────┐  │
│  │   Next.js API Routes / Server Actions    │  │
│  └──────────────────────────────────────────┘  │
│                      │                          │
└──────────────────────┼──────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │     Supabase Backend        │
         │                             │
         │  ┌─────────────────────┐    │
         │  │ PostgreSQL          │    │
         │  │ - Users             │    │
         │  │ - Dashboards        │    │
         │  │ - Items             │    │
         │  └─────────────────────┘    │
         │                             │
         │  ┌─────────────────────┐    │
         │  │ Auth (Row-Level     │    │
         │  │ Security)           │    │
         │  └─────────────────────┘    │
         │                             │
         │  ┌─────────────────────┐    │
         │  │ Storage (Images)    │    │
         │  └─────────────────────┘    │
         └─────────────────────────────┘
                       │
                       │ HTTPS API
                       │
                       ▼
         ┌─────────────────────────────┐
         │      Raspberry Pi           │
         │                             │
         │  ┌─────────────────────┐    │
         │  │ Python Sync Script  │    │
         │  │ (Hourly cron)       │    │
         │  └─────────────────────┘    │
         │            │                │
         │            ▼                │
         │  ┌─────────────────────┐    │
         │  │ config.yaml         │    │
         │  │ (Cached locally)    │    │
         │  └─────────────────────┘    │
         │            │                │
         │            ▼                │
         │  ┌─────────────────────┐    │
         │  │ Flask App           │    │
         │  │ (Display only)      │    │
         │  └─────────────────────┘    │
         └─────────────────────────────┘
                       │
                       ▼
                 [HDMI Display]
```

---

## Database Schema Design

### Users Table
```sql
-- Managed by Supabase Auth
-- auth.users (built-in)
```

### Dashboards Table
```sql
CREATE TABLE dashboards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  slug text UNIQUE NOT NULL,
  name text NOT NULL,
  is_public boolean DEFAULT false,
  settings jsonb DEFAULT '{
    "theme": "light",
    "font": "Luckiest Guy",
    "cardStyle": "default"
  }',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  CONSTRAINT slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

CREATE INDEX idx_dashboards_user_id ON dashboards(user_id);
CREATE INDEX idx_dashboards_slug ON dashboards(slug);
```

### Recurring Items Table
```sql
CREATE TABLE recurring_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dashboard_id uuid REFERENCES dashboards(id) ON DELETE CASCADE,
  title text NOT NULL,
  position integer NOT NULL,
  choices jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz DEFAULT now(),

  -- choices format: [
  --   {"type": "image", "url": "https://..."},
  --   {"type": "emoji", "value": "🎉"}
  -- ]
);

CREATE INDEX idx_recurring_dashboard ON recurring_items(dashboard_id);
```

### Countdowns Table
```sql
CREATE TABLE countdowns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dashboard_id uuid REFERENCES dashboards(id) ON DELETE CASCADE,
  title text NOT NULL,
  date text NOT NULL, -- MM/DD format
  image_url text,
  position integer NOT NULL,
  created_at timestamptz DEFAULT now(),

  CONSTRAINT date_format CHECK (date ~ '^\d{2}/\d{2}$')
);

CREATE INDEX idx_countdowns_dashboard ON countdowns(dashboard_id);
```

### Row-Level Security Policies
```sql
-- Dashboards
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public dashboards are viewable by everyone"
  ON dashboards FOR SELECT
  USING (is_public = true);

CREATE POLICY "Users can view their own dashboards"
  ON dashboards FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own dashboards"
  ON dashboards FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own dashboards"
  ON dashboards FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own dashboards"
  ON dashboards FOR DELETE
  USING (auth.uid() = user_id);

-- Recurring Items (inherit dashboard permissions)
ALTER TABLE recurring_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Items viewable if dashboard is viewable"
  ON recurring_items FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM dashboards
      WHERE dashboards.id = recurring_items.dashboard_id
      AND (dashboards.is_public = true OR dashboards.user_id = auth.uid())
    )
  );

-- Similar policies for countdowns...
```

---

## Migration Strategy

### For Existing Raspberry Pi Users

#### Backward Compatibility
1. **Keep existing Flask app** as `dinkydash-local`
2. **New sync client** as `dinkydash-sync`
3. **User choice** at install:
   - Cloud-synced: Pulls from web dashboard
   - Local-only: Uses current file-based approach

#### Upgrade Path
```bash
# Existing users can opt-in
cd ~/dinkydash
./upgrade.sh --mode=sync --url=https://dinkydash.com/john/family

# Or stay local-only
./upgrade.sh --mode=local
```

#### Migration Tool
```bash
# Convert existing config.yaml to hosted dashboard
dinkydash migrate --from=config.yaml --to=https://dinkydash.com

# Interactive prompts:
# 1. Create account / login
# 2. Upload images from static/
# 3. Create dashboard from YAML
# 4. Get shareable URL
```

---

## Security Considerations

### Authentication
- **Magic link email** (passwordless) for simplicity
- **OAuth** (Google, GitHub) for convenience
- **Session management** via Supabase Auth (JWT tokens)

### Data Privacy
- **Row-level security** enforces data isolation
- **Public dashboards** opt-in only (default private)
- **Image uploads** scoped to user (UUID-based paths)

### API Security
- **Rate limiting** (Vercel Edge middleware)
- **CORS** configuration for Pi sync
- **API keys** for programmatic access (optional future feature)

### Raspberry Pi Security
- **HTTPS-only** API calls (no plaintext)
- **Local caching** (offline fallback)
- **No credentials stored** on Pi (public API endpoint)

---

## Cost Projections

### MVP Phase (0-100 users)
- **Supabase**: Free tier (500MB DB, 1GB storage)
- **Vercel**: Free tier (100GB bandwidth)
- **Total**: **$0/month**

### Growth Phase (100-1,000 users)
- **Supabase Pro**: $25/month (8GB DB, 100GB storage)
- **Vercel Pro**: $20/month (team features, more bandwidth)
- **Total**: **$45/month**

### Scale Phase (1,000-10,000 users)
- **Supabase**: ~$100/month (scale plan with more storage)
- **Vercel**: ~$100/month (higher bandwidth)
- **CDN**: Cloudflare R2 for images (~$10/month)
- **Total**: **~$210/month**

### Enterprise (10,000+ users)
- Migrate to self-hosted or dedicated infrastructure
- Estimated: $500-1,000/month (managed Kubernetes, dedicated DB)

---

## Success Metrics

### Technical Metrics
- **Dashboard load time**: < 1 second
- **API response time**: < 200ms (p95)
- **Uptime**: > 99.9%
- **Image upload**: < 5 seconds

### User Metrics
- **Time to first dashboard**: < 5 minutes
- **Template usage**: > 60% of new users
- **Pi sync success rate**: > 95%
- **User retention (30-day)**: > 40%

---

## Risk Analysis

### Technical Risks
1. **Supabase free tier pausing**
   - **Mitigation**: Upgrade to Pro ($25/mo) before launch
   - **Alternative**: Ping endpoint to keep alive

2. **Image storage costs**
   - **Mitigation**: Image size limits (max 2MB), compression
   - **Alternative**: Use Cloudflare R2 (cheaper at scale)

3. **Database scaling**
   - **Mitigation**: Postgres scales well to 100K+ users
   - **Alternative**: Sharding by user region if needed

### Product Risks
1. **Raspberry Pi sync reliability**
   - **Mitigation**: Offline-first design, local caching
   - **Fallback**: Local-only mode always available

2. **User migration friction**
   - **Mitigation**: One-click migration tool
   - **Support**: Keep local-only option forever

---

## Next Steps

### Immediate (Week 1)
1. Create Supabase project
2. Set up Next.js boilerplate with shadcn/ui
3. Implement database schema
4. Basic auth flow (magic link)

### Short-term (Weeks 2-4)
1. Dashboard CRUD operations
2. Image upload system
3. Visual editor UI
4. Public dashboard view

### Medium-term (Weeks 5-8)
1. Template gallery
2. Drag-and-drop reordering
3. Theme customization
4. QR code generation

### Long-term (Weeks 9-12)
1. Raspberry Pi sync API
2. Python sync script
3. Setup automation
4. Documentation & launch

---

## Conclusion

**Recommended Path Forward**:
1. **Start with Supabase + Vercel** for MVP
2. **Leverage free tiers** for initial development
3. **Build web-first**, then add Pi integration
4. **Maintain backward compatibility** with local-only mode
5. **Scale incrementally** based on user growth

This approach minimizes infrastructure management (~20% effort vs self-hosted), provides a modern developer experience, and maintains the simplicity that makes DinkyDash great for families.

**Total estimated effort**: 8-12 weeks for full MVP with Pi integration
**Infrastructure cost**: $0 to start, $25-45/month at scale
**Risk level**: Low (proven stack, generous free tiers, backward compatible)
