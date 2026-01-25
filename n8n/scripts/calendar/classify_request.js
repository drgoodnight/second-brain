/**
 * Classify_Request - Calendar Action Classification
 * 
 * Workflow: Calendar_input/output
 * Node: Classify_Request
 * 
 * Purpose: Determines if a calendar request is add/query/delete and extracts
 *          date information from natural language input.
 * 
 * Input: $json.request, $json.today
 * Output: action, startDate, endDate, searchTerm, searchTime, deleteAll
 * 
 * Last updated: 2026-01-25
 */

// Strip metadata from bridge FIRST, before any processing
const cleanedRequest = $json.request.toLowerCase().replace(/\[current local time:.*?\]/gi, '');
const request = cleanedRequest;

let action = 'add'; // default

// Check for DELETE patterns first (before query, since "cancel" is more specific)
const deletePatterns = [
  'cancel', 'delete', 'remove', 'drop', 'clear', 'wipe'
];

for (const pattern of deletePatterns) {
  if (request.includes(pattern)) {
    action = 'delete';
    break;
  }
}

// Check if deleting ALL events (flexible patterns)
let deleteAll = false;
if (action === 'delete') {
  const allPatterns = [
    /\b(all|every|each)\s*(my\s*)?(events?|appointments?|meetings?|calendar)?\b/i,
    /\b(everything)\b/i,
    /\b(clear|wipe)\s*(my\s*)?(calendar|schedule|day)?\b/i,
    /\b(the\s*)?(whole|entire)\s*(day|calendar|schedule)?\b/i,
    /\b(delete|cancel|remove|drop)\s+all\b/i
  ];
  
  for (const pattern of allPatterns) {
    if (pattern.test(request)) {
      deleteAll = true;
      break;
    }
  }
}

// Check for QUERY patterns (only if not already delete)
if (action !== 'delete') {
  const queryPatterns = [
    'what', 'show', 'list', 'schedule', 'calendar', 'busy', 'free', 
    'do i have', 'am i', 'check', 'summary', 'tell me',
    'what\'s on', 'whats on'
  ];
  for (const pattern of queryPatterns) {
    if (request.includes(pattern)) {
      action = 'query';
      break;
    }
  }
}

// Parse date from request
let startDate = $json.today;
let endDate = $json.today;

const months = {
  'jan': 0, 'january': 0,
  'feb': 1, 'february': 1,
  'mar': 2, 'march': 2,
  'apr': 3, 'april': 3,
  'may': 4,
  'jun': 5, 'june': 5,
  'jul': 6, 'july': 6,
  'aug': 7, 'august': 7,
  'sep': 8, 'september': 8,
  'oct': 9, 'october': 9,
  'nov': 10, 'november': 10,
  'dec': 11, 'december': 11
};

