const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function harness() {
  // Execute the production pump unchanged, supplying only its surrounding state.
  const source = fs.readFileSync(require.resolve("../integrations/chatgpt-extension/content.js"), "utf8");
  const pump = source.slice(source.indexOf("  async function pump()"), source.indexOf("  function schedule()"));
  const requests = [], results = [];
  const context = vm.createContext({
    enabled: true, epoch: 1, currentChat: "chatgpt:first", running: 0, queue: [],
    Date, JSON, serializeMessage: source => source,
    scan: () => {}, showResult: (state, result) => results.push({state, result}),
    send(message) { return new Promise(resolve => requests.push({message, resolve})); },
  });
  vm.runInContext(pump + "\nglobalThis.start = pump;", context);
  function job(id) {
    const source = {text: `Notizia ${id}`, links: []};
    return {node: {isConnected: true}, source, state: {badge: {}, pending: true}, signature: JSON.stringify(source), epoch: 1, chatId: "chatgpt:first", payload: {id}};
  }
  context.queue.push(job("first"), job("second"));
  return {context, requests, results};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test("the production pump sends one item at a time until the previous assessment completes", async () => {
  const {context, requests, results} = harness();
  await context.start();
  await context.start();
  assert.equal(requests.length, 1);
  assert.equal(context.running, 1);
  requests[0].resolve({ok: true}); await settle();
  assert.equal(requests.length, 2);
  assert.equal(results.length, 1);
  assert.equal(context.running, 1);
  requests[1].resolve({ok: true}); await settle();
  assert.equal(results.length, 2);
  assert.equal(context.running, 0);
});

test("turning the chat off discards the pending result and does not send the next item", async () => {
  const {context, requests, results} = harness();
  await context.start();
  context.enabled = false; context.epoch += 1; context.queue = [];
  requests[0].resolve({ok: true}); await settle();
  assert.equal(results.length, 0);
  assert.equal(requests.length, 1);
  assert.equal(context.running, 0);
});

test("route changes discard results belonging to the previous chat", async () => {
  const {context, requests, results} = harness();
  await context.start();
  context.currentChat = "chatgpt:second"; context.epoch += 1; context.queue = [];
  requests[0].resolve({ok: true}); await settle();
  assert.equal(results.length, 0);
  assert.equal(requests.length, 1);
  assert.equal(context.running, 0);
});
