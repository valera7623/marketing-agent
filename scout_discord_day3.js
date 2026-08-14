const fs = require("fs");
const path = require("path");
const https = require("https");

const root = __dirname;
const cfg = JSON.parse(fs.readFileSync(path.join(root, "data", "config.json"), "utf8"));
const token = cfg.discord_token;
const cid = "1064526595030782043";
const skip = new Set([
  "zebra3d",
  "Mephistase",
  "color500",
  "Olonnais",
  "Razjinh",
  "papapoule75",
  "valera7623",
]);
const keys = [
  "steam",
  "local",
  "traduc",
  "transl",
  "csv",
  "wishlist",
  "feedback",
  "demo",
  "alpha",
  "playtest",
  "showcase",
  "release",
  "avis",
  "retour",
  "multilang",
  "langue",
  "itch",
  "test",
];

const req = https.request(
  {
    hostname: "discord.com",
    path: `/api/v10/channels/${cid}/messages?limit=50`,
    method: "GET",
    headers: {
      Authorization: `Bot ${token}`,
      "User-Agent": "LocForgeScout/1.0",
    },
  },
  (res) => {
    let body = "";
    res.on("data", (c) => (body += c));
    res.on("end", () => {
      if (res.statusCode !== 200) {
        console.log("ERR", res.statusCode, body.slice(0, 300));
        process.exit(1);
      }
      const msgs = JSON.parse(body);
      console.log("OK", msgs.length);
      for (const m of msgs) {
        const a = m.author || {};
        const un = a.username || "";
        if (skip.has(un) || a.bot) continue;
        const content = (m.content || "").replace(/\n/g, " ");
        const low = content.toLowerCase();
        const signals =
          keys.some((k) => low.includes(k)) || low.includes("store.steampowered");
        if (signals || content.length > 80) {
          const url = `https://discord.com/channels/1021378341267320872/${cid}/${m.id}`;
          console.log("---");
          console.log("id", m.id);
          console.log("user", un);
          console.log("sig", signals ? 1 : 0);
          console.log("url", url);
          console.log("text", content.slice(0, 280));
        }
      }
    });
  }
);
req.on("error", (e) => {
  console.log("ERR", e.message);
  process.exit(1);
});
req.end();
