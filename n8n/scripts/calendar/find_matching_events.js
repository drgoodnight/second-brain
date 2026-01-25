/**
 * Find_Matching_Events - Calendar Event Search for Delete
 * 
 * Workflow: Calendar_input/output
 * Node: Find_Matching_Events
 * 
 * Purpose: Queries CalDAV for events on a specific date and filters
 *          based on search term and/or time for delete operations.
 * 
 * Environment Variables Required:
 *   - NEXTCLOUD_URL: CalDAV calendar URL
 *   - NEXTCLOUD_USERNAME: Nextcloud username
 *   - NEXTCLOUD_PASSWORD: Nextcloud app password
 * 
 * Input: $json.startDate, $json.searchTerm, $json.searchTime
 * Output: matches[], matchCount, allEventsOnDay
 * 
 * Last updated: 2026-01-25
 */

const searchDate = $json.startDate;
const searchTerm = $json.searchTerm || '';
const searchTime = $json.searchTime || '';

// Use environment variables - no hardcoded credentials
const calendarUrl = $env.NEXTCLOUD_URL;
const username = $env.NEXTCLOUD_USERNAME;
const password = $env.NEXTCLOUD_PASSWORD;

// Format date for CalDAV query
const formattedDate = searchDate.replace(/-/g, '');

const body = `<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop>
    <D:getetag/>
    <C:calendar-data/>
  </D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="${formattedDate}T000000Z" end="${formattedDate}T235959Z"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>`;

let response;
try {
  response = await this.helpers.httpRequest({
    method: 'REPORT',
    url: calendarUrl,
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Depth': '1',
      'Authorization': 'Basic ' + Buffer.from(username + ':' + password).toString('base64')
    },
    body: body,
    returnFullResponse: true
  });
} catch (error) {
  return {
    json: {
      ...$json,
      matches: [],
      matchCount: 0,
      error: `Calendar query failed: ${error.message}`
    }
  };
}

// Parse the XML response to extract events
const events = [];
const responseBody = response.body || response;

const hrefRegex = /<d:href>([^<]+)<\/d:href>/gi;
const calDataRegex = /<cal:calendar-data[^>]*>([\s\S]*?)<\/cal:calendar-data>/gi;

let hrefMatches = [...responseBody.matchAll(hrefRegex)];
let calDataMatches = [...responseBody.matchAll(calDataRegex)];

for (let i = 0; i < calDataMatches.length; i++) {
  const icsData = calDataMatches[i][1];
  const href = hrefMatches[i]?.[1] || '';
  
  // Extract SUMMARY
  const summaryMatch = icsData.match(/SUMMARY:(.+?)(?:\r?\n|$)/);
  const summary = summaryMatch ? summaryMatch[1].trim() : 'Untitled';
  
  // Extract DTSTART
  const dtstartMatch = icsData.match(/DTSTART[^:]*:(\d{4})(\d{2})(\d{2})T?(\d{2})?(\d{2})?/);
  let startTime = '';
  let displayTime = '';
  if (dtstartMatch) {
    if (dtstartMatch[4] && dtstartMatch[5]) {
      startTime = `${dtstartMatch[4]}:${dtstartMatch[5]}`;
      let hour = parseInt(dtstartMatch[4]);
      const ampm = hour >= 12 ? 'PM' : 'AM';
      hour = hour % 12 || 12;
      displayTime = `${hour}:${dtstartMatch[5]} ${ampm}`;
    } else {
      displayTime = 'All day';
    }
  }
  
  // Extract UID
  const uidMatch = icsData.match(/UID:(.+?)(?:\r?\n|$)/);
  const uid = uidMatch ? uidMatch[1].trim() : '';
  
  events.push({
    summary,
    startTime,
    displayTime,
    href,
    uid,
    icsData
  });
}

// Filter matches based on search criteria
let matches = events.filter(event => {
  const summaryLower = event.summary.toLowerCase();
  const searchLower = searchTerm.toLowerCase();
  
  // Bidirectional matching: 
  // - searchTerm in summary ("test" matches "Test Event")
  // - summary in searchTerm ("Test" matches "delete test event")
  const termMatch = !searchTerm || 
    summaryLower.includes(searchLower) ||
    searchLower.includes(summaryLower);
  
  const timeMatch = !searchTime || 
    event.startTime === searchTime;
  
  if (searchTerm && searchTime) {
    return termMatch && timeMatch;
  }
  
  return termMatch || (searchTime && timeMatch);
});

if (!searchTerm && !searchTime) {
  matches = events;
}

return {
  json: {
    ...$json,
    matches: matches,
    matchCount: matches.length,
    allEventsOnDay: events.length
  }
};
