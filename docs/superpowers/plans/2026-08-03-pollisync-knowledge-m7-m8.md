# PolliSync Phase 2 — Knowledge & Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Supabase RAG knowledge base and give AI assistant full access to live farm data, ML predictions, and knowledge context.

**Architecture:** Seed agricultural knowledge into Supabase vector store, inject live weather/NDVI/bee data + ML predictions into agent context for informed responses.

**Tech Stack:** Supabase Vector Store (pgvector), SQLAlchemy, FastAPI

## Global Constraints

- Backend runs on Python 3.x with FastAPI
- All environment variables go in `backend/.env` and `.env.example`
- Each module must be tested and committed before starting the next
- Agent must gracefully handle missing knowledge base
- Generic chat must work without farm context

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/agent/embedder.py` | Verify SupabaseVectorStore works |
| `backend/app/agent/router.py` | Add live data injection to chat |
| `backend/data/knowledge/` | **NEW** — agricultural knowledge documents |
| `backend/scripts/seed_embeddings.py` | Seed knowledge base |
| `backend/app/api/routes/agent.py` | Add context endpoint |

---

## Task 1: Verify Supabase Vector Store (M7)

**Files:**
- Verify: `backend/app/agent/embedder.py`
- Test: `backend/tests/test_rag.py`

**Interfaces:**
- Consumes: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` env vars
- Produces: Verified vector store connection

- [ ] **Step 1: Write test for vector store**

Create `backend/tests/test_rag.py`:
```python
import pytest
from app.agent.embedder import SupabaseVectorStore

def test_vector_store_initializes():
    store = SupabaseVectorStore()
    assert store is not None

def test_vector_store_count():
    store = SupabaseVectorStore()
    count = store.count()
    assert isinstance(count, int)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_rag.py -v`
Expected: PASS (embedder already exists)

- [ ] **Step 3: Verify table exists in Supabase**

Run: `cd backend && ..\.venv\Scripts\python.exe -c "from app.agent.embedder import SupabaseVectorStore; store = SupabaseVectorStore(); print('Table exists, count:', store.count())"`

- [ ] **Step 4: Commit RAG verification**

```bash
git add backend/tests/test_rag.py
git commit -m "feat(m7): verify supabase vector store connection"
```

---

## Task 2: Create Knowledge Base Documents (M7)

**Files:**
- Create: `backend/data/knowledge/*.md`
- Run: `backend/scripts/seed_embeddings.py`

**Interfaces:**
- Produces: Seeded knowledge chunks in Supabase

- [ ] **Step 1: Create knowledge directory**

```bash
mkdir -p backend/data/knowledge
```

- [ ] **Step 2: Create crop-specific guides**

Create `backend/data/knowledge/mustard.md`:
```markdown
# Mustard Farming Best Practices

## Planting
- Optimal planting time: October-November in Maharashtra
- Seed rate: 5-6 kg/ha
- Row spacing: 30 cm

## Water Management
- Critical stages: flowering and seed filling
- Irrigate at 25-30% soil moisture depletion

## Pest Management
- Common pests: Aphids, Sawfly, Painted bug
- Use yellow sticky traps for monitoring

## Harvesting
- Harvest when 75-80% pods turn brown
- Optimal moisture content: 8-10%
```

Create `backend/data/knowledge/wheat.md`:
```markdown
# Wheat Farming Best Practices

## Planting
- Optimal planting time: November-December
- Seed rate: 100-125 kg/ha
- Seed depth: 5-6 cm

## Water Management
- Critical stages: Crown root, Tillering, Flowering
- 4-6 irrigations recommended

## Nutrient Management
- Apply 120 kg N, 60 kg P2O5, 40 kg K2O per hectare
```

Create `backend/data/knowledge/pollination.md`:
```markdown
# Pollination Best Practices

## Importance
- 75% of crop species depend on pollinators
- Pollination increases yield by 20-30%

## Supporting Pollinators
- Plant pollinator-friendly border crops
- Avoid pesticide spraying during flowering
- Maintain natural habitats near farms

## Bee-Friendly Practices
- Provide water sources for bees
- Grow diverse flowering plants
- Use integrated pest management
```

- [ ] **Step 3: Seed embeddings**

Run: `cd backend && ..\.venv\Scripts\python.exe scripts/seed_embeddings.py`
Expected: Embeddings stored in Supabase

