# VLESS REALITY + Cloudflare DNS

For a REALITY endpoint such as `tr1.example.com:443`, the DNS record **must be DNS-only** (grey cloud) when the client is expected to connect directly to Xray/Marzban on the VPS.

If the record is orange-cloud proxied, the client reaches Cloudflare's TLS edge and receives a real TLS certificate. Xray then logs errors such as:

`REALITY: received real certificate (potential MITM or redirection)`

That is not a client bug. It means the REALITY handshake did not reach the intended Xray listener.

Recommended split:

- `tr1.example.com` -> A/AAAA to VPS -> **DNS only**
- `panel.example.com` -> panel web UI; may use a reverse proxy/CDN only if the web panel configuration supports it. Do not route the REALITY listener through Cloudflare's normal HTTP proxy.

Also verify the REALITY destination/SNI is a reachable TLS 1.3-capable site and that server/client public key, short ID, SNI and flow match exactly.
