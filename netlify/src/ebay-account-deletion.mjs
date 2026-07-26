import { createHash, createVerify } from "node:crypto";

import postgres from "postgres";

const ENDPOINT_PATH = "/api/v1/webhooks/ebay/account-deletion";
const NOTIFICATION_TOPIC = "MARKETPLACE_ACCOUNT_DELETION";
const EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope";
const MAX_BODY_BYTES = 64 * 1024;
const SIGNATURE_HEADER_MAX_BYTES = 4096;
const WEBHOOK_VERSION = "2026-07-24.4";

let databaseClient;
let accessToken;
let accessTokenExpiresAt = 0;
const publicKeyCache = new Map();

export const config = {
  path: ENDPOINT_PATH,
};

export default async function handler(request, context) {
  if (request.method === "GET") {
    return handleChallenge(request);
  }
  if (request.method === "POST") {
    return handleNotification(request, context);
  }
  return new Response(null, {
    status: 405,
    headers: {
      Allow: "GET, POST",
      "Cache-Control": "no-store",
    },
  });
}

async function handleChallenge(request) {
  const verificationToken = requiredEnvironment("DEAL_SCANNER_EBAY_DELETION_VERIFICATION_TOKEN");
  if (!isVerificationToken(verificationToken)) {
    return problem(503, "The eBay verification token is not configured correctly.");
  }
  const requestUrl = new URL(request.url);
  const challengeCode = requestUrl.searchParams.get("challenge_code");
  if (!challengeCode || challengeCode.length > 512) {
    return problem(400, "A valid challenge_code is required.");
  }
  const endpointUrl =
    process.env.DEAL_SCANNER_EBAY_DELETION_ENDPOINT_URL || `${requestUrl.origin}${requestUrl.pathname}`;
  return Response.json(
    {
      challengeResponse: challengeResponse(challengeCode, verificationToken, endpointUrl),
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}

export async function handleNotification(
  request,
  context,
  {
    verifySignature = verifyEbaySignature,
    processDeletion = processAccountDeletion,
  } = {},
) {
  const verificationToken = requiredEnvironment("DEAL_SCANNER_EBAY_DELETION_VERIFICATION_TOKEN");
  if (!isVerificationToken(verificationToken)) {
    return problem(503, "The eBay account deletion endpoint is not configured.");
  }

  const rawBody = await request.text();
  if (Buffer.byteLength(rawBody, "utf8") > MAX_BODY_BYTES) {
    return problem(413, "The notification body is too large.");
  }
  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return problem(400, "The notification body must be valid JSON.");
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return problem(400, "The notification body must be a JSON object.");
  }

  const signatureHeader = request.headers.get("x-ebay-signature");
  if (!parseSignatureHeader(signatureHeader)) {
    return problem(412, "Invalid eBay notification signature.");
  }

  const event = parseDeletionEvent(payload);
  if (!event) {
    return problem(400, "Invalid Marketplace Account Deletion notification.");
  }

  const processing = verifyAndProcessNotification(
    payload,
    signatureHeader,
    event,
    verifySignature,
    processDeletion,
  );
  if (typeof context?.waitUntil === "function") {
    context.waitUntil(processing);
  } else {
    await processing;
  }
  return new Response(null, {
    status: 204,
    headers: {
      "Cache-Control": "no-store",
      "X-Graper-Webhook-Version": WEBHOOK_VERSION,
    },
  });
}

async function verifyAndProcessNotification(
  payload,
  signatureHeader,
  event,
  verifySignature,
  processDeletion,
) {
  try {
    const signatureValid = await verifySignature(payload, signatureHeader);
    if (!signatureValid) {
      console.warn("Invalid eBay notification signature", {
        notificationId: event.notificationId,
      });
      return;
    }
    const result = await processDeletion(event);
    console.info("eBay account deletion processed", {
      notificationId: event.notificationId,
      alreadyProcessed: result.alreadyProcessed,
      deletedSellerCount: result.deletedSellerCount,
      deletedListingCount: result.deletedListingCount,
    });
  } catch (error) {
    console.error("eBay account deletion background processing failed", {
      notificationId: event.notificationId,
      error: errorName(error),
    });
  }
}

export function challengeResponse(challengeCode, verificationToken, endpointUrl) {
  return createHash("sha256")
    .update(`${challengeCode}${verificationToken}${endpointUrl}`, "utf8")
    .digest("hex");
}

export async function verifyEbaySignature(payload, signatureHeader, getPublicKey = fetchPublicKey) {
  const envelope = parseSignatureHeader(signatureHeader);
  if (!envelope) {
    return false;
  }
  const publicKey = await getPublicKey(envelope.keyId);
  const verifier = createVerify("ssl3-sha1");
  verifier.update(JSON.stringify(payload), "utf8");
  verifier.end();
  return verifier.verify(publicKey, envelope.signature);
}

export function parseDeletionEvent(payload) {
  if (payload?.metadata?.topic !== NOTIFICATION_TOPIC) {
    return null;
  }
  const notificationId = payload?.notification?.notificationId;
  const data = payload?.notification?.data;
  if (
    typeof notificationId !== "string" ||
    notificationId.length < 1 ||
    notificationId.length > 128 ||
    !data ||
    typeof data !== "object" ||
    Array.isArray(data)
  ) {
    return null;
  }
  const identifiers = [data.username, data.userId, data.eiasToken].filter(
    (value) => typeof value === "string" && value.length > 0,
  );
  if (identifiers.length === 0 || identifiers.some((value) => value.length > 2048)) {
    return null;
  }
  return {
    notificationId,
    identifiers: [...new Set(identifiers)],
  };
}

function parseSignatureHeader(signatureHeader) {
  if (
    typeof signatureHeader !== "string" ||
    Buffer.byteLength(signatureHeader, "utf8") > SIGNATURE_HEADER_MAX_BYTES
  ) {
    return null;
  }
  try {
    const decodedEnvelope = decodeBase64Strict(signatureHeader);
    if (!decodedEnvelope) {
      return null;
    }
    const envelope = JSON.parse(decodedEnvelope.toString("utf8"));
    if (
      typeof envelope?.kid !== "string" ||
      !/^[A-Za-z0-9_-]{1,255}$/.test(envelope.kid) ||
      typeof envelope.signature !== "string"
    ) {
      return null;
    }
    const signature = decodeBase64Strict(envelope.signature);
    return signature ? { keyId: envelope.kid, signature } : null;
  } catch {
    return null;
  }
}

function decodeBase64Strict(value) {
  if (typeof value !== "string" || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
    return null;
  }
  return Buffer.from(value, "base64");
}

async function fetchPublicKey(keyId) {
  const now = Date.now();
  const cached = publicKeyCache.get(keyId);
  if (cached?.expiresAt > now) {
    return cached.key;
  }
  const environment = process.env.DEAL_SCANNER_EBAY_ENVIRONMENT || "production";
  const apiBase =
    environment === "sandbox" ? "https://api.sandbox.ebay.com" : "https://api.ebay.com";
  const token = await fetchAccessToken(environment);
  const response = await fetch(
    `${apiBase}/commerce/notification/v1/public_key/${encodeURIComponent(keyId)}`,
    {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      redirect: "error",
    },
  );
  if (!response.ok) {
    throw new Error("EBAY_PUBLIC_KEY_UNAVAILABLE");
  }
  const body = await response.json();
  if (typeof body?.key !== "string" || !body.key.trim()) {
    throw new Error("EBAY_PUBLIC_KEY_INVALID");
  }
  const key = normalizePublicKey(body.key);
  const cacheSeconds = Number.parseInt(
    process.env.DEAL_SCANNER_EBAY_NOTIFICATION_PUBLIC_KEY_CACHE_SECONDS || "3600",
    10,
  );
  publicKeyCache.set(keyId, {
    key,
    expiresAt: now + Math.max(cacheSeconds, 60) * 1000,
  });
  return key;
}

async function fetchAccessToken(environment) {
  const now = Date.now();
  if (accessToken && accessTokenExpiresAt > now) {
    return accessToken;
  }
  const suffix = environment === "sandbox" ? "SANDBOX" : "PRODUCTION";
  const clientId =
    process.env[`DEAL_SCANNER_EBAY_${suffix}_CLIENT_ID`] ||
    requiredEnvironment("DEAL_SCANNER_EBAY_CLIENT_ID");
  const clientSecret =
    process.env[`DEAL_SCANNER_EBAY_${suffix}_CLIENT_SECRET`] ||
    requiredEnvironment("DEAL_SCANNER_EBAY_CLIENT_SECRET");
  if (!clientId || !clientSecret) {
    throw new Error("EBAY_CREDENTIALS_MISSING");
  }
  const tokenUrl =
    environment === "sandbox"
      ? "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
      : "https://api.ebay.com/identity/v1/oauth2/token";
  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      scope: EBAY_SCOPE,
    }),
    redirect: "error",
  });
  if (!response.ok) {
    throw new Error("EBAY_TOKEN_UNAVAILABLE");
  }
  const body = await response.json();
  if (typeof body?.access_token !== "string" || !body.access_token) {
    throw new Error("EBAY_TOKEN_INVALID");
  }
  accessToken = body.access_token;
  accessTokenExpiresAt = now + Math.max(Number(body.expires_in || 7200) - 120, 60) * 1000;
  return accessToken;
}

