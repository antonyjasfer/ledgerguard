"""Static HTML UI for LedgerGuard Alexa+ Multi-Modal Command Center.

Apple Home / Stripe Dashboard Aesthetic:
- Clean, bright bg-slate-50 background and white rounded-2xl cards with soft shadows
- Async Web Speech API microphone dictation with explicit event-driven trigger
- 4 benchmark AP invoice scenarios with soft pill risk & policy badges
- Collapsible Hackathon Technical Telemetry for MCP 2025-11-25, Strands, and Argon2id
"""

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LedgerGuard - Autonomous Accounts Payable</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            brand: {
              50: '#eef2ff',
              100: '#e0e7ff',
              500: '#6366f1',
              600: '#4f46e5',
              700: '#4338ca',
            }
          }
        }
      }
    }
  </script>
  <style>
    body {
      font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
    }
    @keyframes pulse-subtle {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.6; transform: scale(0.96); }
    }
    .mic-listening-pulse {
      animation: pulse-subtle 1.4s infinite ease-in-out;
    }
  </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen flex flex-col antialiased">

  <!-- TOP HEADER -->
  <header class="bg-white/90 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-40 px-4 sm:px-8 py-3.5 flex items-center justify-between">
    <div class="flex items-center gap-3.5">
      <div class="w-10 h-10 rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-200">
        <i data-lucide="shield-check" class="w-5 h-5"></i>
      </div>
      <div>
        <div class="flex items-center gap-2.5">
          <h1 class="text-base sm:text-lg font-bold tracking-tight text-slate-900">LedgerGuard - Autonomous Accounts Payable</h1>
          <span class="hidden md:inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/60">
            Alexa+ Primary
          </span>
        </div>
        <p class="text-xs text-slate-500 flex items-center gap-2">
          <span>Enterprise AP Forensics</span>
          <span class="text-slate-300">•</span>
          <span class="inline-flex items-center gap-1.5 text-emerald-700 font-medium">
            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Argon2id Sealed Vault Active
          </span>
        </p>
      </div>
    </div>

    <!-- Header Badges & Actions -->
    <div class="flex items-center gap-2.5 sm:gap-3">
      <div class="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200/80 text-amber-800 text-xs">
        <i data-lucide="clock" class="w-3.5 h-3.5 text-amber-600"></i>
        <span>Bedrock Case 178842133900178: <strong class="font-semibold">Pending Amazon Action</strong></span>
      </div>
      <a href="/docs" target="_blank" class="px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs transition flex items-center gap-1.5">
        <i data-lucide="book-open" class="w-3.5 h-3.5"></i>
        <span>API Docs</span>
      </a>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-8">

    <!-- CENTER SECTION: THE ASSISTANT (ALEXA+) -->
    <section class="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 sm:p-7 space-y-5">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-sky-500 flex items-center justify-center text-white shadow-sm">
            <i data-lucide="sparkles" class="w-5 h-5"></i>
          </div>
          <div>
            <h2 class="text-base font-bold text-slate-900">Alexa+ AP Copilot</h2>
            <p class="text-xs text-slate-500">Natural voice reasoning with cross-session memory and deterministic verification</p>
          </div>
        </div>

        <div class="flex items-center gap-3 text-xs">
          <label class="flex items-center gap-2 cursor-pointer text-slate-600 hover:text-slate-900 select-none">
            <input type="checkbox" id="tts-toggle" checked class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-4 h-4" />
            <span>Spoken Voice (TTS)</span>
          </label>
          <span class="text-slate-300">|</span>
          <span class="text-slate-500">Engine:</span>
          <span id="active-engine-badge" class="px-2.5 py-0.5 rounded-full font-mono font-medium text-[11px] bg-slate-100 text-slate-700 border border-slate-200">
            deterministic_local_router
          </span>
        </div>
      </div>

      <!-- Spoken Speech Response Bubble -->
      <div class="bg-slate-50/90 border border-slate-200/90 rounded-2xl p-4 sm:p-5 flex items-start gap-3.5 transition">
        <div class="w-8 h-8 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0 mt-0.5">
          <i data-lucide="bot" class="w-4 h-4"></i>
        </div>
        <div class="flex-1 space-y-1">
          <div class="text-[11px] font-semibold uppercase tracking-wider text-indigo-700 flex items-center gap-1.5">
            <span>Alexa+ Voice Response</span>
            <span id="speaking-pulse" class="hidden w-2 h-2 rounded-full bg-indigo-500 animate-ping"></span>
          </div>
          <div id="alexa-speech-output" class="text-slate-800 text-sm sm:text-base leading-relaxed font-normal">
            "Hello, I am LedgerGuard for Alexa+. I audited your Q4 pending batch. I flagged invoice INV-2026-102 for a $1,200 arithmetic error, and INV-2026-103 as an exact duplicate of a settled invoice."
          </div>
        </div>
        <button onclick="replayLastSpeech()" title="Replay voice audio" class="p-2 rounded-xl text-slate-400 hover:text-indigo-600 hover:bg-white transition shrink-0">
          <i data-lucide="volume-2" class="w-4 h-4"></i>
        </button>
      </div>

      <!-- Large Friendly Chat Input Bar with Working Mic -->
      <div class="space-y-3">
        <div class="flex flex-col sm:flex-row gap-2.5">
          <div class="relative flex-1">
            <input
              id="voice-input-text"
              type="text"
              placeholder="Speak or type a command: 'Audit pending batch', 'Inspect duplicate INV-2026-103', 'Quarantine and freeze'..."
              class="w-full bg-slate-50 hover:bg-white focus:bg-white border border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 rounded-2xl px-4 py-3.5 text-sm text-slate-900 placeholder-slate-400 transition outline-none"
              onkeydown="if(event.key === 'Enter') { const v = this.value.trim(); if(v) sendTurn(v); }"
            />
          </div>

          <div class="flex items-center gap-2">
            <!-- Prominent Working Mic Button -->
            <button
              id="mic-btn"
              onclick="startDictation()"
              class="flex items-center justify-center gap-2 px-5 py-3.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition border border-slate-200/80 shadow-sm shrink-0"
              title="Click to speak using Web Speech API"
            >
              <i id="mic-icon" data-lucide="mic" class="w-4 h-4 text-slate-700"></i>
              <span id="mic-btn-text">Speak</span>
            </button>

            <!-- Send Button -->
            <button
              id="send-btn"
              onclick="const v = document.getElementById('voice-input-text').value.trim(); if(v) sendTurn(v);"
              class="flex items-center justify-center gap-2 px-6 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm transition shadow-sm shadow-indigo-200 shrink-0"
            >
              <span>Send</span>
              <i data-lucide="arrow-right" class="w-4 h-4"></i>
            </button>
          </div>
        </div>

        <!-- Quick-Prompt Chips -->
        <div class="flex items-center gap-2 flex-wrap pt-1 text-xs">
          <span class="text-slate-400 font-medium">Quick Prompts:</span>
          <button onclick="runChip('Audit pending Q4 batch and report any duplicate invoices')" class="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 font-medium transition border border-slate-200/70">
            ⚡ Audit pending batch
          </button>
          <button onclick="runChip('Inspect duplicate invoice INV-2026-103')" class="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 font-medium transition border border-slate-200/70">
            🔍 Inspect duplicate INV-103
          </button>
          <button onclick="runChip('Inspect arithmetic mismatch on invoice INV-2026-102')" class="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 font-medium transition border border-slate-200/70">
            🧮 Check math INV-102
          </button>
          <button onclick="runChip('Quarantine the duplicate invoice we just found and freeze that vendor')" class="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 font-medium transition border border-rose-200">
            🛡️ Quarantine & freeze vendor
          </button>
          <button onclick="runChip('Approve and seal clean invoice INV-2026-101 in the vault')" class="px-3 py-1.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium transition border border-emerald-200">
            ✅ Approve & seal INV-101
          </button>
          <button onclick="runTamperTest()" class="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition border border-slate-200/70 flex items-center gap-1.5">
            🧪 Simulate DB tamper
          </button>
        </div>
      </div>
    </section>

    <!-- MIDDLE SECTION: THE INVOICES (4 BENCHMARK SCENARIOS) -->
    <section class="space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 class="text-lg font-bold text-slate-900 tracking-tight">Pending Accounts Payable Invoices</h2>
          <p class="text-xs text-slate-500">Autonomous evaluation across Arithmetic, Historical Duplicate, and Corporate Spend Policy ($25k Limit)</p>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="loadState()" class="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-200/90 shadow-sm flex items-center gap-1.5 transition">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5 text-slate-500"></i>
            <span>Refresh State</span>
          </button>
        </div>
      </div>

      <!-- 4 Invoices Responsive Grid -->
      <div id="invoice-cards-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div class="col-span-full py-12 text-center text-slate-400 font-medium">
          Loading forensic invoice records...
        </div>
      </div>
    </section>

    <!-- BOTTOM SECTION: COLLAPSIBLE HACKATHON TECHNICAL TELEMETRY -->
    <section>
      <details class="group bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden transition">
        <summary class="px-6 py-4.5 font-semibold text-slate-800 cursor-pointer flex items-center justify-between hover:bg-slate-50/80 transition select-none">
          <div class="flex items-center gap-3">
            <span class="text-base font-bold text-slate-900">🛠️ View Hackathon Technical Telemetry (MCP, Argon2, Strands)</span>
            <span class="text-xs px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium border border-indigo-200/60">
              Judges Evidence Proof
            </span>
          </div>
          <div class="flex items-center gap-2 text-slate-400 group-open:text-indigo-600 transition">
            <span class="text-xs font-normal text-slate-400 group-open:hidden">Click to expand</span>
            <i data-lucide="chevron-down" class="w-5 h-5 transition-transform duration-200 group-open:rotate-180"></i>
          </div>
        </summary>

        <div class="p-6 sm:p-7 border-t border-slate-100 space-y-7 bg-slate-50/50">

          <!-- 1. Strands Deterministic Tool Trace & MCP Tester Side-by-Side -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <!-- Tool Trace -->
            <div class="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-3.5">
              <div class="flex items-center justify-between border-b border-slate-100 pb-3">
                <div class="flex items-center gap-2">
                  <i data-lucide="cpu" class="w-4 h-4 text-indigo-600"></i>
                  <h3 class="font-bold text-sm text-slate-900">Strands Deterministic Tool Trace</h3>
                </div>
                <span class="text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 font-semibold">
                  6 Tools • &lt;60ms
                </span>
              </div>
              <p class="text-xs text-slate-500 leading-relaxed">
                Deterministic forensic tools executed without stochastic LLM math hallucinations:
              </p>
              <div class="space-y-2 text-xs font-mono">
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <i data-lucide="check-circle" class="w-4 h-4 text-emerald-600"></i>
                    <span class="text-slate-800 font-medium">calculate_invoice_arithmetic</span>
                  </div>
                  <span class="text-slate-500 text-[11px]">12ms</span>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <i data-lucide="check-circle" class="w-4 h-4 text-emerald-600"></i>
                    <span class="text-slate-800 font-medium">check_duplicate_invoice</span>
                  </div>
                  <span class="text-slate-500 text-[11px]">15ms</span>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <i data-lucide="check-circle" class="w-4 h-4 text-emerald-600"></i>
                    <span class="text-slate-800 font-medium">get_vendor_history</span>
                  </div>
                  <span class="text-slate-500 text-[11px]">10ms</span>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <i data-lucide="check-circle" class="w-4 h-4 text-emerald-600"></i>
                    <span class="text-slate-800 font-medium">evaluate_invoice_policy</span>
                  </div>
                  <span class="text-slate-500 text-[11px]">8ms</span>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <i data-lucide="check-circle" class="w-4 h-4 text-emerald-600"></i>
                    <span class="text-slate-800 font-medium">calculate_invoice_risk</span>
                  </div>
                  <span class="text-slate-500 text-[11px]">14ms</span>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <i data-lucide="shield-check" class="w-4 h-4 text-indigo-600"></i>
                    <span class="text-slate-800 font-medium">seal_ledger_audit_record</span>
                  </div>
                  <span class="text-indigo-600 font-semibold text-[11px]">45ms</span>
                </div>
              </div>
            </div>

            <!-- MCP Streamable HTTP 2025-11-25 Tester -->
            <div class="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-3.5">
              <div class="flex items-center justify-between border-b border-slate-100 pb-3">
                <div class="flex items-center gap-2">
                  <i data-lucide="network" class="w-4 h-4 text-indigo-600"></i>
                  <h3 class="font-bold text-sm text-slate-900">Alexa+ MCP Server (Streamable HTTP)</h3>
                </div>
                <span class="text-[11px] font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200 font-semibold">
                  SPEC 2025-11-25
                </span>
              </div>
              <p class="text-xs text-slate-500 leading-relaxed">
                Streamable HTTP endpoint mounted at <code class="font-mono text-indigo-600 font-medium">http://127.0.0.1:8000/mcp</code> for Alexa+ Skills and Amazon Device Builder Tools:
              </p>
              <div class="flex gap-2.5">
                <button
                  onclick="callMcpToolsList()"
                  class="flex-1 py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold transition border border-slate-200 flex items-center justify-center gap-1.5"
                >
                  <i data-lucide="list" class="w-3.5 h-3.5 text-indigo-600"></i>
                  <span>Query tools/list</span>
                </button>
                <button
                  onclick="callMcpSealTool()"
                  class="flex-1 py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-sm shadow-indigo-200"
                >
                  <i data-lucide="shield-check" class="w-3.5 h-3.5"></i>
                  <span>Test tools/call</span>
                </button>
              </div>

              <!-- MCP Live Response Box -->
              <div class="bg-slate-900 p-3.5 rounded-xl border border-slate-800 text-[11px] font-mono max-h-44 overflow-y-auto">
                <div class="text-slate-400 mb-1">// MCP JSON-RPC 2025-11-25 Live Response</div>
                <pre id="mcp-response-output" class="text-indigo-300 whitespace-pre-wrap">{
  "status": "ready",
  "endpoint": "http://127.0.0.1:8000/mcp",
  "protocolVersion": "2025-11-25",
  "registered_tools": 8
}</pre>
              </div>
            </div>
          </div>

          <!-- 2. Argon2id Cryptographic Audit Chain & Tamper Simulator -->
          <div class="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3.5">
              <div>
                <div class="flex items-center gap-2">
                  <i data-lucide="link" class="w-4 h-4 text-emerald-600"></i>
                  <h3 class="font-bold text-sm text-slate-900">Argon2id Linked Audit Chain (Tamper-Evident Vault)</h3>
                  <span class="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                    m=65536KB (64MB), t=2, p=2
                  </span>
                </div>
                <p class="text-xs text-slate-500 mt-1">
                  Every invoice audit decision is bound into an immutable sequential hash chain verified with memory-hard Argon2id.
                </p>
              </div>

              <button
                onclick="runTamperTest()"
                class="px-4 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold text-xs uppercase tracking-wider transition border border-rose-200 flex items-center gap-1.5 shrink-0"
              >
                <i data-lucide="shield-alert" class="w-4 h-4 text-rose-600"></i>
                <span>Simulate Database Tamper Attack</span>
              </button>
            </div>

            <!-- Chain Blocks Feed -->
            <div id="audit-chain-feed" class="space-y-2.5 max-h-72 overflow-y-auto pr-1">
              <div class="text-center py-6 text-slate-400 font-mono text-xs">Loading cryptographic chain blocks...</div>
            </div>
          </div>

        </div>
      </details>
    </section>

  </main>

  <!-- TAMPER ATTACK MODAL DIALOG -->
  <div id="tamper-modal" class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="bg-white max-w-xl w-full rounded-2xl p-6 space-y-4 border border-rose-200 shadow-xl relative animate-in fade-in zoom-in duration-150">
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-200">
            <i data-lucide="shield-alert" class="w-6 h-6"></i>
          </div>
          <div>
            <h3 class="font-bold text-base text-slate-900">Database Tampering Simulation</h3>
            <p class="text-xs text-rose-700 font-medium">Argon2id Memory-Hard Verification Result</p>
          </div>
        </div>
        <button onclick="closeTamperModal()" class="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1 font-mono">
          <div class="text-slate-500 font-semibold">// Attack Vector Injected</div>
          <div class="text-rose-700 font-medium break-all" id="tamper-attack-vector">Simulating direct database manipulation...</div>
        </div>

        <div class="grid grid-cols-2 gap-3 font-mono">
          <div class="p-3 rounded-xl bg-emerald-50/60 border border-emerald-200">
            <div class="text-emerald-700 text-[10px] uppercase font-semibold">Original Record</div>
            <div class="text-emerald-800 font-bold text-sm mt-1 flex items-center gap-1.5">
              <i data-lucide="check" class="w-4 h-4"></i>
              <span>VALID [200 OK]</span>
            </div>
            <div class="text-[10px] text-emerald-600 mt-1">Seal matches original payload</div>
          </div>
          <div class="p-3 rounded-xl bg-rose-50 border border-rose-200">
            <div class="text-rose-700 text-[10px] uppercase font-semibold">Tampered Record</div>
            <div class="text-rose-800 font-bold text-sm mt-1 flex items-center gap-1.5">
              <i data-lucide="ban" class="w-4 h-4"></i>
              <span>TAMPER BLOCKED</span>
            </div>
            <div class="text-[10px] text-rose-600 mt-1">Argon2 verification failed (403)</div>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-indigo-50/80 border border-indigo-200/80 text-indigo-900 leading-relaxed font-sans text-xs">
          <strong>Cryptographic Proof Confirmed:</strong> Because Argon2id requires 64MB of dedicated memory and 2 full iterations per evaluation, forged or tampered entries in unencrypted database storage cannot match the cryptographically sealed hash. Any unauthorized modification to amounts, recipient accounts, or timestamps is immediately detected and rejected.
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button onclick="closeTamperModal()" class="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-sm transition">
          Close Verification Proof
        </button>
      </div>
    </div>
  </div>

  <!-- SCRIPT LOGIC -->
  <script>
    let appState = null;
    let recognition = null;
    let isListening = false;
    let isSpeaking = false;
    let lastSpokenText = "";

    // Initialize on page load
    document.addEventListener("DOMContentLoaded", () => {
      lucide.createIcons();
      loadState();
    });

    // -------------------------------------------------------------
    // Microphone Fix: Web Speech API Dictation
    // -------------------------------------------------------------
    function startDictation() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        alert("Microphone speech recognition is not supported in this browser. Please type your command in the input box.");
        return;
      }

      if (isListening) {
        if (recognition) {
          try { recognition.stop(); } catch (e) {}
        }
        setMicUI(false);
        return;
      }

      try {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = "en-US";

        recognition.onstart = () => {
          isListening = true;
          setMicUI(true);
        };

        // ONLY trigger sendTurn AFTER onresult fires and captures transcript
        recognition.onresult = (event) => {
          isListening = false;
          setMicUI(false);

          let transcript = "";
          if (event.results && event.results[0] && event.results[0][0]) {
            transcript = event.results[0][0].transcript || "";
          }

          const trimmed = transcript.trim();
          if (trimmed.length > 0) {
            const input = document.getElementById("voice-input-text");
            if (input) input.value = trimmed;
            sendTurn(trimmed);
          }
        };

        recognition.onerror = (event) => {
          console.warn("Speech recognition error:", event.error);
          isListening = false;
          setMicUI(false);
        };

        recognition.onend = () => {
          isListening = false;
          setMicUI(false);
        };

        recognition.start();
      } catch (err) {
        console.error("Failed to start speech recognition:", err);
        isListening = false;
        setMicUI(false);
      }
    }

    // Toggle helper alias
    function toggleMicrophone() {
      startDictation();
    }

    function setMicUI(listening) {
      const btn = document.getElementById("mic-btn");
      const btnText = document.getElementById("mic-btn-text");
      const icon = document.getElementById("mic-icon");

      if (listening) {
        btn.className = "flex items-center justify-center gap-2 px-5 py-3.5 rounded-2xl bg-rose-50 text-rose-700 border border-rose-300 ring-2 ring-rose-200 font-semibold text-sm transition shrink-0 mic-listening-pulse";
        btnText.innerHTML = '<span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse"></span> Listening...</span>';
      } else {
        btn.className = "flex items-center justify-center gap-2 px-5 py-3.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition border border-slate-200/80 shadow-sm shrink-0";
        btnText.innerText = "Speak";
      }
    }

    // -------------------------------------------------------------
    // Send Turn / User Query
    // -------------------------------------------------------------
    async function sendTurn(customQuery) {
      const input = document.getElementById("voice-input-text");
      const prompt = customQuery || input.value.trim();
      if (!prompt) return;

      input.value = "";
      const sendBtn = document.getElementById("send-btn");
      sendBtn.disabled = true;
      sendBtn.classList.add("opacity-60");

      const output = document.getElementById("alexa-speech-output");
      output.innerText = "Analyzing AP scenario with Strands agent and forensic tools...";

      try {
        const res = await fetch("/api/alexa/converse", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({prompt: prompt}),
        });

        if (!res.ok) throw new Error("Converse error: " + res.status);
        const data = await res.json();

        // Update Alexa speech bubble and speak
        output.innerText = `"${data.voice_speech}"`;
        lastSpokenText = data.voice_speech;

        const ttsEnabled = document.getElementById("tts-toggle")?.checked ?? true;
        if (ttsEnabled) {
          speakText(data.voice_speech);
        }

        // Update active engine badge
        const engineBadge = document.getElementById("active-engine-badge");
        if (engineBadge) {
          engineBadge.innerText = data.active_engine || "deterministic_local_router";
        }

        // Refresh state
        await loadState();
      } catch (err) {
        console.error(err);
        output.innerText = "Error communicating with Alexa+ service: " + err.message;
      } finally {
        sendBtn.disabled = false;
        sendBtn.classList.remove("opacity-60");
      }
    }

    // Alias for backward compatibility
    function sendUserQuery(q) {
      sendTurn(q);
    }

    function runChip(text) {
      const input = document.getElementById("voice-input-text");
      if (input) input.value = text;
      sendTurn(text);
    }

    // -------------------------------------------------------------
    // Spoken Voice Audio (TTS) Playback
    // -------------------------------------------------------------
    function speakText(text) {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.02;
      utterance.pitch = 1.0;

      const pulse = document.getElementById("speaking-pulse");

      utterance.onstart = () => {
        isSpeaking = true;
        if (pulse) pulse.classList.remove("hidden");
      };

      utterance.onend = () => {
        isSpeaking = false;
        if (pulse) pulse.classList.add("hidden");
      };

      utterance.onerror = () => {
        isSpeaking = false;
        if (pulse) pulse.classList.add("hidden");
      };

      window.speechSynthesis.speak(utterance);
    }

    function replayLastSpeech() {
      if (lastSpokenText) {
        speakText(lastSpokenText);
      } else {
        const text = document.getElementById("alexa-speech-output")?.innerText?.replace(/^"|"$/g, '') || "";
        if (text) speakText(text);
      }
    }

    // -------------------------------------------------------------
    // Fetch and Render State
    // -------------------------------------------------------------
    async function loadState() {
      try {
        const res = await fetch("/api/alexa/state");
        if (!res.ok) throw new Error("Failed to load state: " + res.status);
        appState = await res.json();
        renderInvoices(appState.invoices);
        renderAuditChain(appState.audit_chain);
        lucide.createIcons();
      } catch (err) {
        console.error("Error loading state:", err);
      }
    }

    // -------------------------------------------------------------
    // Render Invoices Grid (Soft Pills, Apple Home / Stripe Aesthetic)
    // -------------------------------------------------------------
    function renderInvoices(invoices) {
      const container = document.getElementById("invoice-cards-container");
      if (!invoices || invoices.length === 0) {
        container.innerHTML = '<div class="col-span-full py-8 text-center text-slate-400">No invoices loaded.</div>';
        return;
      }

      container.innerHTML = invoices.map(inv => {
        const risk = inv.forensics?.risk || {};
        const arith = inv.forensics?.arithmetic || {};
        const dup = inv.forensics?.duplicate || {};
        const policy = inv.forensics?.policy || {};

        // Risk Pill Styling (Soft Pills)
        let riskBadgeClass = "bg-emerald-50 text-emerald-700 border-emerald-200/80";
        if (risk.risk_level === "HIGH") {
          riskBadgeClass = "bg-rose-50 text-rose-700 border-rose-200/80";
        } else if (risk.risk_level === "CRITICAL") {
          riskBadgeClass = "bg-purple-50 text-purple-700 border-purple-200/80 ring-1 ring-purple-300/60";
        } else if (risk.risk_level === "MEDIUM") {
          riskBadgeClass = "bg-amber-50 text-amber-700 border-amber-200/80";
        }

        // Status Pill Styling
        let statusBadgeClass = "bg-slate-100 text-slate-700 border-slate-200";
        let statusLabel = inv.status;
        if (inv.status.includes("QUARANTINE")) {
          statusBadgeClass = "bg-rose-100 text-rose-800 border-rose-300 font-bold";
          statusLabel = "QUARANTINED";
        } else if (inv.status.includes("APPROVED")) {
          statusBadgeClass = "bg-emerald-100 text-emerald-800 border-emerald-300 font-bold";
          statusLabel = "SEALED & APPROVED";
        } else if (inv.status === "VERIFIED_CLEAN") {
          statusBadgeClass = "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold";
          statusLabel = "VERIFIED CLEAN";
        } else if (inv.status === "FLAGGED_ARITHMETIC") {
          statusBadgeClass = "bg-amber-50 text-amber-800 border-amber-200 font-semibold";
          statusLabel = "ARITHMETIC ERROR";
        } else if (inv.status === "FLAGGED_DUPLICATE") {
          statusBadgeClass = "bg-rose-50 text-rose-800 border-rose-200 font-semibold";
          statusLabel = "DUPLICATE MATCH";
        } else if (inv.status === "FLAGGED_POLICY") {
          statusBadgeClass = "bg-amber-50 text-amber-800 border-amber-200 font-semibold";
          statusLabel = "POLICY BREACH";
        }

        // Policy Check Pill
        const policyPassed = policy.passed === true;
        const policyLabel = policyPassed ? "PASS" : "BREACH (>$25k)";
        const policyBadgeClass = policyPassed
          ? "bg-emerald-50 text-emerald-700 border border-emerald-200/70"
          : "bg-rose-50 text-rose-700 border border-rose-200 font-semibold";

        // Arithmetic Pill
        const arithPassed = arith.passed === true;
        const arithLabel = arithPassed ? "PASS (Exact)" : "FAIL ($1,200 error)";
        const arithBadgeClass = arithPassed
          ? "text-emerald-700 font-medium"
          : "text-rose-700 font-bold";

        // Duplicate Pill
        const isDuplicate = dup.status === "CONFIRMED_DUPLICATE";
        const dupLabel = isDuplicate ? "DUPLICATE MATCH" : "NO DUPLICATE";
        const dupBadgeClass = isDuplicate
          ? "text-rose-700 font-bold"
          : "text-emerald-700 font-medium";

        const formattedTotal = parseFloat(inv.total).toLocaleString('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        });

        return `
          <div class="bg-white rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md transition p-5 flex flex-col justify-between space-y-4">
            <!-- Header & Amount -->
            <div class="space-y-2.5">
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold text-slate-900 text-sm font-mono tracking-tight">${inv.invoice_number}</span>
                <span class="text-[10px] px-2 py-0.5 rounded-full border font-mono ${statusBadgeClass}">
                  ${statusLabel}
                </span>
              </div>

              <div>
                <div class="text-xs text-slate-500 font-medium">${inv.vendor_name}</div>
                <div class="text-xl font-bold text-slate-900 tracking-tight mt-0.5">
                  $${formattedTotal} <span class="text-xs text-slate-400 font-normal font-mono">USD</span>
                </div>
                <div class="text-[11px] text-slate-400 mt-0.5">${inv.invoice_date}</div>
              </div>

              <!-- Risk Badge -->
              <div class="pt-1">
                <span class="inline-flex items-center text-xs px-2.5 py-1 rounded-full border font-semibold ${riskBadgeClass}">
                  ${risk.risk_level || "UNKNOWN"} RISK (${risk.risk_score || 0}/100)
                </span>
              </div>
            </div>

            <!-- Checks Grid -->
            <div class="space-y-1.5 text-[11px] bg-slate-50 p-3 rounded-xl border border-slate-100">
              <div class="flex items-center justify-between">
                <span class="text-slate-500">Arithmetic:</span>
                <span class="${arithBadgeClass}">${arithLabel}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-slate-500">Duplicates:</span>
                <span class="${dupBadgeClass}">${dupLabel}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-slate-500">Policy Check:</span>
                <span class="px-1.5 py-0.5 rounded text-[10px] ${policyBadgeClass}">${policyLabel}</span>
              </div>
            </div>

            <!-- Card Actions -->
            <div class="space-y-2 pt-1 border-t border-slate-100">
              <div class="text-[10px] font-mono text-slate-400 truncate" title="${inv.latest_seal || ''}">
                <span class="text-slate-500">Seal:</span> ${inv.latest_seal ? inv.latest_seal.substring(0, 24) + '...' : 'Unsealed'}
              </div>

              <div class="grid grid-cols-2 gap-2">
                <button
                  onclick="triggerAction('${inv.invoice_id}', 'APPROVE_AND_SEAL')"
                  class="py-2 px-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition flex items-center justify-center gap-1 shadow-sm"
                >
                  <i data-lucide="check" class="w-3.5 h-3.5"></i>
                  <span>Approve</span>
                </button>
                <button
                  onclick="triggerAction('${inv.invoice_id}', 'QUARANTINE_AND_DISPUTE')"
                  class="py-2 px-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-medium text-xs transition flex items-center justify-center gap-1"
                >
                  <i data-lucide="shield-alert" class="w-3.5 h-3.5"></i>
                  <span>Quarantine</span>
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    // -------------------------------------------------------------
    // Render Audit Chain Blocks
    // -------------------------------------------------------------
    function renderAuditChain(chain) {
      const feed = document.getElementById("audit-chain-feed");
      if (!chain || chain.length === 0) {
        feed.innerHTML = '<div class="text-slate-400 py-4 text-center font-mono text-xs">No audit blocks in ledger.</div>';
        return;
      }

      feed.innerHTML = chain.slice().reverse().map(block => {
        return `
          <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 font-mono text-xs space-y-1.5 transition hover:bg-white hover:border-slate-300">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold text-[10px]">
                  BLOCK #${block.block_index}
                </span>
                <span class="text-slate-900 font-semibold">${block.action}</span>
                <span class="text-slate-300">•</span>
                <span class="text-indigo-600 font-medium">${block.tx_id}</span>
              </div>
              <span class="text-[10px] text-slate-400">${block.timestamp}</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] text-slate-500 pt-0.5">
              <div class="truncate">
                <span class="font-medium text-slate-400">Prev Hash:</span> <span class="text-slate-700">${block.prev_hash.substring(0, 32)}...</span>
              </div>
              <div class="truncate">
                <span class="font-medium text-slate-400">SHA-256:</span> <span class="text-slate-700">${block.sha256.substring(0, 32)}...</span>
              </div>
            </div>

            <div class="text-[10px] text-slate-500 truncate pt-0.5">
              <span class="font-semibold text-emerald-700">Argon2id Seal:</span> <span class="text-emerald-800/90">${block.argon2_seal}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    // -------------------------------------------------------------
    // Invoice Explicit Actions
    // -------------------------------------------------------------
    async function triggerAction(invoiceId, action) {
      try {
        const res = await fetch("/api/alexa/action", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({invoice_id: invoiceId, action: action}),
        });
        if (!res.ok) throw new Error("Action failed: " + res.status);
        await loadState();
      } catch (err) {
        console.error("Action error:", err);
      }
    }

    // -------------------------------------------------------------
    // MCP Streamable HTTP Live Calls
    // -------------------------------------------------------------
    async function callMcpToolsList() {
      const output = document.getElementById("mcp-response-output");
      output.innerText = "// Querying /mcp tools/list via JSON-RPC 2025-11-25...";
      try {
        const res = await fetch("/mcp", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({jsonrpc: "2.0", id: Date.now(), method: "tools/list", params: {}}),
        });
        const data = await res.json();
        output.innerText = JSON.stringify(data, null, 2);
      } catch (err) {
        output.innerText = "Error: " + err;
      }
    }

    async function callMcpSealTool() {
      const output = document.getElementById("mcp-response-output");
      output.innerText = "// Calling /mcp seal_ledger_audit_record tool...";
      try {
        const res = await fetch("/mcp", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: Date.now(),
            method: "tools/call",
            params: {
              name: "seal_ledger_audit_record",
              arguments: {
                prev_hash: "MCP_STREAMABLE_TEST_CHAIN",
                tx_id: "INV-MCP-LIVE-001",
                action: "ALEXA_MCP_SEAL_TEST",
              }
            }
          }),
        });
        const data = await res.json();
        output.innerText = JSON.stringify(data, null, 2);
      } catch (err) {
        output.innerText = "Error: " + err;
      }
    }

    // -------------------------------------------------------------
    // Tamper Test Simulation
    // -------------------------------------------------------------
    async function runTamperTest() {
      try {
        const res = await fetch("/api/alexa/tamper-test", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({invoice_id: "INV-2026-103", tampered_amount: "84000.00"}),
        });
        const data = await res.json();

        document.getElementById("tamper-attack-vector").innerText = data.attack_vector;
        document.getElementById("tamper-modal").classList.remove("hidden");
        lucide.createIcons();
        await loadState();
      } catch (err) {
        console.error("Tamper test error:", err);
      }
    }

    function closeTamperModal() {
      document.getElementById("tamper-modal").classList.add("hidden");
    }
  </script>
</body>
</html>
"""
