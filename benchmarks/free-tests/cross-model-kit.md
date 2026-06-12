# Cross-model parse-consistency kit (free — kimi.ai + ChatGPT web)

**What this closes:** the last objection to the transport thesis — *"maybe Claude
parses ICENI well because Claude produced it."* If Kimi and GPT extract the same
fields from the same ICENI XML, the format is model-agnostic to consume — the
interoperability claim. Kimi's tokenizer (SentencePiece) is the most different
from Claude's, so Claude+Kimi is the decisive pair; GPT is a bonus.

**How to run (~10 min each):** open kimi.ai (and chat.openai.com), paste the whole
block below — prompt + XML — as one message. Record what comes back in the table.

**Pass criterion:** ≥90% field match vs Claude's reference (below) = PASS. Claude
already extracted **7/7 findings, every one with severity + CWE + location +
remediation** (deterministic XML parse and Claude's own parse both agree).

---

## PASTE THIS into kimi.ai and ChatGPT

> You are a downstream agent in a pipeline. The message below is XML produced by an
> upstream agent (a security audit). Extract every `<finding>` into a JSON array.
> For each, capture: `id`, `severity`, `cwe`, `location`, and `remediation`. Return
> ONLY the JSON array, then on a final line print `COUNT=<number of findings>`.
>
> ```xml
> <security_audit target="SessionMiddleware (internal admin panel)">
>   <findings>
>     <finding id="1" severity="Critical" cvss="9.8" cwe="CWE-502">
>       <title>Deserialization of untrusted data via pickle.loads on the session cookie</title>
>       <location>line 30: pickle.loads(base64.b64decode(raw))</location>
>       <remediation>Stop using pickle for session data; use JSON. Never deserialize attacker-controlled bytes.</remediation>
>     </finding>
>     <finding id="2" severity="High" cvss="7.5" cwe="CWE-328">
>       <title>Weak hash (MD5) used as the session authentication primitive</title>
>       <location>lines 28 and 52: hashlib.md5((SECRET + raw))</location>
>       <remediation>Replace with hmac.new(key, raw, hashlib.sha256) and hmac.compare_digest.</remediation>
>     </finding>
>     <finding id="3" severity="High" cvss="8.6" cwe="CWE-798">
>       <title>Hardcoded default secret ("changeme")</title>
>       <location>line 9: SECRET = os.environ.get("SESSION_SECRET", "changeme")</location>
>       <remediation>Remove the default; fail closed when SESSION_SECRET is unset.</remediation>
>     </finding>
>     <finding id="4" severity="High" cvss="7.5" cwe="CWE-209">
>       <title>Sensitive information disclosure on the error path</title>
>       <location>lines 33-35: returns exception text and dict(environ)</location>
>       <remediation>Return a generic 500; log server-side only; never serialize environ.</remediation>
>     </finding>
>     <finding id="5" severity="Medium" cvss="6.5" cwe="CWE-290">
>       <title>Trust decision based on spoofable X-Forwarded-For header</title>
>       <location>lines 18-22: client_ip from HTTP_X_FORWARDED_FOR</location>
>       <remediation>Use REMOTE_ADDR / trusted-proxy XFF parsing with real CIDR checks.</remediation>
>     </finding>
>     <finding id="6" severity="Medium" cvss="5.9" cwe="CWE-208">
>       <title>Non-constant-time signature comparison (timing side channel)</title>
>       <location>line 29: if sig == expected</location>
>       <remediation>Compare with hmac.compare_digest(sig, expected).</remediation>
>     </finding>
>     <finding id="7" severity="Low" cvss="3.7" cwe="CWE-565">
>       <title>No session expiry/binding; reliance on cookie alone</title>
>       <location>lines 24-37, 49-53</location>
>       <remediation>Add signed expiry + rotation; set HttpOnly/Secure/SameSite.</remediation>
>     </finding>
>   </findings>
> </security_audit>
> ```

---

## Reference (Claude / deterministic parse)

`COUNT=7`. All 7 findings, each with non-null severity, cwe, location, remediation.
Severity vector: Critical, High, High, High, Medium, Medium, Low. CWE vector:
502, 328, 798, 209, 290, 208, 565.

## Score sheet — fill in after pasting

| Consumer | COUNT | All 7 severities match? | All 7 CWEs match? | Verdict |
|----------|------:|-------------------------|-------------------|---------|
| Claude (reference) | 7 | yes | yes | PASS |
| Kimi (kimi.ai) | ? | ? | ? | ? |
| GPT (chatgpt) | ? | ? | ? | ? |

If both non-Claude consumers hit COUNT=7 with matching severities/CWEs, the
interoperability claim is proven and the benchmark suite can be frozen — move to
Phase II (already built: `iceni discover`).