function normalizePublicKey(value) {
  const begin = "-----BEGIN PUBLIC KEY-----";
  const end = "-----END PUBLIC KEY-----";
  const stripped = value.trim();
  if (!stripped.startsWith(begin) || !stripped.endsWith(end)) {
    return stripped;
  }
  const body = stripped.slice(begin.length, -end.length).replaceAll(/\s/g, "");
  return `${begin}\n${body.match(/.{1,64}/g)?.join("\n") || body}\n${end}\n`;
}

export async function processAccountDeletion(event) {
  const sql = database();
  return sql.begin(async (transaction) => {
    await transaction`select pg_advisory_xact_lock(hashtextextended(${event.notificationId}, 0))`;
    await transaction`select set_config('search_path', 'deal_scanner,public', true)`;
    await transaction`select set_config('deal_scanner.account_deletion', 'on', true)`;

    const existing = await transaction`
      select deleted_seller_count, deleted_listing_count
      from deal_scanner.ebay_account_deletion_events
      where notification_id = ${event.notificationId}
    `;
    if (existing.length > 0) {
      return {
        alreadyProcessed: true,
        deletedSellerCount: existing[0].deleted_seller_count,
        deletedListingCount: existing[0].deleted_listing_count,
      };
    }

    const identifiers = event.identifiers;
    const foldedIdentifiers = [...new Set(identifiers.map((value) => value.toLocaleLowerCase("en-US")))];
    const sellers = await transaction`
      select seller.id
      from deal_scanner.sellers seller
      where seller.platform = 'ebay'
        and (
          seller.external_id in ${transaction(identifiers)}
          or lower(seller.external_id) in ${transaction(foldedIdentifiers)}
          or seller.display_name in ${transaction(identifiers)}
          or lower(seller.display_name) in ${transaction(foldedIdentifiers)}
          or ${jsonContainsIdentifier(transaction, "seller.raw_data", identifiers, foldedIdentifiers)}
        )
    `;
    const sellerIds = new Set(sellers.map((row) => row.id));
    const sellerListingFilter =
      sellerIds.size > 0
        ? transaction`or listing.seller_id in ${transaction([...sellerIds])}`
        : transaction``;
    const listings = await transaction`
      select listing.id, listing.seller_id
      from deal_scanner.listings listing
      where listing.platform = 'ebay'
        and (
          listing.external_id in ${transaction(identifiers)}
          or lower(listing.external_id) in ${transaction(foldedIdentifiers)}
          or listing.url in ${transaction(identifiers)}
          or listing.title in ${transaction(identifiers)}
          or listing.description in ${transaction(identifiers)}
          or listing.location in ${transaction(identifiers)}
          ${sellerListingFilter}
          or exists (
            select 1
            from deal_scanner.listing_snapshots snapshot
            where snapshot.listing_id = listing.id
              and ${jsonContainsIdentifier(transaction, "snapshot.raw_data", identifiers, foldedIdentifiers)}
          )
        )
    `;
    const listingIds = new Set(listings.map((row) => row.id));
    for (const listing of listings) {
      if (listing.seller_id) {
        sellerIds.add(listing.seller_id);
      }
    }
    if (sellerIds.size > 0) {
      const sellerListings = await transaction`
        select id
        from deal_scanner.listings
        where platform = 'ebay' and seller_id in ${transaction([...sellerIds])}
      `;
      for (const listing of sellerListings) {
        listingIds.add(listing.id);
      }
    }

    const storagePaths =
      listingIds.size > 0
        ? await transaction`
            select distinct storage_path
            from deal_scanner.listing_images
            where listing_id in ${transaction([...listingIds])} and storage_path is not null
          `
        : [];
    await deletePrivateImages(storagePaths.map((row) => row.storage_path));

    const observations = await transaction`
      select observation.id
      from deal_scanner.price_observations observation
      where observation.platform = 'ebay'
        and ${jsonContainsIdentifier(
          transaction,
          "observation.metadata",
          identifiers,
          foldedIdentifiers,
        )}
    `;
    const observationIds = new Set(observations.map((row) => row.id));
    if (listingIds.size > 0) {
      const listingObservations = await transaction`
        select id
        from deal_scanner.price_observations
        where listing_id in ${transaction([...listingIds])}
      `;
      for (const observation of listingObservations) {
        observationIds.add(observation.id);
      }
    }

    const aggregateIds = [...sellerIds, ...listingIds];
    if (aggregateIds.length > 0) {
      await transaction`
        delete from deal_scanner.audit_events where aggregate_id in ${transaction(aggregateIds)}
      `;
    }
    if (observationIds.size > 0) {
      await transaction`
        delete from deal_scanner.price_observations where id in ${transaction([...observationIds])}
      `;
    }
    if (listingIds.size > 0) {
      await transaction`
        delete from deal_scanner.listings where id in ${transaction([...listingIds])}
      `;
    }
    if (sellerIds.size > 0) {
      await transaction`
        delete from deal_scanner.sellers where id in ${transaction([...sellerIds])}
      `;
    }
    await transaction`
      insert into deal_scanner.ebay_account_deletion_events (
        notification_id,
        deleted_seller_count,
        deleted_listing_count
      ) values (
        ${event.notificationId},
        ${sellerIds.size},
        ${listingIds.size}
      )
    `;
    return {
      alreadyProcessed: false,
      deletedSellerCount: sellerIds.size,
      deletedListingCount: listingIds.size,
    };
  });
}

