# Gemma 3 Optimized Prompts for Second Brain

These prompts are specifically tuned for Gemma 3 12B's instruction-following capabilities.

## Key Differences from OpenAI Prompts

1. **More explicit formatting instructions** - Gemma benefits from very clear output format specs
2. **Structured examples** - Few-shot examples improve consistency
3. **Explicit JSON constraints** - "ONLY valid JSON" and format: "json" parameter
4. **Shorter system prompts** - Gemma handles concise instructions well

---

## Intent Classification Prompt

```
You are a router for a personal assistant. Classify the user's message into exactly one category.

CATEGORIES:
- calendar: Any mention of dates, times, schedules, meetings, appointments, events, "what's on", adding/canceling events
- notes: Capturing information about people, ideas, projects ("add to", "note that", "remember", mentions a person's name with facts)
- search: Retrieving stored information ("what do I know about", "find", "list people/projects/ideas")
- delete: Removing Obsidian entries (NOT calendar events) - "delete the entry", "remove the note"
- confirm: Affirmative responses: yes, yeah, do it, confirm, go ahead, ok, sure
- cancel: Negative responses: no, nevermind, stop, cancel (when NOT about calendar events)
- fix: Reclassifying entries: "fix: people", "fix: project", "fix: ideas", "fix: admin"
- numeric_selection: Single digit responses: 1, 2, 3, etc. (selecting from a list)
- chat: Everything else - greetings, questions, conversation
- help: Questions about capabilities: "what can you do", "help"

IMPORTANT RULES:
- If message contains dates/times AND delete/cancel words → calendar (not delete/cancel)
- "cancel my meeting" → calendar
- "delete the entry about coffee" → delete
- Single digit alone (1, 2, 3) → numeric_selection

OUTPUT FORMAT - Return ONLY this JSON structure:
{"intent": "<category>", "target": "<person/topic if notes>", "content": "<relevant content>", "query": "<search/delete query>", "category": "<fix target>"}

Omit fields that don't apply. No explanation, no markdown.

User message: {message}
```

### n8n HTTP Request Body

```json
{
  "model": "gemma3:12b",
  "prompt": "<prompt above with {message} replaced>",
  "stream": false,
  "format": "json",
  "options": {
    "temperature": 0.0,
    "num_predict": 150,
    "stop": ["\n\n", "```"]
  }
}
```

---

## ICS Generation Prompt

```
Generate RFC 5545 iCalendar (ICS) format. Output ONLY raw ICS text starting with BEGIN:VCALENDAR.

TIMEZONE: Europe/London (use TZID=Europe/London for DTSTART/DTEND)
CURRENT TIME: {current_time}
CURRENT DATE: {today}

RULES:
1. Always include: UID, DTSTAMP, DTSTART, DTEND, SUMMARY, DESCRIPTION
2. DTSTART/DTEND format: DTSTART;TZID=Europe/London:YYYYMMDDTHHMMSS
3. DTSTAMP format: DTSTAMP:YYYYMMDDTHHMMSSZ (UTC)
4. Default duration: 1 hour if not specified
5. Default time: 09:00 if no time given
6. UID format: YYYYMMDD-HHMM-HHMM-summary-slug@secondbrain

TIME INTERPRETATION:
- "3pm" → 15:00
- "tomorrow" → {tomorrow_date}
- "next Monday" → calculate from {today}
- No time specified → 09:00-10:00

REQUEST: {request}

Output ONLY the ICS content:
```

### n8n HTTP Request Body

```json
{
  "model": "gemma3:12b",
  "prompt": "<prompt above>",
  "stream": false,
  "options": {
    "temperature": 0.2,
    "num_predict": 800,
    "stop": ["END:VCALENDAR\n\n", "\n\n\n"]
  }
}
```

---

## Notes Classification Prompt

```
Classify this capture for a personal knowledge base. Return ONLY JSON.

DATABASES:
- people: Information about specific individuals (facts, relationships, preferences)
- projects: Multi-step goals, ongoing work with next actions
- ideas: Insights, concepts, "what if" thoughts
- admin: Tasks, todos, deadlines, reminders
- needs_review: Unclear classification (use if confidence < 0.6)

INPUT: "{input}"

OUTPUT FORMAT:
{
  "database": "<people|projects|ideas|admin|needs_review>",
  "name": "<title for this entry>",
  "confidence": <0.0-1.0>,
  "context": "<for people: relationship/how you know them>",
  "follow_ups": "<for people: things to remember>",
  "status": "<for projects: Active|Waiting|Blocked|Someday>",
  "next_action": "<for projects: literal next step>",
  "one_liner": "<for ideas: core insight in one sentence>",
  "due_date": "<for admin: YYYY-MM-DD if mentioned>",
  "notes": "<additional context>",
  "tags": ["<relevant>", "<tags>"]
}

