import assert from "node:assert/strict";
import { createSign, generateKeyPairSync } from "node:crypto";
import test from "node:test";

import handler, {
  challengeResponse,
  handleNotification,
  parseDeletionEvent,
  verifyEbaySignature,
} from "../src/ebay-account-deletion.mjs";

const endpointUrl =
  "https://graper-ebay-compliance.netlify.app/api/v1/webhooks/ebay/account-deletion";
const verificationToken = "netlify_account_deletion_fixture_123456789";

test("challenge uses challenge code, token, and exact endpoint URL", async () => {
  process.env.DEAL_SCANNER_EBAY_DELETION_VERIFICATION_TOKEN = verificationToken;
  process.env.DEAL_SCANNER_EBAY_DELETION_ENDPOINT_URL = endpointUrl;
  const response = await handler(
    new Request(`${endpointUrl}?challenge_code=fixture-challenge`, {
      method: "GET",
    }),
  );
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    challengeResponse: challengeResponse(
      "fixture-challenge",
      verificationToken,
      endpointUrl,
    ),
  });
});

test("signature verification accepts the official eBay envelope format", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("ec", {
    namedCurve: "prime256v1",
  });
  const payload = deletionPayload("signed-fixture");
  const signer = createSign("ssl3-sha1");
  signer.update(JSON.stringify(payload), "utf8");
  signer.end();
  const signature = signer.sign(privateKey);
  const header = Buffer.from(
    JSON.stringify({
      kid: "fixture-key",
      signature: signature.toString("base64"),
    }),
  ).toString("base64");

  assert.equal(
    await verifyEbaySignature(
      payload,
      header,
      async () => publicKey.export({ format: "pem", type: "spki" }),
    ),
    true,
  );
  assert.equal(
    await verifyEbaySignature(
      { ...payload, notification: { ...payload.notification, notificationId: "tampered" } },
      header,
      async () => publicKey.export({ format: "pem", type: "spki" }),
    ),
    false,
  );
});

test("only Marketplace Account Deletion payloads with identifiers are accepted", () => {
  const payload = deletionPayload("payload-fixture");
  assert.deepEqual(parseDeletionEvent(payload), {
    notificationId: "payload-fixture",
    identifiers: ["fixture-user", "fixture-user-id", "fixture-eias-token"],
  });
  assert.equal(
    parseDeletionEvent({
      ...payload,
      metadata: { topic: "OTHER_TOPIC" },
    }),
    null,
  );
});

test("valid notifications are acknowledged before background processing completes", async () => {
  process.env.DEAL_SCANNER_EBAY_DELETION_VERIFICATION_TOKEN = verificationToken;
  const payload = deletionPayload("background-fixture");
  const signatureHeader = Buffer.from(
    JSON.stringify({
      kid: "fixture-key",
      signature: Buffer.from("fixture-signature").toString("base64"),
    }),
  ).toString("base64");
  let backgroundTask;
  let finishProcessing;
  const processingGate = new Promise((resolve) => {
    finishProcessing = resolve;
  });
  let processedEvent;

  const response = await handleNotification(
    new Request(endpointUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-EBAY-SIGNATURE": signatureHeader,
      },
      body: JSON.stringify(payload),
    }),
    {
      waitUntil(task) {
        backgroundTask = task;
      },
    },
    {
      verifySignature: async () => {
        await processingGate;
        return true;
      },
      processDeletion: async (event) => {
        processedEvent = event;
        return {
          alreadyProcessed: false,
          deletedSellerCount: 0,
          deletedListingCount: 0,
        };
      },
    },
  );

  assert.equal(response.status, 204);
  assert.ok(backgroundTask instanceof Promise);
  assert.equal(processedEvent, undefined);
  finishProcessing();
  await backgroundTask;
  assert.deepEqual(processedEvent, parseDeletionEvent(payload));
});

function deletionPayload(notificationId) {
  return {
    metadata: {
      topic: "MARKETPLACE_ACCOUNT_DELETION",
      schemaVersion: "1.0",
    },
    notification: {
      notificationId,
      data: {
        username: "fixture-user",
        userId: "fixture-user-id",
        eiasToken: "fixture-eias-token",
      },
    },
  };
}
