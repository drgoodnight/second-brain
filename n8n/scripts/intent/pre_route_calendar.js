/**
 * Pre_Route_Calendar - Fast Calendar Detection
 * 
 * Workflow: SimpleX_SecondBrain_Router
 * Node: Pre_route_calendar
 * 
 * Purpose: Detects obvious calendar requests without using AI classification.
 *          Improves response time for common calendar operations.
 * 
 * Input: $json.message or $json.query
 * Output: intent (if calendar), skipAI flag, routedBy indicator
 * 
 * Last updated: 2026-01-25
 */

const message = ($json.message || $json.query || '').toLowerCase();

// Date/time indicators that suggest calendar context
const datePatterns = [
  /\b(today|tonight|tomorrow|yesterday)\b/,
  /\b(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b/i,
  /\b(next|this|last)\s+(week|month|mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b/i,
  /\b\d{1,2}(st|nd|rd|th)?\s*(of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i,
  /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(st|nd|rd|th)?\b/i,
  /\b(the\s+)?\d{1,2}(st|nd|rd|th)\b/,  // "the 22nd", "on the 5th"
  /\b\d{1,2}(:\d{2})?\s*(am|pm)\b/,      // "3pm", "15:00"
  /\bin\s+\d+\s+days?\b/,                 // "in 3 days"
  /\b\d+\s+days?\s+(ago|from now)\b/,     // "2 days ago"
  /\bday\s+(after|before)\s+(tomorrow|yesterday)\b/,
  /\b(for\s+)?(the\s+)?week\b/           // "the week", "this week"
];

// Calendar action words
const calendarQueryWords = ['what\'s on', 'whats on', 'schedule', 'calendar', 'busy', 'free', 'do i have', 'am i', 'show my', 'list my', 'check my'];
const calendarAddWords = ['add', 'create', 'schedule', 'book', 'set up', 'put in', 'new event', 'new meeting', 'new appointment'];
const calendarDeleteWords = ['cancel', 'delete', 'remove', 'drop', 'clear', 'wipe'];

// Check for date/time indicators
const hasDateIndicator = datePatterns.some(pattern => pattern.test(message));

// Check for calendar-specific words
const hasQueryWord = calendarQueryWords.some(word => message.includes(word));
const hasAddWord = calendarAddWords.some(word => message.includes(word));
const hasDeleteWord = calendarDeleteWords.some(word => message.includes(word));

// Determine if this is clearly a calendar request
let isCalendar = false;
let calendarAction = null;

// Query: calendar query words OR "what" + date indicator
if (hasQueryWord || (message.includes('what') && hasDateIndicator)) {
  isCalendar = true;
  calendarAction = 'query';
}

// Add: date/time indicator + add words, OR time pattern (likely scheduling)
if (hasAddWord && hasDateIndicator) {
  isCalendar = true;
  calendarAction = 'add';
}

// Delete: delete words + date indicator (this is the key fix!)
if (hasDeleteWord && hasDateIndicator) {
  isCalendar = true;
  calendarAction = 'delete';
}

// Also catch time-based adds without explicit "add" word
// e.g., "meeting at 3pm tomorrow", "lunch with Bob at noon"
const hasTimePattern = /\b\d{1,2}(:\d{2})?\s*(am|pm)\b/.test(message) || /\bat\s+(noon|midnight)\b/.test(message);
const hasEventWord = /\b(meeting|appointment|call|lunch|dinner|breakfast|event|reminder|shift)\b/.test(message);
if (hasTimePattern && hasEventWord && hasDateIndicator && !hasDeleteWord && !hasQueryWord) {
  isCalendar = true;
  calendarAction = 'add';
}

// Return result
if (isCalendar) {
  return {
    json: {
      ...$json,
      intent: 'calendar',
      calendarAction: calendarAction,
      skipAI: true,
      routedBy: 'pre-route-calendar'
    }
  };
}

// Not a clear calendar pattern - let AI classify
return {
  json: {
    ...$json,
    skipAI: false
  }
};