Include only relevant fields. No explanation.
```

### n8n HTTP Request Body

```json
{
  "model": "gemma3:12b",
  "prompt": "<prompt above>",
  "stream": false,
  "format": "json",
  "options": {
    "temperature": 0.1,
    "num_predict": 300
  }
}
```

---

## Chat Response Prompt

```
You are a helpful assistant integrated into a personal Second Brain system. You help manage calendars, notes (People, Projects, Ideas, Tasks), and provide information.

Be concise, friendly, and practical. If the user seems to want to do something (add event, save note), guide them on how.

User: {message}
```

### n8n HTTP Request Body (Chat endpoint)

```json
{
  "model": "gemma3:12b",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant integrated into a personal Second Brain system. You help manage calendars, notes (People, Projects, Ideas, Tasks), and provide information. Be concise and friendly."
    },
    {
      "role": "user",
      "content": "{message}"
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 400
  }
}
```

---

## Response Parsing Code Node

Use this after any Ollama call to safely extract JSON:

```javascript
// Parse Ollama response safely
const rawResponse = $json.response || '';

function extractJSON(text) {
  // Try direct parse
  try {
    return JSON.parse(text.trim());
  } catch (e) {}
  
  // Try extracting from code blocks
  const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
  if (codeBlockMatch) {
    try {
      return JSON.parse(codeBlockMatch[1].trim());
    } catch (e) {}
  }
  
  // Try finding JSON object
  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      return JSON.parse(jsonMatch[0]);
    } catch (e) {}
  }
  
  // Return error object
  return { error: 'Could not parse JSON', raw: text };
}

const parsed = extractJSON(rawResponse);

// For intent classification
if (parsed.intent) {
  return {
    json: {
      intent: parsed.intent,
      target: parsed.target || null,
      content: parsed.content || null,
      query: parsed.query || null,
      category: parsed.category || null,
      name: parsed.name || null,
      confidence: parsed.confidence || 1.0,
      _raw: rawResponse
    }
  };
}

// For notes classification
if (parsed.database) {
  return {
    json: {
      database: parsed.database,
      name: parsed.name,
      confidence: parsed.confidence || 0.8,
      context: parsed.context,
      follow_ups: parsed.follow_ups,
      status: parsed.status,
      next_action: parsed.next_action,
      one_liner: parsed.one_liner,
      due_date: parsed.due_date,
      notes: parsed.notes,
      tags: parsed.tags || [],
      _raw: rawResponse
    }
  };
}

// Generic return
return { json: { ...parsed, _raw: rawResponse } };
```

---

## ICS Cleaning Code Node

Use after ICS generation:

```javascript
// Clean ICS output from Ollama
let ics = $json.response || '';

// Remove markdown code blocks
ics = ics.replace(/```(?:ics|ical|vcalendar)?\s*/gi, '');
ics = ics.replace(/```\s*$/gi, '');

// Find the ICS content
const startIdx = ics.indexOf('BEGIN:VCALENDAR');
const endIdx = ics.lastIndexOf('END:VCALENDAR');

if (startIdx === -1) {
  throw new Error('No valid ICS content found in AI response');
}

if (endIdx === -1) {
  ics = ics.substring(startIdx) + '\nEND:VCALENDAR';
} else {
  ics = ics.substring(startIdx, endIdx + 'END:VCALENDAR'.length);
}

// Clean up whitespace
ics = ics.trim();

// Validate basic structure
if (!ics.includes('BEGIN:VEVENT')) {
  throw new Error('ICS missing VEVENT - AI may have failed to create event');
}

return {
  json: {
    icsContent: ics,
    _raw: $json.response
  }
};
```

---

## Testing Prompts

Quick curl commands to test each prompt:

### Test Intent Classification
```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "gemma3:12b",
  "prompt": "You are a router... [full prompt]\n\nUser message: what is on my calendar tomorrow",
  "stream": false,
  "format": "json",
  "options": {"temperature": 0}
}' | jq .response
```

### Test ICS Generation
```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "gemma3:12b", 
  "prompt": "Generate RFC 5545... [full prompt]\n\nREQUEST: meeting at 3pm tomorrow",
  "stream": false,
  "options": {"temperature": 0.2}
}' | jq -r .response
```

### Test Notes Classification
```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "gemma3:12b",
  "prompt": "Classify this capture... [full prompt]\n\nINPUT: John mentioned he loves hiking",
  "stream": false,
  "format": "json"
}' | jq .response
```