function jsonContainsIdentifier(transaction, expression, identifiers, foldedIdentifiers) {
  return transaction`
    exists (
      select 1
      from jsonb_path_query(
        coalesce(${transaction.unsafe(expression)}, '{}'::jsonb),
        '$.** ? (@.type() == "string")'
      ) value
      where value #>> '{}' in ${transaction(identifiers)}
         or lower(value #>> '{}') in ${transaction(foldedIdentifiers)}
    )
  `;
}

function database() {
  if (databaseClient) {
    return databaseClient;
  }
  const databaseUrl = requiredEnvironment("DEAL_SCANNER_SUPABASE_DB_URL");
  if (!databaseUrl) {
    throw new Error("DATABASE_URL_MISSING");
  }
  databaseClient = postgres(databaseUrl, {
    connect_timeout: 15,
    idle_timeout: 10,
    max: 1,
    prepare: false,
    ssl: "require",
  });
  return databaseClient;
}

export async function closeDatabaseConnection() {
  if (databaseClient) {
    await databaseClient.end({ timeout: 2 });
    databaseClient = undefined;
  }
}

async function deletePrivateImages(storagePaths) {
  const uniquePaths = [...new Set(storagePaths.filter(Boolean))];
  if (uniquePaths.length === 0) {
    return;
  }
  const supabaseUrl = requiredEnvironment("DEAL_SCANNER_SUPABASE_URL")?.replace(/\/$/, "");
  const serviceRoleKey = requiredEnvironment("DEAL_SCANNER_SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error("SUPABASE_STORAGE_CONFIGURATION_MISSING");
  }
  for (let index = 0; index < uniquePaths.length; index += 1000) {
    const response = await fetch(`${supabaseUrl}/storage/v1/object/listing-images`, {
      method: "DELETE",
      headers: {
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prefixes: uniquePaths.slice(index, index + 1000),
      }),
      redirect: "error",
    });
    if (!response.ok) {
      throw new Error("SUPABASE_STORAGE_DELETE_FAILED");
    }
  }
}

function requiredEnvironment(name) {
  return process.env[name]?.trim() || "";
}

function isVerificationToken(value) {
  return /^[A-Za-z0-9_-]{32,80}$/.test(value);
}

function problem(status, detail) {
  return Response.json(
    {
      title: detail,
      status,
    },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "application/problem+json",
      },
    },
  );
}

function errorName(error) {
  return error instanceof Error ? error.name : "UnknownError";
}
