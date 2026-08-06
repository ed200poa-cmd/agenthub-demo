# AgentHub — AI CRM Automation Platform

A production-ready AI agent platform that integrates LangChain, Claude API, Supabase, GoHighLevel CRM, and Zapier webhook automation for intelligent sales workflow management.

**Built by Edward Kim — AI Automation Developer**

---

## What This Demonstrates

- **LangChain multi-tool AI agent** with 6 custom tools
- **Claude (claude-haiku)** as the LLM backbone via LangChain
- **Supabase** as a managed PostgreSQL + Auth backend
- **GoHighLevel CRM** webhook integration
- **Zapier** inbound + outbound automation
- **FastAPI** async Python backend
- **Railway** cloud deployment

---

## Quick Start (Demo Mode)

The app runs in demo mode with only `ANTHROPIC_API_KEY` set — no Supabase or webhook URLs required.

```bash
cd agenthub_demo
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
uvicorn main:app --reload
```

Open http://localhost:8000 and start chatting with the AI agent.

---

## How LangChain Differs from Direct Claude API

**Direct Claude API** — you call `anthropic.messages.create()` and get a text response. You manually parse it, decide what to do next, call external services, then call Claude again. All orchestration is your code.

**LangChain** — you define *tools* (Python functions) and attach them to an agent. LangChain's agent loop automatically decides which tool to call, calls it, reads the result, and decides the next step — all in a loop until it has a final answer. Your code just defines what each tool does; the LLM figures out *when* and *how* to use them.

In this project, Claude automatically:
1. Calls `crm_lookup` to find a contact
2. Calls `lead_scorer` to evaluate them
3. Calls `gohighlevel_sync` if they're Hot
4. Calls `zapier_trigger` to fire downstream automations
5. Returns a complete summary

No manual chaining required.

---

## How Supabase Replaces Traditional PostgreSQL

| Traditional | Supabase |
|---|---|
| Spin up PostgreSQL server | Managed cloud DB, no ops |
| Write migration scripts | Visual table editor + SQL |
| Build auth from scratch | Built-in JWT auth with Row Level Security |
| No realtime | Native WebSocket subscriptions |
| Manual connection pooling | Automatic pooler (pgBouncer) |

This project uses Supabase's Python client (`supabase-py`) to query contacts, log interactions, and check appointments — identical to a direct `psycopg2` connection but without the infrastructure overhead.

---

## GoHighLevel Webhook Integration

GoHighLevel is a CRM platform used by sales agencies. This integration works as follows:

1. **Inbound** (`POST /webhook/gohighlevel`): GHL sends contact events (created, updated) to this endpoint. The app saves the contact to Supabase and scores them with AI.

2. **Outbound** (`integrations/ghl_webhook.py`): When the AI agent scores a lead, it pushes the contact back to GHL via `POST` to your GHL webhook URL, updating pipeline stage:
   - Hot → `demo_scheduled`
   - Warm → `nurturing`
   - Cold → `cold_leads`

Set `GHL_WEBHOOK_URL` to your GoHighLevel catch hook URL. Without it, all GHL actions are simulated and logged in the event log.

---

## How Zapier Connects to This System

Zapier acts as middleware between this platform and 5,000+ apps:

**Inbound (Zapier → AgentHub):**
- A Zapier "Webhooks by Zapier" action posts to `POST /webhook/zapier`
- Common trigger: new HubSpot contact, Typeform submission, Gmail label, etc.
- AgentHub receives it, stores the contact, and runs AI scoring

**Outbound (AgentHub → Zapier):**
- When a lead is scored `Hot`, AgentHub fires a `POST` to your `ZAPIER_WEBHOOK_URL`
- Zapier picks it up and can: send Slack alert, create calendar invite, add to email sequence, update Google Sheets, etc.

Set `ZAPIER_WEBHOOK_URL` to your Zapier "Catch Hook" URL. Without it, triggers are simulated.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent/run` | Run AI agent with message |
| `GET` | `/agent/history/{session_id}` | Conversation history |
| `GET` | `/contacts` | List all contacts |
| `GET` | `/contacts/{id}` | Single contact |
| `POST` | `/contacts` | Create/update contact |
| `POST` | `/webhook/gohighlevel` | Receive GHL events |
| `POST` | `/webhook/zapier` | Receive Zapier triggers |
| `POST` | `/webhook/form` | New lead form submission |
| `GET` | `/health` | Service status |

---

## AI Agent Tools

| Tool | What It Does |
|---|---|
| `crm_lookup` | Search Supabase contacts by email/name/phone |
| `lead_scorer` | Score lead Hot/Warm/Cold with reasoning |
| `email_drafter` | Write personalized follow-up emails |
| `calendar_checker` | List available appointment slots |
| `gohighlevel_sync` | Push contact to GHL + update pipeline |
| `zapier_trigger` | Fire Zapier webhook with any event data |

---

## Database Schema (Supabase)

```sql
-- contacts
CREATE TABLE contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT,
  email TEXT UNIQUE,
  phone TEXT,
  score TEXT DEFAULT 'Cold',
  status TEXT DEFAULT 'new',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- interactions