- [ ] **Step 4: Verify seeded count**

Run: `cd backend && ..\.venv\Scripts\python.exe -c "from app.agent.embedder import SupabaseVectorStore; store = SupabaseVectorStore(); print('Seeded chunks:', store.count())"`
Expected: count > 5

- [ ] **Step 5: Commit knowledge base**

```bash
git add backend/data/knowledge/
git commit -m "feat(m7): add agricultural knowledge base documents"
```

---

## Task 3: Inject Live Data into Agent Context (M8)

**Files:**
- Modify: `backend/app/agent/router.py`
- Create: `backend/app/api/routes/agent.py` (if not exists)

**Interfaces:**
- Consumes: `weather_service`, `environment_service`, `bee_service`, `prediction_service`
- Produces: Agent chat with live farm context

- [ ] **Step 1: Read current agent router**

Read `backend/app/agent/router.py` to understand current implementation.

- [ ] **Step 2: Add live data assembly function**

Add to `backend/app/agent/router.py`:
```python
from datetime import date
from app.services.weather_service import get_weather_with_cache
from app.services.environment_service import get_environment_features
from app.services.bee_service import get_bee_data_with_cache

async def assemble_farm_context(farm_id: str, db: Session) -> str:
    """Assemble live farm data for agent context."""
    from app.models.farm import Farm
    from app.models.prediction import Prediction
    
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        return ""
    
    # Get latest prediction
    prediction = (
        db.query(Prediction)
        .filter(Prediction.farm_id == farm_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    
    # Get live weather
    try:
        weather = await get_weather_with_cache(str(farm.id), farm.latitude, farm.longitude, db)
        weather_info = f"Temperature: {weather.get('current', {}).get('temperature_2m', 'N/A')}°C, Humidity: {weather.get('current', {}).get('relative_humidity_2m', 'N/A')}%"
    except Exception:
        weather_info = "Weather data unavailable"
    
    # Get bee data
    try:
        bee_data = await get_bee_data_with_cache(str(farm.id), farm.latitude, farm.longitude, db)
        bee_info = f"Bee species richness: {bee_data.get('richness', 'N/A')}"
    except Exception:
        bee_info = "Bee data unavailable"
    
    # Get prediction info
    if prediction:
        pred_info = f"Risk level: {prediction.risk_level}, PSI: {prediction.psi_score}"
    else:
        pred_info = "No prediction available"
    
    context = f"""
Live farm conditions:
Crop: {farm.crop_type}
District: {farm.location_name or 'Unknown'}

Weather: {weather_info}
Bee Data: {bee_info}
Prediction: {pred_info}
"""
    return context
```

- [ ] **Step 3: Modify chat endpoint to inject context**

Update the chat endpoint in `router.py` to call `assemble_farm_context` when `farm_id` is provided.

- [ ] **Step 4: Add context debugging endpoint**

Add to `backend/app/api/routes/agent.py`:
```python
@router.get("/context")
async def get_agent_context(farm_id: str, db: Session = Depends(get_db)):
    """Debug endpoint to see assembled agent context."""
    from app.agent.router import assemble_farm_context
    context = await assemble_farm_context(farm_id, db)
    return {"context": context}
```

- [ ] **Step 5: Commit agent context injection**

```bash
git add backend/app/agent/router.py backend/app/api/routes/agent.py
git commit -m "feat(m8): inject live farm data into agent context"
```

---

## Task 4: Full Integration Test (M7-M8)

**Files:**
- Test: Manual verification

**Interfaces:**
- Consumes: All M7-M8 implementations
- Produces: Verified agent with live data

- [ ] **Step 1: Test RAG knowledge retrieval**

Ask agent: "What are best practices for mustard farming?" → should return knowledge from seeded docs.

- [ ] **Step 2: Test live weather in agent response**

Ask agent: "What is the weather at my farm?" → should quote real weather numbers.

- [ ] **Step 3: Test prediction data in agent response**

Ask agent: "What is my risk level?" → should quote actual prediction data.

- [ ] **Step 4: Test generic chat without farm**

Send chat without farm_id → should still work with generic responses.

---

## Definition of Done — Plan C

- [ ] M7: Knowledge base seeded, count > 5, agent retrieves relevant docs
- [ ] M8: Agent injects live weather/bee/prediction data into context
- [ ] All code committed with descriptive messages
- [ ] Integration tests passing
