# Intelligent Intake and Triage MCP Server

This project focuses on building and containerizing a **Model Context Protocol (MCP) server** for a **Healthcare Intelligent Intake and Triage system**, including integration with LLM providers like **Gemini**.

---

## 🚀 Getting Started: Building the MCP Server

### 1) Project Initialization
Create the main project and server directories:

```bash
mkdir healthcare-intake-mcp
cd healthcare-intake-mcp
mkdir mcp-server
cd mcp-server
```

---

### 2) Configuration Setup
Create the taxonomy, severity, and routing configuration files:

```bash
mkdir -p config/healthcare
touch config/healthcare/taxonomy.json
touch config/healthcare/severity.yaml
touch config/healthcare/routing.json
```

---

### 3) Server Files
Create the main Python server file and the requirements list:

```bash
touch healthcare_mcp_server.py
touch requirements.txt
```

Add these dependencies to `requirements.txt`:

```txt
fastmcp
pyyaml
python-dotenv
httpx
starlette
```

---

### 4) Installation & Execution
Install the required packages and run the server:

```bash
pip install -r requirements.txt
python healthcare_mcp_server.py
```

✅ Expected Log:
```
🚀 Starting Intelligent Intake and Triage MCP Server...
```

---

### 5) Health Check
- Status: `http://0.0.0.0:8000` → ✅ MCP is running  
- Health: `http://0.0.0.0:8000/health` → `OK`

---

## 🐳 Containerization with Docker

### 1) Multi-Industry Configuration Support
We use Docker to package the server and support multiple industries (**Healthcare, Finance, E-commerce**) via mounted external configurations.

- **Default Config:** `config/healthcare/` (Bundled inside the image as a fallback)
- **External Config:** `external-config/` (Mounted at runtime for multi-industry support)

---

### 2) Default Configuration Structures

#### A) `routing.json`
```json
{
  "default_destination": "General_Queue",
  "severity_override": {
    "min_score": 9,
    "destination": "ER_Triage",
    "priority": "HIGH"
  },
  "routes": [
    {
      "category": "emergency",
      "threshold": 9,
      "destination": "ER_Triage"
    },
    {
      "category": "billing",
      "threshold": 2,
      "destination": "Billing_Department"
    }
  ]
}
```

#### B) `severity.yaml`
```yaml
severity_rules:
  critical:
    score: 10
    keywords:
      - chest pain
      - unconscious
  low:
    score: 2
    keywords:
      - billing
      - refund
```

#### C) `taxonomy.json`
```json
{
  "taxonomy": [
    {
      "id": "emergency",
      "keywords": ["chest pain", "heavy bleeding"]
    },
    {
      "id": "billing",
      "keywords": ["insurance", "refund"]
    }
  ]
}
```

---

### 3) Build and Run Docker
Create a `Dockerfile` in the `mcp-server` folder, then build the image:

```bash
docker build -t intake-triage-server .
```

Run using External Healthcare Config:

```bash
docker run -p 8000:8000 \
  -v $(pwd)/external-config:/config \
  -e CONFIG_PATH=/config/healthcare \
  intake-triage-server
```

Switching Industries (e.g., Finance): Simply change the `CONFIG_PATH` environment variable:

```bash
-e CONFIG_PATH=/config/finance
```

---

## 🤖 LLM Provider Integration (Gemini)

### 1) Client Setup
Create the client directory and files:

```bash
mkdir mcp-client
cd mcp-client
touch intake_mcp_client.py
touch requirements.txt
```

Add these to `mcp-client/requirements.txt`:

```txt
fastmcp
google-genai
httpx
```

---

### 2) Execution

Install Client Requirements:

```bash
pip install -r requirements.txt
```

Set API Key:

```bash
export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
```

Run Client:

```bash
python intake_mcp_client.py
```

---

## 📁 Final Project Structure

```txt
healthcare-intake-mcp/
├── mcp-server/
│   ├── config/healthcare/
│   │   ├── taxonomy.json
│   │   ├── severity.yaml
│   │   └── routing.json
│   ├── external-config/
│   ├── Dockerfile
│   ├── healthcare_mcp_server.py
│   └── requirements.txt
└── mcp-client/
    ├── intake_mcp_client.py
    └── requirements.txt
```
