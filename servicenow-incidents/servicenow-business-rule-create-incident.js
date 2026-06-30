/**
 * ServiceNow Business Rule: push an Incident record to LinearB.
 *
 * WHERE THIS RUNS
 *   System Definition → Business Rules → New
 *     Name:       Push Incident to LinearB
 *     Table:      Incident [incident]
 *     Advanced:   true
 *     When:       after          (use "async" if you don't need to block the save)
 *     Insert:     true
 *     Update:     true           (optional — only if you want re-pushes on resolve, etc.)
 *     Condition:  current.short_description.changes() || current.resolved_at.changes() || current.operation() == 'insert'
 *
 * SYSTEM PROPERTIES (System Properties → New)
 *   x.linearb.api_key        type: password2   – LinearB API key (encrypted at rest)
 *   x.linearb.dry_run        type: true|false  – "true" = log payload, do NOT POST
 *   x.linearb.incidents_url  type: string      – Defaults to public LinearB URL
 *
 * DRY RUN
 *   ServiceNow has no native "dry run" for outbound REST, so we gate the
 *   RESTMessageV2.execute() call on the x.linearb.dry_run system property.
 *   When true, the fully-built payload is written to the system log
 *   (System Log → All) under source "LinearB" and no HTTP call is made.
 *
 * NOTE ON SCRIPT ENGINE
 *   ServiceNow server scripts run on Rhino with ES5 semantics by default
 *   (var, no arrow functions, no template literals, no destructuring).
 *   Code below is written ES5-safe so it works on every supported release.
 */
(function executeRule(current, previous /* null on insert */) {

    var SERVICE_TO_TEAM = {
        'Home Care':        'home care',
        'Core Communities': 'core & community',
        'Data Services':    'data'
    };

    var DEFAULT_URL = 'https://public-api.linearb.io/api/v1/incidents';
    var LOG_SOURCE  = 'LinearB';

    // ── Resolve the ServiceNow service name ──────────────────
    // Adjust the field name to match your instance. Common options:
    //   business_service       – reference to cmdb_ci_service
    //   service_offering       – reference to service_offering
    //   u_service              – custom string field on incident
    var serviceName = current.business_service.getDisplayValue();
    if (!serviceName) {
        serviceName = current.service_offering.getDisplayValue();
    }

    var team = SERVICE_TO_TEAM[serviceName];
    if (!team) {
        gs.warn('[' + LOG_SOURCE + '] No team mapping for service "' + serviceName +
                '" on ' + current.number + '. Sending empty teams[].');
    }

    // ── Build the http_url back to the ServiceNow record ─────
    var instance = gs.getProperty('instance_name'); // built-in: e.g. "acmedev"
    var httpUrl  = 'https://' + instance + '.service-now.com/nav_to.do' +
                   '?uri=incident.do?sys_id=' + current.getUniqueValue();

    // ── ServiceNow stores datetime in UTC as "YYYY-MM-DD HH:mm:ss"
    //    LinearB wants ISO-8601 with a "Z" suffix.
    function toIso(field) {
        var raw = field ? field.toString() : '';
        if (!raw) return null;
        return raw.replace(' ', 'T') + 'Z';
    }

    var payload = {
        provider_id: current.number.toString(),
        http_url:    httpUrl,
        title:       current.short_description.toString(),
        issued_at:   toIso(current.sys_created_on),
        teams:       team ? [team] : []
    };

    var endedAt = toIso(current.resolved_at);
    if (endedAt) payload.ended_at = endedAt;

    // ── Dry-run gate ─────────────────────────────────────────
    var dryRun = String(gs.getProperty('x.linearb.dry_run', 'false')).toLowerCase() === 'true';
    if (dryRun) {
        gs.info('[' + LOG_SOURCE + '] DRY RUN for ' + current.number +
                ' – would POST to LinearB: ' + JSON.stringify(payload));
        return;
    }

    // ── Real POST ────────────────────────────────────────────
    var apiKey = gs.getProperty('x.linearb.api_key');
    if (!apiKey) {
        gs.error('[' + LOG_SOURCE + '] x.linearb.api_key is not set – aborting push for ' +
                 current.number);
        return;
    }

    var url = gs.getProperty('x.linearb.incidents_url', DEFAULT_URL);

    var rm = new sn_ws.RESTMessageV2();
    rm.setEndpoint(url);
    rm.setHttpMethod('POST');
    rm.setRequestHeader('Content-Type', 'application/json');
    rm.setRequestHeader('x-api-key', apiKey);
    rm.setRequestBody(JSON.stringify(payload));

    try {
        var response = rm.execute();
        var status   = response.getStatusCode();
        if (status >= 200 && status < 300) {
            gs.info('[' + LOG_SOURCE + '] Pushed ' + current.number + ' (HTTP ' + status + ')');
        } else {
            gs.error('[' + LOG_SOURCE + '] Push failed for ' + current.number +
                     ' – HTTP ' + status + ' – ' + response.getBody());
        }
    } catch (ex) {
        gs.error('[' + LOG_SOURCE + '] Exception pushing ' + current.number +
                 ' – ' + ex.message);
    }

})(current, previous);