// Check multi-word phrases BEFORE single words
// Order matters! "day after tomorrow" must come before "tomorrow"
if (request.includes('day before yesterday')) {
  const dayBeforeYesterday = new Date($json.today);
  dayBeforeYesterday.setDate(dayBeforeYesterday.getDate() - 2);
  startDate = dayBeforeYesterday.toISOString().slice(0, 10);
  endDate = startDate;
} else if (request.includes('day after tomorrow')) {
  const dayAfter = new Date($json.today);
  dayAfter.setDate(dayAfter.getDate() + 2);
  startDate = dayAfter.toISOString().slice(0, 10);
  endDate = startDate;
} else if (request.includes('tomorrow')) {
  const tomorrow = new Date($json.today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  startDate = tomorrow.toISOString().slice(0, 10);
  endDate = startDate;
} else if (request.includes('yesterday')) {
  const yesterday = new Date($json.today);
  yesterday.setDate(yesterday.getDate() - 1);
  startDate = yesterday.toISOString().slice(0, 10);
  endDate = startDate;
} else if (/\b(\d+)\s*days?\s*ago\b/i.test(request)) {
  const daysAgoMatch = request.match(/\b(\d+)\s*days?\s*ago\b/i);
  const daysAgo = parseInt(daysAgoMatch[1]);
  const pastDate = new Date($json.today);
  pastDate.setDate(pastDate.getDate() - daysAgo);
  startDate = pastDate.toISOString().slice(0, 10);
  endDate = startDate;
} else if (/\bin\s*(\d+)\s*days?\b/i.test(request)) {
  const inDaysMatch = request.match(/\bin\s*(\d+)\s*days?\b/i);
  const inDays = parseInt(inDaysMatch[1]);
  const futureDate = new Date($json.today);
  futureDate.setDate(futureDate.getDate() + inDays);
  startDate = futureDate.toISOString().slice(0, 10);
  endDate = startDate;
// Match "the week", "this week", or just "week" for weekly queries
} else if (/\b(this\s+week|the\s+week|for\s+the\s+week)\b/i.test(request)) {
  const today = new Date($json.today);
  const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, etc.
  
  // Start from Monday of current week
  const startOfWeek = new Date(today);
  const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Adjust for Monday start
  startOfWeek.setDate(today.getDate() - daysFromMonday);
  
  // End on Sunday
  const endOfWeek = new Date(startOfWeek);
  endOfWeek.setDate(startOfWeek.getDate() + 6);
  
  startDate = startOfWeek.toISOString().slice(0, 10);
  endDate = endOfWeek.toISOString().slice(0, 10);
} else if (request.includes('next week')) {
  const today = new Date($json.today);
  const dayOfWeek = today.getDay();
  const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  
  // Start from next Monday
  const startOfNextWeek = new Date(today);
  startOfNextWeek.setDate(today.getDate() - daysFromMonday + 7);
  
  const endOfNextWeek = new Date(startOfNextWeek);
  endOfNextWeek.setDate(startOfNextWeek.getDate() + 6);
  
  startDate = startOfNextWeek.toISOString().slice(0, 10);
  endDate = endOfNextWeek.toISOString().slice(0, 10);
} else if (/\blast\s+week\b/i.test(request)) {
  const today = new Date($json.today);
  const dayOfWeek = today.getDay();
  const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  
  // Start from last Monday (7 days before this Monday)
  const startOfLastWeek = new Date(today);
  startOfLastWeek.setDate(today.getDate() - daysFromMonday - 7);
  
  // End on last Sunday
  const endOfLastWeek = new Date(startOfLastWeek);
  endOfLastWeek.setDate(startOfLastWeek.getDate() + 6);
  
  startDate = startOfLastWeek.toISOString().slice(0, 10);
  endDate = endOfLastWeek.toISOString().slice(0, 10);

// Day names with modifiers: "next Monday", "this Fri", "last Tues"
} else if (/\b(next|this|last)\s+(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b/i.test(request)) {
  const dayNameToNum = {
    'sun': 0, 'sunday': 0,
    'mon': 1, 'monday': 1,
    'tue': 2, 'tues': 2, 'tuesday': 2,
    'wed': 3, 'wednesday': 3,
    'thu': 4, 'thur': 4, 'thurs': 4, 'thursday': 4,
    'fri': 5, 'friday': 5,
    'sat': 6, 'saturday': 6
  };
  
  const match = request.match(/\b(next|this|last)\s+(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b/i);
  const modifier = match[1].toLowerCase();
  const targetDayName = match[2].toLowerCase();
  const targetDayNum = dayNameToNum[targetDayName];
  
  const today = new Date($json.today);
  const currentDayNum = today.getDay();
  
  let daysToAdd = targetDayNum - currentDayNum;
  
  if (modifier === 'next') {
    // Next = the coming occurrence in the next 7 days, or +7 if same day
    if (daysToAdd <= 0) daysToAdd += 7;
  } else if (modifier === 'last') {
    // Last = the previous occurrence
    if (daysToAdd >= 0) daysToAdd -= 7;
  } else if (modifier === 'this') {
    // This = this week's occurrence (could be past or future within the week)
  }
  
  const targetDate = new Date(today);
  targetDate.setDate(today.getDate() + daysToAdd);
  startDate = targetDate.toISOString().slice(0, 10);
  endDate = startDate;

// Bare day names: "Monday", "on Fri", "Tues schedule"
} else if (/\b(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b/i.test(request)) {
  const dayNameToNum = {
    'sun': 0, 'sunday': 0,
    'mon': 1, 'monday': 1,
    'tue': 2, 'tues': 2, 'tuesday': 2,
    'wed': 3, 'wednesday': 3,
    'thu': 4, 'thur': 4, 'thurs': 4, 'thursday': 4,
    'fri': 5, 'friday': 5,
    'sat': 6, 'saturday': 6
  };
  
  const match = request.match(/\b(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b/i);
  const targetDayName = match[1].toLowerCase();
  const targetDayNum = dayNameToNum[targetDayName];
  
  const today = new Date($json.today);
  const currentDayNum = today.getDay();
  
  // Default behavior: find the NEXT occurrence (including today if it matches)
  let daysToAdd = targetDayNum - currentDayNum;
  if (daysToAdd < 0) daysToAdd += 7; // If day passed this week, go to next week
  
  const targetDate = new Date(today);
  targetDate.setDate(today.getDate() + daysToAdd);
  startDate = targetDate.toISOString().slice(0, 10);
  endDate = startDate;

// Month patterns: "this month", "the month", "next month"
} else if (/\b(this\s+month|the\s+month|for\s+the\s+month)\b/i.test(request)) {
  const today = new Date($json.today);
  
  // Start from 1st of current month
  const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  
  // End on last day of current month
  const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  
  startDate = startOfMonth.toISOString().slice(0, 10);
  endDate = endOfMonth.toISOString().slice(0, 10);
} else if (/\bnext\s+month\b/i.test(request)) {
  const today = new Date($json.today);
  
  // Start from 1st of next month
  const startOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  
  // End on last day of next month
  const endOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 2, 0);
  
  startDate = startOfNextMonth.toISOString().slice(0, 10);
  endDate = endOfNextMonth.toISOString().slice(0, 10);
} else if (/\blast\s+month\b/i.test(request)) {
  const today = new Date($json.today);
  
  // Start from 1st of last month
  const startOfLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  
  // End on last day of last month
  const endOfLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
  
  startDate = startOfLastMonth.toISOString().slice(0, 10);
  endDate = endOfLastMonth.toISOString().slice(0, 10);
} else {
  // Try to parse specific dates
  let dateParsed = false;
  
  // Pattern 1: Date WITH month - "9th jan", "jan 9", "january 15", "15th january"
  const dateWithMonthPattern = /(\d{1,2})(?:st|nd|rd|th)?\s*(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)|(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s*(\d{1,2})(?:st|nd|rd|th)?/i;
  
  const matchWithMonth = request.match(dateWithMonthPattern);
  if (matchWithMonth) {
    let day, monthStr;
    if (matchWithMonth[1] && matchWithMonth[2]) {
      day = parseInt(matchWithMonth[1]);
      monthStr = matchWithMonth[2].toLowerCase();
    } else if (matchWithMonth[3] && matchWithMonth[4]) {
      monthStr = matchWithMonth[3].toLowerCase();
      day = parseInt(matchWithMonth[4]);
    }
    
    if (day && monthStr && months.hasOwnProperty(monthStr)) {
      const year = new Date($json.today).getFullYear();
      const parsedDate = new Date(year, months[monthStr], day);
      startDate = parsedDate.toISOString().slice(0, 10);
      endDate = startDate;
      dateParsed = true;
    }
  }
  
  // Pattern 2: Bare ordinal WITHOUT month - "the 22nd", "on the 5th", "22nd"
  // Assumes current month (or next month if date has passed)
  if (!dateParsed) {
    const bareOrdinalPattern = /\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b/i;
    const matchBare = request.match(bareOrdinalPattern);
    
    if (matchBare) {
      const day = parseInt(matchBare[1]);
      const today = new Date($json.today);
      const currentMonth = today.getMonth();
      const currentYear = today.getFullYear();
      const currentDay = today.getDate();
      
      // Validate day is reasonable (1-31)
      if (day >= 1 && day <= 31) {
        let targetMonth = currentMonth;
        let targetYear = currentYear;
        
        // If the day has already passed this month, assume next month
        if (day < currentDay) {
          targetMonth = currentMonth + 1;
          if (targetMonth > 11) {
            targetMonth = 0;
            targetYear++;
          }
        }
        
        const parsedDate = new Date(targetYear, targetMonth, day);
        // Verify the date is valid (handles cases like "31st" in a 30-day month)
        if (parsedDate.getDate() === day) {
          startDate = parsedDate.toISOString().slice(0, 10);
          endDate = startDate;
          dateParsed = true;
        }
      }
    }
  }
}

// Extract search term for delete (the event title/description)
let searchTerm = '';
if (action === 'delete' && !deleteAll) {
  searchTerm = request
    .replace(/\b(cancel|delete|remove|drop|clear|wipe)\b/gi, '')
    .replace(/\b(my|the|a|an)\b/gi, '')
    .replace(/\b(tomorrow|today|tonight|yesterday)\b/gi, '')
    .replace(/\b(day before yesterday|day after tomorrow)\b/gi, '')
    .replace(/\b\d+\s*days?\s*ago\b/gi, '')
    .replace(/\bin\s*\d+\s*days?\b/gi, '')
    .replace(/\b(on|at|for)\b/gi, '')
    .replace(/\b(\d{1,2})(st|nd|rd|th)?\s*(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\b/gi, '')
    .replace(/\b(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s*(\d{1,2})(st|nd|rd|th)?\b/gi, '')
    .replace(/\b\d{1,2}(:\d{2})?\s*(am|pm)?\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Extract time for more precise matching (only if user explicitly specified a time)
let searchTime = '';
const timeMatch = request.match(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i);
if (timeMatch) {
  let hour = parseInt(timeMatch[1]);
  const minutes = timeMatch[2] || '00';
  const ampm = timeMatch[3]?.toLowerCase();
  
  if (ampm === 'pm' && hour !== 12) hour += 12;
  if (ampm === 'am' && hour === 12) hour = 0;
  
  searchTime = `${hour.toString().padStart(2, '0')}:${minutes}`;
}

return {
  json: {
    ...$json,
    action: action,
    startDate: startDate,
    endDate: endDate,
    searchTerm: searchTerm,
    searchTime: searchTime,
    deleteAll: deleteAll
  }
};
