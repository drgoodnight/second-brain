/**
 * Pre_Route - Fast Calendar, Task & Command Detection
 * 
 * Workflow: SimpleX_SecondBrain_Router
 * Node: Pre route calendar
 * 
 * Purpose: Detects obvious requests without using AI classification.
 *          Improves response time for common operations.
 *          Routes tasks directly to tasks workflow.
 *          Routes calendar operations directly to calendar workflow.
 *          Passes special commands (fix, confirm, cancel) to AI classifier.
 * 
 * Input: $json.message or $json.query
 * Output: intent, calendarAction (if calendar), skipAI flag, routedBy indicator
 * 
 * Last updated: 2026-01-26
 */

const message = ($json.message || $json.query || '').toLowerCase();

// ============================================================================
// SPECIAL COMMANDS - Must check FIRST before any other detection
// These need AI classification for proper handling
// ============================================================================
const isFixCommand = /^fix[:\s]/i.test(message.trim());
const isConfirmCommand = /^(yes|yep|yeah|confirm|do it|go ahead|ok|okay)$/i.test(message.trim());
const isCancelCommand = /^(no|nope|cancel|nevermind|never mind|stop)$/i.test(message.trim());
const isNumericSelection = /^\d+$/.test(message.trim());

if (isFixCommand || isConfirmCommand || isCancelCommand || isNumericSelection) {
  return {
    json: {
      ...$json,
      skipAI: false
    }
  };
}

// ============================================================================
// TASK DETECTION - Route directly to tasks workflow
// Tasks take priority over calendar - if user says "task", they mean task
// ============================================================================
const isTaskRequest = /\b(task|todo|to-do|to do)\b/.test(message);
if (isTaskRequest) {
  return {
    json: {
      ...$json,
      intent: 'tasks',
      skipAI: true,
      routedBy: 'pre-route-tasks'
    }
  };
}

// ============================================================================
// DATE/TIME PATTERNS - Indicators that suggest calendar context
// ============================================================================
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

// ============================================================================
// CALENDAR ACTION WORDS
// ============================================================================
const calendarQueryWords = [
  'what\'s on', 'whats on', 'schedule', 'calendar', 
  'busy', 'free', 'do i have', 'am i', 
  'show my', 'list my', 'check my'
];

const calendarAddWords = [
  'add', 'create', 'schedule', 'book', 
  'set up', 'put in', 'new event', 'new meeting', 'new appointment'
];

const calendarDeleteWords = [
  'cancel', 'delete', 'remove', 'drop', 'clear', 'wipe'
];

// ============================================================================
// PATTERN DETECTION
// ============================================================================
const hasDateIndicator = datePatterns.some(pattern => pattern.test(message));
const hasQueryWord = calendarQueryWords.some(word => message.includes(word));
const hasAddWord = calendarAddWords.some(word => message.includes(word));
const hasDeleteWord = calendarDeleteWords.some(word => message.includes(word));

// Time and event patterns for implicit calendar adds
const hasTimePattern = /\b\d{1,2}(:\d{2})?\s*(am|pm)\b/.test(message) || /\bat\s+(noon|midnight)\b/.test(message);
const hasEventWord = /\b(meeting|appointment|call|lunch|dinner|breakfast|event|shift)\b/.test(message);

// ============================================================================
// CALENDAR ACTION CLASSIFICATION
// ============================================================================
let isCalendar = false;
let calendarAction = null;

// Query: calendar query words OR "what" + date indicator
if (hasQueryWord || (message.includes('what') && hasDateIndicator)) {
  isCalendar = true;
  calendarAction = 'query';
}

// Add: date/time indicator + add words
if (hasAddWord && hasDateIndicator) {
  isCalendar = true;
  calendarAction = 'add';
}

// Delete: delete words + date indicator
if (hasDeleteWord && hasDateIndicator) {
  isCalendar = true;
  calendarAction = 'delete';
}

// Implicit add: time + event word + date, without delete/query words
// e.g., "meeting at 3pm tomorrow", "lunch with Bob at noon"
if (hasTimePattern && hasEventWord && hasDateIndicator && !hasDeleteWord && !hasQueryWord) {
  isCalendar = true;
  calendarAction = 'add';
}

// ============================================================================
// RETURN RESULT
// ============================================================================
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

// Not a clear pattern - let AI classify
return {
  json: {
    ...$json,
    skipAI: false
  }
};
