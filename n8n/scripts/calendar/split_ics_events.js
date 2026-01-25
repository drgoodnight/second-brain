/**
 * Split_ICS_Events - ICS Parser and Splitter
 * 
 * Workflow: calendar_agent
 * Node: Split_ICS_Events
 * 
 * Purpose: Takes ICS output from AI model and splits into individual events.
 *          Handles literal \n characters from AI output and extracts metadata
 *          for each event (summary, times, UID).
 * 
 * Input: AI model output with ICS content
 * Output: Array of individual events with uid, output (ICS), summary, times
 * 
 * Last updated: 2026-01-25
 */

const items = $input.all();
const results = [];

// Helper to format date nicely
function formatDate(dateStr) {
  const year = dateStr.substr(0, 4);
  const month = parseInt(dateStr.substr(4, 2), 10);
  const day = parseInt(dateStr.substr(6, 2), 10);
  
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  
  const ordinal = (d) => {
    if (d > 3 && d < 21) return d + 'th';
    switch (d % 10) {
      case 1: return d + 'st';
      case 2: return d + 'nd';
      case 3: return d + 'rd';
      default: return d + 'th';
    }
  };
  
  return `${ordinal(day)} ${months[month - 1]}`;
}

// Helper to extract time from datetime string
function extractTime(dt) {
  if (dt && dt.includes('T')) {
    const hour = dt.substr(9, 2);
    const minute = dt.substr(11, 2);
    return `${hour}:${minute}`;
  }
  return '';
}

for (const item of items) {
  // Get ICS content and normalize newlines
  let icsContent = item.json.content || item.json.output || item.json.text || '';
  
  // CRITICAL: Convert literal \n to actual newlines
  icsContent = icsContent.replace(/\\n/g, '\n');
  
  // Also handle \r\n and normalize to \n
  icsContent = icsContent.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  
  const contactId = item.json.contactId || $('When Executed by Another Workflow').item.json.contactId;
  
  const veventMatches = icsContent.match(/BEGIN:VEVENT[\s\S]*?END:VEVENT/g) || [];
  
  for (const vevent of veventMatches) {
    // Extract UID
    const uidMatch = vevent.match(/UID:(.+)/);
    const uid = uidMatch ? uidMatch[1].trim() : `event-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Extract SUMMARY
    const summaryMatch = vevent.match(/SUMMARY:(.+)/);
    const summary = summaryMatch ? summaryMatch[1].trim() : 'Untitled Event';
    
    // Extract DTSTART
    const dtstartMatch = vevent.match(/DTSTART[^:]*:(\d{8}T?\d{0,6})/);
    let startTime = '';
    let dateStr = '';
    
    if (dtstartMatch) {
      const dt = dtstartMatch[1];
      dateStr = formatDate(dt);
      startTime = extractTime(dt);
    }
    
    // Extract DTEND
    const dtendMatch = vevent.match(/DTEND[^:]*:(\d{8}T?\d{0,6})/);
    let endTime = '';
    
    if (dtendMatch) {
      endTime = extractTime(dtendMatch[1]);
    }
    
    // Rebuild complete ICS for this single event with proper newlines
    const singleIcs = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//n8n AI//SecondBrain//EN
CALSCALE:GREGORIAN
${vevent}
END:VCALENDAR`;
    
    results.push({
      json: {
        uid,
        output: singleIcs,
        summary,
        startTime,
        endTime,
        date: dateStr,
        contactId
      }
    });
  }
}

if (results.length === 0) {
  return items;
}

return results;