CREATE TABLE interactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id UUID REFERENCES contacts(id),
  type TEXT,
  content TEXT,
  agent_response TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- appointments
CREATE TABLE appointments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id UUID REFERENCES contacts(id),
  datetime TIMESTAMPTZ,
  status TEXT DEFAULT 'available',
  notes TEXT
);
```

---

## Environment Variables

```env
ANTHROPIC_API_KEY=sk-ant-...       # Required — Claude API key
SUPABASE_URL=https://...           # Optional — uses demo data if not set
SUPABASE_ANON_KEY=eyJ...           # Optional — uses demo data if not set
GHL_WEBHOOK_URL=https://...        # Optional — simulated if not set
ZAPIER_WEBHOOK_URL=https://...     # Optional — simulated if not set
```

---

## Tech Stack

- **Python 3.12** + **FastAPI** + **Uvicorn**
- **LangChain 0.3** + **langchain-anthropic**
- **Claude claude-haiku** (fast, cost-efficient LLM)
- **Supabase** (managed PostgreSQL + realtime)
- **GoHighLevel** (CRM webhook integration)
- **Zapier** (automation webhook integration)
- **Railway** (cloud deployment)

---

## Multi-Cloud Deployment

### LLM providers

The provider is selected by the `LLM_PROVIDER` environment variable.

| `LLM_PROVIDER` | Backing service | Agent tool calling | Connection check |
|---|---|---|---|
| `anthropic` (default) | Anthropic API | `ChatAnthropic` | `test_provider.py` |
| `bedrock` | AWS Bedrock Runtime | `ChatBedrockConverse` | `test_provider.py`, verified |
| `vertexai` | Google Cloud Vertex AI | | `test_provider.py`, verified |

Providers in the **Agent tool calling** column return a LangChain `BaseChatModel`, so the agent's tool-calling logic is identical across them.

`anthropic` runs on the base install. The others need the optional dependencies:

```bash
pip install -r providers/requirements-multicloud.txt
```

```env
LLM_PROVIDER=anthropic                                    # anthropic | bedrock | vertexai
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
AWS_REGION=us-east-1
GCP_PROJECT_ID=your-gcp-project
GCP_LOCATION=us-central1
VERTEX_MODEL_ID=gemini-3.6-flash
```

`test_provider.py` sends one prompt through a single provider to check credentials and model access:

```bash
LLM_PROVIDER=anthropic python3 test_provider.py "What is 2+2?"
LLM_PROVIDER=bedrock   python3 test_provider.py "What is 2+2?"
LLM_PROVIDER=vertexai  python3 test_provider.py "What is 2+2?"
```

### AWS Bedrock

Verified on `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `us-east-1`.

```
$ LLM_PROVIDER=bedrock python3 test_provider.py "What is 2+2?"
[bedrock] 2 + 2 = 4
```

The agent's tool-calling path runs on the same model through `ChatBedrockConverse`:

```
> Entering new AgentExecutor chain...
Invoking: `crm_lookup` with `{'query': 'sarah@example.com'}`
No contacts found matching 'sarah@example.com'.
> Finished chain.

TOOLS CALLED: ['crm_lookup']
```

List the inference profiles the account can reach with:

```bash
aws bedrock list-inference-profiles --region us-east-1
```

### Google Vertex AI

Verified on `gemini-3.6-flash` at the `global` endpoint.

```
$ GCP_PROJECT_ID=<project> LLM_PROVIDER=vertexai python3 test_provider.py "What is 2+2?"
[vertexai] 2 + 2 = 4
```

Authentication is Application Default Credentials:

```bash
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com
```

### Azure Functions (`deploy/azure/`)

HTTP trigger that answers a question using a document from Azure Blob Storage as context, generated with Azure OpenAI Service. Python v2 programming model.

```bash
cd deploy/azure
cp local.settings.json.example local.settings.json
pip install -r requirements.txt
func start

curl -X POST http://localhost:7071/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our refund policy?"}'
```

```bash
func azure functionapp publish <function-app-name>
```

### Kubernetes (`deploy/k8s/`)

Deployment and ClusterIP Service for the image built from this repository's Dockerfile.

```bash
docker build -t agenthub:local .
k3d cluster create agenthub-cluster
k3d image import agenthub:local -c agenthub-cluster

kubectl create secret generic agenthub-secrets \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml

kubectl port-forward svc/agenthub 8080:80
curl http://localhost:8080/health
```

Verified on k3s v1.35.5+k3s1 (k3d on Colima).

```
$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
agenthub-76f5c4d9bd-4m7rj   1/1     Running   0          9s

$ curl http://localhost:8080/health
{"status":"ok","mode":"demo","anthropic_key_set":true,"supabase_connected":false}
```

`INCIDENT_LOG.md` records four failure modes reproduced against this
Deployment, with the `kubectl` output for each: OOMKilled, a missing
Secret, a readiness probe path mismatch, and an image tag that does not
exist.
