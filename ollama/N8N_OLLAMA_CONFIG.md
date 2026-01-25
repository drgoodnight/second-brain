# n8n Configuration for Local Ollama

This guide covers updating your n8n workflows to use local Ollama instead of cloud AI providers.

## Overview

Your Second Brain uses AI for three main tasks:

1. **Intent Classification** - Routing messages to the right workflow
2. **ICS Generation** - Creating calendar events from natural language
3. **Notes Classification** - Categorizing captures into People/Projects/Ideas/Admin
4. **Chat Responses** - General conversation

All of these will be updated to use your local Gemma 3 12B model.

---

## Step 1: Create Ollama Credential in n8n

1. Open n8n: `http://localhost:5678`
2. Go to **Settings** → **Credentials**
3. Click **Add Credential**
4. Search for "Ollama"
5. Configure:
   - **Name**: `Ollama Local`
   - **Base URL**: `http://ollama:11434`
6. Click **Save**

---

## Step 2: Update Intent Classification

### Current Setup (OpenAI)
Your `Classify_Intent_AI` node likely uses OpenAI's API.

### New Setup (Ollama)

**Option A: Replace with HTTP Request Node**

Create a new **HTTP Request** node:

```
Name: Classify_Intent_Ollama
Method: POST
URL: http://ollama:11434/api/generate
Body (JSON):
{
  "model": "gemma3:12b",
  "prompt": "{{ $json.systemPrompt }}\n\nUser message: {{ $json.message }}\n\nRespond with ONLY valid JSON.",
  "stream": false,
  "format": "json",
  "options": {
    "temperature": 0.1,
    "num_predict": 200
  }
}
```

**Option B: Use n8n's Ollama Node (if available)**

n8n has built-in Ollama support:

1. Add **Ollama** node
2. Select credential: `Ollama Local`
3. Model: `gemma3:12b`
4. Operation: `Generate`
5. Prompt: Your classification prompt

### Parsing the Response

Add a **Code** node after the Ollama call:

```javascript
// Parse Ollama response
const response = $json.response || $json.message?.content || '';

// Extract JSON from response
let parsed;
try {
  // Try direct parse first
  parsed = JSON.parse(response);
} catch (e) {
  // Try to extract JSON from markdown code blocks
  const jsonMatch = response.match(/```json?\s*([\s\S]*?)\s*```/);
  if (jsonMatch) {
    parsed = JSON.parse(jsonMatch[1]);
  } else {
    // Try to find JSON object in response
    const objectMatch = response.match(/\{[\s\S]*\}/);
    if (objectMatch) {
      parsed = JSON.parse(objectMatch[0]);
    } else {
      throw new Error('Could not parse JSON from response');
    }
  }
}

return {
  json: {
    intent: parsed.intent,
    target: parsed.target,
    content: parsed.content,
    query: parsed.query,
    category: parsed.category,
    name: parsed.name,
    raw_response: response
  }
};
```

---

## Step 3: Update ICS Generation

### Current Setup
Your `AI_Agent_ICS_generator` uses OpenAI for calendar event creation.

### New Setup

Replace with HTTP Request to Ollama:

```
Name: Generate_ICS_Ollama
Method: POST
URL: http://ollama:11434/api/generate
Body (JSON):
{
  "model": "gemma3:12b",
  "prompt": "{{ $json.icsPrompt }}\n\n{{ $json.request }}\n\n[Current local time: {{ $json.currentTime }}, Date: {{ $json.today }}]",
  "stream": false,
  "options": {
    "temperature": 0.2,
    "num_predict": 1000,
    "stop": ["END:VCALENDAR\n\n", "```"]
  }
}
```

### Post-Processing ICS Output

Add a Code node to clean the response:

```javascript
// Extract ICS content from Ollama response
let icsContent = $json.response || '';

// Remove any markdown code blocks
icsContent = icsContent.replace(/```ics?\s*/gi, '').replace(/```\s*$/gi, '');

// Ensure it starts with BEGIN:VCALENDAR
if (!icsContent.includes('BEGIN:VCALENDAR')) {
  throw new Error('Invalid ICS output from AI');
}

// Ensure it ends with END:VCALENDAR
if (!icsContent.includes('END:VCALENDAR')) {
  icsContent += '\nEND:VCALENDAR';
}

// Clean up any extra whitespace
icsContent = icsContent.trim();

