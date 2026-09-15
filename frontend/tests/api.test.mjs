import assert from "node:assert/strict";
import test from "node:test";

import {
  NonJsonResponseError,
  fetchJson,
  parseJsonResponse,
} from "../lib/api.ts";


test("非 JSON 响应会转换为友好错误", async () => {
  const response = new Response("<html>Internal Server Error</html>", { status: 500 });

  await assert.rejects(
    parseJsonResponse(response),
    (error) => {
      assert.ok(error instanceof NonJsonResponseError);
      assert.equal(error.message, "服务器返回异常响应，请查看后端日志");
      assert.equal(error.error, "Server returned non-JSON response");
      assert.equal(error.status, 500);
      assert.equal(error.body, "<html>Internal Server Error</html>");
      return true;
    },
  );
});

test("API JSON 错误优先展示后端 detail", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "后端返回的错误摘要" }),
    { status: 400, headers: { "Content-Type": "application/json" } },
  );
  try {
    await assert.rejects(fetchJson("/api/test"), /后端返回的错误摘要/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
