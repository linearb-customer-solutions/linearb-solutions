/**
 * Maps ServiceNow service names to LinearB team names.
 *
 * LinearB's Incident API requires the `teams` field to be
 * an array of lowercase strings, so every value here is lowercase.
 * Ref: https://docs.linearb.io/api-incidents/#body-parameters
 */
const SERVICE_TO_TEAM = {
  "Home Care":        "home care",
  "Core Communities": "core & community",
  "Data Services":    "data",
};

const LINEARB_INCIDENTS_URL = "https://public-api.linearb.io/api/v1/incidents";

/**
 * Given a ServiceNow incident, return a LinearB-ready incident payload.
 *
 * @param {Object} snowIncident - Incoming ServiceNow incident record
 * @param {string} snowIncident.number        - e.g. "INC0012345"
 * @param {string} snowIncident.short_description
 * @param {string} snowIncident.sys_created_on - ISO-ish timestamp
 * @param {string} snowIncident.resolved_at    - ISO-ish timestamp (may be empty)
 * @param {string} snowIncident.service        - ServiceNow business service name
 * @param {string} [snowInstance]              - ServiceNow instance hostname (e.g. "acme.service-now.com")
 * @returns {Object} Payload for POST /api/v1/incidents
 */
function toLinearBIncident(snowIncident, snowInstance) {
  const team = SERVICE_TO_TEAM[snowIncident.service];

  if (!team) {
    console.warn(`No LinearB team mapping for ServiceNow service: "${snowIncident.service}"`);
  }

  return {
    provider_id: snowIncident.number,
    http_url: `https://${snowInstance}/nav_to.do?uri=incident.do?sys_id=${snowIncident.sys_id}`,
    title: snowIncident.short_description,
    issued_at: new Date(snowIncident.sys_created_on).toISOString(),
    ...(snowIncident.resolved_at && {
      ended_at: new Date(snowIncident.resolved_at).toISOString(),
    }),
    teams: team ? [team] : [],
  };
}

/**
 * Send an incident payload to LinearB, or log it if dryRun is true.
 *
 * @param {Object} payload - Output of toLinearBIncident()
 * @param {Object} options
 * @param {boolean} options.dryRun - If true, log the payload and skip the HTTP call
 * @param {string}  options.apiKey - LinearB API key (required when dryRun is false)
 * @returns {Promise<{dryRun: boolean, status?: number, body?: any}>}
 */
async function sendIncident(payload, { dryRun, apiKey }) {
  if (dryRun) {
    console.log("[DRY RUN] Would POST to LinearB Incidents API:");
    console.log(`  URL: ${LINEARB_INCIDENTS_URL}`);
    console.log("  Body:");
    console.log(JSON.stringify(payload, null, 2));
    return { dryRun: true };
  }

  if (!apiKey) {
    throw new Error("LINEARB_API_KEY is required when dryRun is false.");
  }

  const response = await fetch(LINEARB_INCIDENTS_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      `LinearB API responded ${response.status}: ${JSON.stringify(body)}`
    );
  }

  return { dryRun: false, status: response.status, body };
}

// ── Example usage ───────────────────────────────────────────
// Run with: node servicenow-linearb-mapping.js
//
// Env vars:
//   LINEARB_API_KEY      – required unless DRY_RUN=true
//   SERVICENOW_INSTANCE  – your ServiceNow host (e.g. "acme.service-now.com")
//   DRY_RUN              – "true" to skip the HTTP call and log the payload
if (require.main === module) {
  const dryRun = process.env.DRY_RUN === "true" || process.argv.includes("--dry-run");
  const apiKey = process.env.LINEARB_API_KEY;
  const snowInstance = process.env.SERVICENOW_INSTANCE || "yourinstance.service-now.com";

  const sampleSnowIncident = {
    number: "INC0012345",
    sys_id: "abc123def456",
    short_description: "Home Care portal returning 503",
    sys_created_on: "2026-04-01T14:30:00Z",
    resolved_at: "2026-04-01T16:45:00Z",
    service: "Home Care",
  };

  const payload = toLinearBIncident(sampleSnowIncident, snowInstance);

  sendIncident(payload, { dryRun, apiKey })
    .then((result) => {
      if (!result.dryRun) {
        console.log(`LinearB responded ${result.status}`);
        console.log(JSON.stringify(result.body, null, 2));
      }
    })
    .catch((err) => {
      console.error(err.message);
      process.exit(1);
    });
}

module.exports = { toLinearBIncident, sendIncident, SERVICE_TO_TEAM };