return {
  json: {
    icsContent: icsContent,
    raw: $json.response
  }
};
```

---

## Step 4: Update Notes Classification

The notes agent classifies captures into People/Projects/Ideas/Admin.

### Prompt Template for Ollama

Store this in a Set node or as a variable:

```javascript
const classificationPrompt = `You are a classification agent for a personal knowledge base. Analyze the input and return JSON.

Databases:
- "people": Information about specific individuals (names, relationships, facts about people)
- "projects": Multi-step goals, ongoing work, things with next actions
- "ideas": Insights, concepts, shower thoughts, "what if" scenarios
- "admin": Tasks, todos, reminders, administrative items with deadlines
- "needs_review": Unclear or low confidence classification

Extract:
- database: Which database this belongs to
- name: A title for this entry (person's name for people, project name, idea title, task description)
- confidence: 0.0 to 1.0 how sure you are
- For people: context (relationship/role), follow_ups (things to remember)
- For projects: status (Active/Waiting/Blocked/Someday), next_action
- For ideas: one_liner (the core insight in one sentence)
- For admin: due_date (YYYY-MM-DD if mentioned), notes
- tags: relevant tags as array

Input: "${input}"

Respond with ONLY valid JSON, no explanation.`;
```

### HTTP Request Configuration

```
Method: POST
URL: http://ollama:11434/api/generate
Body:
{
  "model": "gemma3:12b",
  "prompt": "{{ $json.classificationPrompt }}",
  "stream": false,
  "format": "json",
  "options": {
    "temperature": 0.1,
    "num_predict": 300
  }
}
```

---

## Step 5: Update Chat Responses

For general chat, use the chat endpoint:

```
Method: POST
URL: http://ollama:11434/api/chat
Body:
{
  "model": "gemma3:12b",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful personal assistant integrated into a Second Brain system. Be concise and friendly. You help manage calendars, notes, and tasks."
    },
    {
      "role": "user", 
      "content": "{{ $json.message }}"
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 500
  }
}
```

---

## Complete Workflow Example

Here's a simplified flow for intent classification:

```
┌─────────────────┐
│ Webhook_SimpleX │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Prepare_Input  │  (Add timestamp, clean message)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Pre_Route_Cal   │  (Quick pattern matching)
└────────┬────────┘
         │
    ┌────┴────┐
    │ skip_AI │
    └────┬────┘
         │ (if not pre-routed)
         ▼
┌─────────────────┐
│ Build_AI_Prompt │  (Set node with classification prompt)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Ollama_Classify │  (HTTP Request to Ollama)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Parse_Intent   │  (Code node to extract JSON)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Route_Intent   │  (Switch node based on intent)
└─────────────────┘
```

---

## Environment Variables

Add these to your n8n container environment:

```yaml
environment:
  - OLLAMA_HOST=ollama
  - OLLAMA_PORT=11434
  - OLLAMA_MODEL=gemma3:12b
```

Then reference in workflows: `{{ $env.OLLAMA_MODEL }}`

---

## Testing Your Setup

### 1. Test Ollama Connection from n8n

Create a simple test workflow:

1. **Manual Trigger** node
2. **HTTP Request** node:
   - URL: `http://ollama:11434/api/generate`
   - Method: POST
   - Body: `{"model": "gemma3:12b", "prompt": "Say hello", "stream": false}`
3. Execute and verify response

### 2. Test Intent Classification

Send test messages through SimpleX:
- "what's on my calendar tomorrow" → Should classify as `calendar`
- "add to John he likes pizza" → Should classify as `notes`
- "yes" → Should classify as `confirm`

### 3. Test ICS Generation

- "meeting at 3pm tomorrow" → Should generate valid ICS

### 4. Check Logs

```bash
# n8n logs
docker compose logs -f n8n

# Ollama logs (shows model loading and inference)
docker compose logs -f ollama
```

---

## Performance Tuning

### Reduce Latency

```json
{
  "options": {
    "num_ctx": 2048,      // Smaller context = faster
    "num_predict": 200,   // Limit output length
    "num_thread": 8       // Match your CPU cores
  }
}
```

### Improve Quality

```json
{
  "options": {
    "temperature": 0.1,   // Lower = more deterministic
    "top_p": 0.9,
    "repeat_penalty": 1.1
  }
}
```

### For Classification Tasks

```json
{
  "format": "json",       // Force JSON output
  "options": {
    "temperature": 0.0,   // Deterministic
    "num_predict": 200    // Classifications are short
  }
}
```

---

## Fallback Strategy

If you want cloud AI as a fallback:

```javascript
// In a Code node after Ollama call
const ollamaResponse = $json.response;
const ollamaError = $json.error;

if (ollamaError || !ollamaResponse) {
  // Flag for fallback to OpenAI
  return {
    json: {
      useOpenAI: true,
      originalMessage: $('Prepare_Input').first().json.message
    }
  };
}

return {
  json: {
    useOpenAI: false,
    response: ollamaResponse
  }
};
```

Then use an IF node to route to OpenAI when `useOpenAI` is true.

---

## Migrating Existing Workflows

### Quick Migration Checklist

- [ ] Create Ollama credential in n8n
- [ ] Update `Classify_Intent_AI` → Ollama HTTP Request
- [ ] Update `AI_Agent_ICS_generator` → Ollama HTTP Request  
- [ ] Update `Execute_Notes_Agent` → Ollama HTTP Request
- [ ] Update `Chat_Response` → Ollama chat endpoint
- [ ] Add JSON parsing Code nodes after each Ollama call
- [ ] Test each workflow path
- [ ] Monitor for errors and tune prompts

### Prompt Adjustments for Gemma

Gemma 3 responds well to:
- Clear, structured instructions
- Explicit output format requirements
- Examples (few-shot prompting)
- "Respond with ONLY..." constraints

You may need to adjust your existing prompts slightly. The prompts in your project are already well-structured and should work with minimal changes.
