/**
 * Query_Calendar - CalDAV Calendar Query
 * 
 * Workflow: Calendar_input/output
 * Node: Query_Calendar
 * 
 * Purpose: Queries Nextcloud CalDAV for events within a date range.
 *          Used for "what's on my calendar" type queries.
 * 
 * Environment Variables Required:
 *   - NEXTCLOUD_URL: CalDAV calendar URL
 *   - NEXTCLOUD_USERNAME: Nextcloud username
 *   - NEXTCLOUD_PASSWORD: Nextcloud app password
 * 
 * Input: $json.startDate, $json.endDate, $json.contactId
 * Output: data (XML response), statusCode, contactId, startDate, endDate
 * 
 * Last updated: 2026-01-25
 */

const calendarUrl = $env.NEXTCLOUD_URL;
const username = $env.NEXTCLOUD_USERNAME;
const password = $env.NEXTCLOUD_PASSWORD;

const startDate = $json.startDate.replace(/-/g, '');
const endDate = $json.endDate.replace(/-/g, '');

const body = `<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop>
    <D:getetag/>
    <C:calendar-data/>
  </D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="${startDate}T000000Z" end="${endDate}T235959Z"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>`;

const response = await this.helpers.httpRequest({
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

return {
  json: {
    data: response.body,
    statusCode: response.statusCode,
    contactId: $json.contactId,
    startDate: $json.startDate,
    endDate: $json.endDate
  }
};
