# n8n Scripts

JavaScript code nodes and prompts for the Second Brain n8n workflows.

## Directory Structure

```
n8n/scripts/
├── calendar/
│   ├── classify_request.js      # Determines add/query/delete action, parses dates
│   ├── execute_bulk_delete.js   # Deletes calendar events via CalDAV
│   ├── find_matching_events.js  # Searches calendar for delete operations
│   ├── query_calendar.js        # CalDAV REPORT query for event retrieval
│   └── split_ics_events.js      # Parses AI-generated ICS into individual events
├── intent/
│   ├── parse_intent.js          # Extracts intent from AI classification response
│   └── pre_route_calendar.js    # Fast calendar detection without AI
├── prompts/
│   ├── classify_intent_prompt.txt   # System prompt for intent classification
│   └── ai_ics_generator_prompt.txt  # System prompt for ICS generation
└── README.md
```

## Usage

These scripts are used in n8n Code nodes. To update a script:

1. Edit the file in this repository
2. Copy the contents into the corresponding n8n Code node
3. Test the workflow

## Environment Variables

The following environment variables must be set in your `.env` file and passed to the n8n container:

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXTCLOUD_URL` | Full CalDAV calendar URL | `http://nextcloud/remote.php/dav/calendars/user/calendar/` |
| `NEXTCLOUD_USERNAME` | Nextcloud username | `cypherdoc` |
| `NEXTCLOUD_PASSWORD` | Nextcloud app password | `xxxxx-xxxxx-xxxxx-xxxxx-xxxxx` |

## Workflows

### SimpleX_SecondBrain_Router
Main workflow that receives messages from SimpleX and routes to appropriate handlers.

**Scripts used:**
- `intent/pre_route_calendar.js` - Pre-route obvious calendar requests
- `intent/parse_intent.js` - Parse AI classification response
- `prompts/classify_intent_prompt.txt` - System prompt for Classify_Intent_AI node

### Calendar_input/output
Sub-workflow for all calendar operations (add, query, delete).

**Scripts used:**
- `calendar/classify_request.js` - Classify calendar action and parse dates
- `calendar/query_calendar.js` - Query CalDAV for events
- `calendar/find_matching_events.js` - Find events for delete operations
- `calendar/execute_bulk_delete.js` - Delete events via CalDAV

### calendar_agent
Sub-workflow for creating new calendar events via AI.

**Scripts used:**
- `prompts/ai_ics_generator_prompt.txt` - System prompt for ICS generation
- `calendar/split_ics_events.js` - Split multi-event ICS into individual events

## Last Updated

2026-01-25
