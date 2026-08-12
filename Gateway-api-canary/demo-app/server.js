const express = require("express");
const client = require("prom-client");

const app = express();

const PORT = 8080;
const VERSION = process.env.VERSION || "unknown";

const register = new client.Registry();

client.collectDefaultMetrics({
  register
});

const httpRequests = new client.Counter({
  name: "demo_http_requests_total",
  help: "Total HTTP requests",
  labelNames: ["version", "method", "status"]
});

register.registerMetric(httpRequests);

app.use((req, res, next) => {
  res.on("finish", () => {
    httpRequests.inc({
      version: VERSION,
      method: req.method,
      status: res.statusCode
    });
  });

  next();
});

app.get("/", (req, res) => {
  res.send(`Hello from VERSION ${VERSION}`);
});

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", register.contentType);
  res.end(await register.metrics());
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});