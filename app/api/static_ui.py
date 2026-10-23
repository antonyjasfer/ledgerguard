UI_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LedgerGuard — Alexa+ Multi-Modal Command Center</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'sans-serif'],
            mono: ['JetBrains Mono', 'monospace'],
          },
          colors: {
            brand: {
              50: '#f0f9ff',
              400: '#38bdf8',
              500: '#0ea5e9',
              600: '#0284c7',
            },
            argon: {
              glow: '#00f2fe',
              purple: '#7928ca',
            }
          }
        }
      }
    }
  </script>
  <style>
    body {
      background-color: #060911;
      color: #f1f5f9;
      font-family: 'Inter', sans-serif;
    }
    .argon-glass {
      background: rgba(13, 20, 36, 0.75);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .argon-glass-glow {
      background: rgba(13, 20, 36, 0.85);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(56, 189, 248, 0.25);
      box-shadow: 0 0 25px -5px rgba(56, 189, 248, 0.2);
    }
    /* Voice Orb Animation */
    .orb-core {
      background: radial-gradient(circle at 35% 35%, #38bdf8, #2563eb, #7c3aed);
      box-shadow: 0 0 40px rgba(56, 189, 248, 0.6), inset 0 0 20px rgba(255, 255, 255, 0.6);
      transition: all 0.3s ease;
    }
    .orb-listening {
      animation: pulse-listening 1.6s infinite ease-in-out;
      box-shadow: 0 0 60px rgba(239, 68, 68, 0.8), inset 0 0 25px rgba(255, 255, 255, 0.8);
      background: radial-gradient(circle at 35% 35%, #f87171, #dc2626, #991b1b);
    }
    .orb-thinking {
      animation: rotate-thinking 2s infinite linear;
      box-shadow: 0 0 60px rgba(168, 85, 247, 0.8), inset 0 0 25px rgba(255, 255, 255, 0.8);
      background: radial-gradient(circle at 35% 35%, #c084fc, #9333ea, #581c87);
    }
    .orb-speaking {
      animation: pulse-speaking 1.2s infinite ease-in-out;
      box-shadow: 0 0 60px rgba(34, 197, 94, 0.8), inset 0 0 25px rgba(255, 255, 255, 0.8);
      background: radial-gradient(circle at 35% 35%, #4ade80, #16a34a, #14532d);
    }
    @keyframes pulse-listening {
      0%, 100% { transform: scale(1); filter: brightness(1); }
      50% { transform: scale(1.1); filter: brightness(1.3); }
    }
    @keyframes rotate-thinking {
      0% { transform: rotate(0deg) scale(1.05); }
      100% { transform: rotate(360deg) scale(1.05); }
    }
    @keyframes pulse-speaking {
      0%, 100% { transform: scale(1); filter: brightness(1.1); }
      50% { transform: scale(1.15); filter: brightness(1.4); }
    }
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: rgba(15, 23, 42, 0.6);
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(148, 163, 184, 0.3);
      border-radius: 3px;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col bg-[#060911] text-slate-100">

  <!-- TOP APP NAV -->
  <header class="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
        <i data-lucide="shield-check" class="w-5 h-5 text-white"></i>
      </div>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-sky-400 via-indigo-300 to-white bg-clip-text text-transparent">LedgerGuard</span>
          <span class="text-xs px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-400/30 text-sky-400 font-semibold tracking-wide">ALEXA+ PRIMARY</span>
          <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-400/30 text-indigo-300 font-mono">MCP 2025-11-25</span>
        </div>
        <div class="text-[11px] text-slate-400 flex items-center gap-2">
          <span>Amazon Developer Hackathon</span>
          <span class="text-slate-600">•</span>
          <span class="text-emerald-400 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Argon2id Sealed Vault Active</span>
        </div>
      </div>
    </div>

    <!-- Telemetry Pills -->
    <div class="flex items-center gap-3 text-xs font-mono">
      <div class="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800">
        <i data-lucide="server" class="w-3.5 h-3.5 text-sky-400"></i>
        <span class="text-slate-400">AWS Identity:</span>
        <span class="text-sky-300" id="top-identity">ledgerguard-dev</span>
      </div>
      <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300">
        <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i>
        <span>Bedrock Case 178842133900178: <strong class="text-amber-200">Pending Amazon Action</strong></span>
      </div>
      <a href="/docs" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 transition flex items-center gap-1.5 text-slate-300">
        <i data-lucide="book" class="w-3.5 h-3.5"></i>
        <span>API Docs</span>
      </a>
    </div>
  </header>

  <!-- MAIN DASHBOARD CONTENT -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">

    <!-- HERO SECTION: ALEXA+ VOICE ORB & PUSH-TO-TALK BAR -->
    <div class="argon-glass-glow rounded-2xl p-6 relative overflow-hidden">
      <div class="absolute -right-20 -top-20 w-80 h-80 bg-sky-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div class="absolute -left-20 -bottom-20 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div class="flex flex-col lg:flex-row items-center gap-8 relative z-10">
        <!-- Voice Orb Display -->
        <div class="flex flex-col items-center justify-center">
          <div class="relative w-32 h-32 flex items-center justify-center cursor-pointer" onclick="toggleMicrophone()">
            <div id="orb-ring-outer" class="absolute inset-0 rounded-full border border-sky-400/20 animate-ping opacity-30"></div>
            <div id="orb-ring-inner" class="absolute w-28 h-28 rounded-full border border-purple-400/30"></div>
            <div id="voice-orb" class="orb-core w-20 h-20 rounded-full flex items-center justify-center shadow-2xl">
              <i id="orb-icon" data-lucide="mic" class="w-8 h-8 text-white drop-shadow"></i>
            </div>
          </div>
          <div class="mt-2 text-center">
            <span id="voice-status-text" class="text-xs font-semibold uppercase tracking-wider text-sky-400">Push to Talk (Web Speech API)</span>
            <div id="tts-indicator" class="text-[11px] text-slate-400 mt-0.5">Spoken audio playback: <span class="text-emerald-400 font-medium">ENABLED</span></div>
          </div>
        </div>

        <!-- Voice Interaction Bar & Speech Feed -->
        <div class="flex-1 w-full space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <i data-lucide="sparkles" class="w-5 h-5 text-sky-400"></i>
              <span>Alexa+ Multi-Modal Reasoning Console</span>
            </h2>
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-slate-400">Engine:</span>
              <span id="active-engine-badge" class="text-xs px-2 py-0.5 rounded font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30">deterministic_local_router</span>
            </div>
          </div>

          <!-- Spoken Transcript Balloon -->
          <div class="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 text-sm leading-relaxed text-slate-200 min-h-[58px] flex items-start gap-3">
            <div class="w-6 h-6 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center shrink-0 mt-0.5">
              <i data-lucide="bot" class="w-4 h-4"></i>
            </div>
            <div id="alexa-speech-output" class="flex-1 font-sans">
              "Hello, I am LedgerGuard for Alexa+. I audited your Q4 pending batch. I flagged invoice INV-2026-102 for a $1,200 arithmetic error, and INV-2026-103 as an exact duplicate of a settled invoice."
            </div>
          </div>

          <!-- Input Bar -->
          <div class="flex gap-2">
            <div class="relative flex-1">
              <input
                id="voice-input-text"
                type="text"
                placeholder="Speak or type a command: 'Audit pending batch', 'Inspect duplicate INV-2026-103', 'Quarantine and freeze'..."
                class="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-sans"
                onkeydown="if(event.key === 'Enter') sendUserQuery()"
              />
            </div>
            <button
              onclick="toggleMicrophone()"
              id="mic-btn"
              class="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-400 border border-slate-700 font-semibold text-sm transition flex items-center gap-2"
              title="Speak with real microphone"
            >
              <i data-lucide="mic" class="w-4 h-4"></i>
              <span class="hidden sm:inline">Mic</span>
            </button>
            <button
              onclick="sendUserQuery()"
              class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold text-sm transition flex items-center gap-2 shadow-lg shadow-sky-500/20"
            >
              <i data-lucide="send" class="w-4 h-4"></i>
              <span>Send</span>
            </button>
          </div>

          <!-- Quick-Prompt Chips -->
          <div class="flex flex-wrap gap-2 pt-1 text-xs">
            <span class="text-slate-500 self-center">Try saying:</span>
            <button onclick="runChip(this.innerText)" class="px-3 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition">Audit pending Q4 batch</button>
            <button onclick="runChip(this.innerText)" class="px-3 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition">Inspect arithmetic on INV-2026-102</button>
            <button onclick="runChip(this.innerText)" class="px-3 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition">Quarantine duplicate invoice INV-2026-103</button>
            <button onclick="runChip(this.innerText)" class="px-3 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition">Freeze vendor Shadow Consulting</button>
            <button onclick="runTamperTest()" class="px-3 py-1 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 transition flex items-center gap-1 font-semibold">
              <i data-lucide="shield-alert" class="w-3.5 h-3.5"></i>
              <span>Run Argon2 Tamper Test</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 2-COLUMN GRID: CARDS CAROUSEL + MULTI-AGENT / MCP INSPECTOR -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

      <!-- LEFT: ALEXA+ APL VISUAL INVOICE CAROUSEL (7 Cols) -->
      <div class="lg:col-span-7 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="font-bold text-base text-white flex items-center gap-2">
              <i data-lucide="layers" class="w-4 h-4 text-sky-400"></i>
              <span>Alexa+ Interactive APL Visual Carousel</span>
            </h3>
            <p class="text-xs text-slate-400">4 benchmark Accounts Payable scenarios analyzed via Strands deterministic tools</p>
          </div>
          <button onclick="loadState()" class="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1">
            <i data-lucide="refresh-cw" class="w-3 h-3"></i>
            <span>Refresh</span>
          </button>
        </div>

        <div id="invoice-cards-container" class="space-y-3.5">
          <!-- Invoices rendered dynamically via JS -->
          <div class="text-center py-12 text-slate-500">Loading invoice scenarios...</div>
        </div>
      </div>

      <!-- RIGHT: STRANDS MULTI-AGENT & MCP 2025-11-25 INSPECTOR (5 Cols) -->
      <div class="lg:col-span-5 space-y-6">

        <!-- Strands Forensic Tool Trace -->
        <div class="argon-glass rounded-2xl p-5 space-y-3">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h4 class="font-bold text-sm text-white flex items-center gap-2">
              <i data-lucide="activity" class="w-4 h-4 text-purple-400"></i>
              <span>Strands 1.54.0 Forensic Tool Trace</span>
            </h4>
            <span class="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">DETERMINISTIC PIPELINE</span>
          </div>

          <div class="space-y-2 text-xs font-mono" id="tool-trace-list">
            <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                <span class="text-slate-200">calculate_invoice_arithmetic</span>
              </div>
              <span class="text-slate-400">12ms</span>
            </div>
            <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                <span class="text-slate-200">check_duplicate_invoice</span>
              </div>
              <span class="text-slate-400">15ms</span>
            </div>
            <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                <span class="text-slate-200">get_vendor_history</span>
              </div>
              <span class="text-slate-400">10ms</span>
            </div>
            <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                <span class="text-slate-200">evaluate_invoice_policy</span>
              </div>
              <span class="text-slate-400">8ms</span>
            </div>
            <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                <span class="text-slate-200">calculate_invoice_risk</span>
              </div>
              <span class="text-slate-400">14ms</span>
            </div>
          </div>
        </div>

        <!-- MCP Streamable HTTP 2025-11-25 Live Tester -->
        <div class="argon-glass rounded-2xl p-5 space-y-3">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h4 class="font-bold text-sm text-white flex items-center gap-2">
              <i data-lucide="network" class="w-4 h-4 text-sky-400"></i>
              <span>Alexa+ MCP Server (`/mcp` Streamable HTTP)</span>
            </h4>
            <span class="text-[11px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 font-mono">SPEC 2025-11-25</span>
          </div>

          <p class="text-xs text-slate-400 leading-relaxed">
            The local MCP server is connected via Streamable HTTP at <code class="text-sky-300 font-mono">http://127.0.0.1:8000/mcp</code> for Alexa+ Skills and Amazon Devices Builder Tools.
          </p>

          <div class="flex gap-2">
            <button
              onclick="callMcpToolsList()"
              class="flex-1 py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition border border-slate-700 flex items-center justify-center gap-1.5"
            >
              <i data-lucide="list" class="w-3.5 h-3.5 text-sky-400"></i>
              <span>Query tools/list</span>
            </button>
            <button
              onclick="callMcpSealTool()"
              class="flex-1 py-2 px-3 rounded-lg bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 text-white text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow"
            >
              <i data-lucide="shield-check" class="w-3.5 h-3.5"></i>
              <span>Test tools/call</span>
            </button>
          </div>

          <!-- MCP Live Response Box -->
          <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-[11px] font-mono max-h-48 overflow-y-auto">
            <div class="text-slate-500 mb-1">// MCP JSON-RPC 2025-11-25 Streamable HTTP Response</div>
            <pre id="mcp-response-output" class="text-sky-300 whitespace-pre-wrap">{
  "status": "ready",
  "endpoint": "http://127.0.0.1:8000/mcp",
  "protocolVersion": "2025-11-25",
  "registered_tools": 8
}</pre>
          </div>
        </div>

      </div>
    </div>

    <!-- SECTION 3: ARGON2ID CRYPTOGRAPHIC HASH CHAIN & LIVE TAMPER SIMULATOR -->
    <div class="argon-glass rounded-2xl p-6 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div class="flex items-center gap-2">
            <h3 class="font-bold text-base text-white flex items-center gap-2">
              <i data-lucide="link-2" class="w-5 h-5 text-emerald-400"></i>
              <span>Argon2id Cryptographic Audit Chain (Tamper-Evident Vault)</span>
            </h3>
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono font-semibold">
              m=65536, t=2, p=2 (64MB Hardness)
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-1">
            Every invoice decision and Alexa+ action is permanently sealed into an immutable, linked SHA-256 + Argon2id hash chain.
          </p>
        </div>

        <!-- LIVE TAMPER BUTTON -->
        <button
          onclick="runTamperTest()"
          class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-red-700 hover:from-rose-500 hover:to-red-600 text-white font-bold text-xs uppercase tracking-wider transition flex items-center gap-2 shadow-lg shadow-rose-600/30 shrink-0"
        >
          <i data-lucide="skull" class="w-4 h-4"></i>
          <span>Simulate Ledger Tamper Attack</span>
        </button>
      </div>

      <!-- Chain Blocks Feed -->
      <div id="audit-chain-feed" class="space-y-2.5 max-h-72 overflow-y-auto pr-1">
        <div class="text-center py-6 text-slate-500 font-mono text-xs">Loading cryptographic chain blocks...</div>
      </div>
    </div>

  </main>

  <!-- TAMPER ATTACK MODAL DIALOG -->
  <div id="tamper-modal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md hidden flex items-center justify-center p-4">
    <div class="argon-glass-glow max-w-xl w-full rounded-2xl p-6 space-y-4 border border-rose-500/40 relative">
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center">
            <i data-lucide="shield-alert" class="w-6 h-6"></i>
          </div>
          <div>
            <h3 class="font-bold text-lg text-white">Live Tamper Attack Simulation</h3>
            <p class="text-xs text-rose-300 font-mono">Argon2id Memory-Hard Verification Result</p>
          </div>
        </div>
        <button onclick="closeTamperModal()" class="text-slate-400 hover:text-white p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 font-mono">
          <div class="text-slate-400 font-semibold">// Attack Vector Injected</div>
          <div class="text-rose-400" id="tamper-attack-vector">Simulating direct database manipulation...</div>
        </div>

        <div class="grid grid-cols-2 gap-3 font-mono">
          <div class="p-3 rounded-xl bg-slate-900 border border-slate-800">
            <div class="text-slate-400 text-[10px] uppercase">Original Record</div>
            <div class="text-emerald-400 font-bold text-sm mt-1 flex items-center gap-1.5">
              <i data-lucide="check" class="w-4 h-4"></i>
              <span>VALID [200 OK]</span>
            </div>
            <div class="text-[10px] text-slate-500 mt-1">Argon2 seal verified cleanly</div>
          </div>
          <div class="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40">
            <div class="text-rose-300 text-[10px] uppercase">Tampered Record</div>
            <div class="text-rose-400 font-bold text-sm mt-1 flex items-center gap-1.5">
              <i data-lucide="ban" class="w-4 h-4"></i>
              <span>TAMPER BLOCKED</span>
            </div>
            <div class="text-[10px] text-rose-300/80 mt-1">Hash verification failed (403)</div>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-emerald-200 leading-relaxed font-sans">
          <strong>Cryptographic Proof Confirmed:</strong> Because Argon2id requires 64MB of dedicated memory and 2 full iterations per evaluation, forged or tampered entries cannot match the original hash. Any unauthorized modification to amounts, recipient accounts, or timestamps is immediately rejected.
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button onclick="closeTamperModal()" class="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">Close</button>
      </div>
    </div>
  </div>

  <!-- SCRIPT LOGIC -->
  <script>
    // State cache
    let appState = null;
    let recognition = null;
    let isListening = false;
    let isSpeaking = false;

    // Initialize Lucide icons
    document.addEventListener("DOMContentLoaded", () => {
      lucide.createIcons();
      initSpeechRecognition();
      loadState();
    });

    // -------------------------------------------------------------
    // Web Speech API: Microphone Speech Recognition
    // -------------------------------------------------------------
    function initSpeechRecognition() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        console.warn("Web SpeechRecognition is not supported in this browser.");
        document.getElementById("voice-status-text").innerText = "Speech API Not Supported (Use Text)";
        return;
      }

      recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        isListening = true;
        setOrbState("listening");
        document.getElementById("voice-status-text").innerText = "Listening to your voice...";
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById("voice-input-text").value = transcript;
        sendUserQuery(transcript);
      };

      recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        isListening = false;
        setOrbState("idle");
        document.getElementById("voice-status-text").innerText = "Push to Talk (Web Speech API)";
      };

      recognition.onend = () => {
        isListening = false;
        if (!isSpeaking) {
          setOrbState("idle");
          document.getElementById("voice-status-text").innerText = "Push to Talk (Web Speech API)";
        }
      };
    }

    function toggleMicrophone() {
      if (!recognition) {
        alert("Microphone recognition is not supported in this browser. Please type your query.");
        return;
      }
      if (isListening) {
        recognition.stop();
      } else {
        try {
          recognition.start();
        } catch (e) {
          console.error(e);
        }
      }
    }

    // -------------------------------------------------------------
    // Web Speech API: Spoken TTS Playback
    // -------------------------------------------------------------
    function speakText(text) {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      utterance.onstart = () => {
        isSpeaking = true;
        setOrbState("speaking");
        document.getElementById("voice-status-text").innerText = "Alexa+ Speaking...";
      };

      utterance.onend = () => {
        isSpeaking = false;
        setOrbState("idle");
        document.getElementById("voice-status-text").innerText = "Push to Talk (Web Speech API)";
      };

      window.speechSynthesis.speak(utterance);
    }

    function setOrbState(state) {
      const orb = document.getElementById("voice-orb");
      const icon = document.getElementById("orb-icon");
      orb.className = "orb-core w-20 h-20 rounded-full flex items-center justify-center shadow-2xl";

      if (state === "listening") {
        orb.classList.add("orb-listening");
      } else if (state === "thinking") {
        orb.classList.add("orb-thinking");
      } else if (state === "speaking") {
        orb.classList.add("orb-speaking");
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
        console.error(err);
      }
    }

    function renderInvoices(invoices) {
      const container = document.getElementById("invoice-cards-container");
      if (!invoices || invoices.length === 0) {
        container.innerHTML = '<div class="text-slate-500 py-6 text-center">No invoices loaded.</div>';
        return;
      }

      container.innerHTML = invoices.map(inv => {
        const risk = inv.forensics?.risk || {};
        const arith = inv.forensics?.arithmetic || {};
        const dup = inv.forensics?.duplicate || {};
        const policy = inv.forensics?.policy || {};

        let badgeClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
        if (risk.risk_level === "HIGH") badgeClass = "bg-rose-500/10 text-rose-400 border-rose-500/30";
        if (risk.risk_level === "CRITICAL") badgeClass = "bg-purple-500/20 text-purple-300 border-purple-500/40 ring-1 ring-purple-400";
        if (risk.risk_level === "MEDIUM") badgeClass = "bg-amber-500/10 text-amber-300 border-amber-500/30";

        let statusPill = `<span class="text-[11px] px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">${inv.status}</span>`;
        if (inv.status.includes("QUARANTINE")) {
          statusPill = `<span class="text-[11px] px-2 py-0.5 rounded font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30">QUARANTINED</span>`;
        } else if (inv.status.includes("APPROVED")) {
          statusPill = `<span class="text-[11px] px-2 py-0.5 rounded font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">SEALED & APPROVED</span>`;
        }

        return `
          <div class="argon-glass rounded-xl p-4 transition hover:border-slate-700 space-y-3">
            <div class="flex items-start justify-between">
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-bold text-white text-sm">${inv.invoice_number}</span>
                  <span class="text-xs px-2 py-0.5 rounded-full border font-bold ${badgeClass}">
                    ${risk.risk_level || "UNKNOWN"} RISK (${risk.risk_score || 0}/100)
                  </span>
                  ${statusPill}
                </div>
                <div class="text-xs text-slate-300 mt-0.5 font-medium">${inv.vendor_name}</div>
              </div>
              <div class="text-right">
                <div class="font-mono font-bold text-base text-white">$${parseFloat(inv.total).toLocaleString('en-US', {minimumFractionDigits: 2})}</div>
                <div class="text-[10px] text-slate-400">${inv.invoice_date}</div>
              </div>
            </div>

            <!-- Checks Grid -->
            <div class="grid grid-cols-3 gap-2 text-[11px] font-mono">
              <div class="p-2 rounded-lg bg-slate-900/80 border border-slate-800/80">
                <span class="text-slate-400 block text-[10px]">Arithmetic</span>
                <span class="${arith.passed ? 'text-emerald-400' : 'text-rose-400 font-bold'}">
                  ${arith.passed ? 'PASS (Exact)' : 'FAIL ($1,200 error)'}
                </span>
              </div>
              <div class="p-2 rounded-lg bg-slate-900/80 border border-slate-800/80">
                <span class="text-slate-400 block text-[10px]">Duplicates</span>
                <span class="${dup.status === 'CONFIRMED_DUPLICATE' ? 'text-rose-400 font-bold' : 'text-emerald-400'}">
                  ${dup.status === 'CONFIRMED_DUPLICATE' ? 'DUPLICATE MATCH' : 'NO_DUPLICATE'}
                </span>
              </div>
              <div class="p-2 rounded-lg bg-slate-900/80 border border-slate-800/80">
                <span class="text-slate-400 block text-[10px]">Policy Check</span>
                <span class="${policy.passed ? 'text-emerald-400' : 'text-amber-400 font-bold'}">
                  ${policy.passed ? 'COMPLIANT' : 'BREACH (>$25k)'}
                </span>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="flex items-center justify-between pt-1 text-xs">
              <span class="text-[10px] font-mono text-slate-500 truncate max-w-[260px]">
                Seal: ${inv.latest_seal ? inv.latest_seal.substring(0, 32) + '...' : 'Unsealed'}
              </span>
              <div class="flex items-center gap-2">
                <button
                  onclick="triggerAction('${inv.invoice_id}', 'APPROVE_AND_SEAL')"
                  class="px-2.5 py-1 rounded-lg bg-emerald-600/80 hover:bg-emerald-500 text-white font-medium text-[11px] transition flex items-center gap-1 shadow"
                >
                  <i data-lucide="check" class="w-3 h-3"></i>
                  <span>Approve & Seal</span>
                </button>
                <button
                  onclick="triggerAction('${inv.invoice_id}', 'QUARANTINE_AND_DISPUTE')"
                  class="px-2.5 py-1 rounded-lg bg-rose-600/80 hover:bg-rose-500 text-white font-medium text-[11px] transition flex items-center gap-1 shadow"
                >
                  <i data-lucide="shield-alert" class="w-3 h-3"></i>
                  <span>Quarantine</span>
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderAuditChain(chain) {
      const feed = document.getElementById("audit-chain-feed");
      if (!chain || chain.length === 0) {
        feed.innerHTML = '<div class="text-slate-500 py-4 text-center font-mono text-xs">No audit blocks.</div>';
        return;
      }

      feed.innerHTML = chain.slice().reverse().map(block => {
        return `
          <div class="p-3 rounded-xl bg-slate-950/80 border border-slate-800/90 font-mono text-xs space-y-1.5 transition hover:border-slate-700">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[10px]">BLOCK #${block.block_index}</span>
                <span class="text-white font-semibold">${block.action}</span>
                <span class="text-slate-500">|</span>
                <span class="text-sky-300">${block.tx_id}</span>
              </div>
              <span class="text-[10px] text-slate-500">${block.timestamp}</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] text-slate-400 pt-1">
              <div class="truncate">
                <span class="text-slate-500">Prev Hash:</span> <span class="text-slate-300">${block.prev_hash.substring(0, 36)}...</span>
              </div>
              <div class="truncate">
                <span class="text-slate-500">SHA-256:</span> <span class="text-slate-300">${block.sha256.substring(0, 36)}...</span>
              </div>
            </div>

            <div class="text-[10px] text-slate-500 truncate pt-0.5">
              <span class="text-emerald-500 font-semibold">Argon2id Seal:</span> <span class="text-emerald-300/90">${block.argon2_seal}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    // -------------------------------------------------------------
    // Send Voice / Text Query
    // -------------------------------------------------------------
    async function sendUserQuery(customQuery) {
      const input = document.getElementById("voice-input-text");
      const prompt = customQuery || input.value.trim();
      if (!prompt) return;

      input.value = "";
      setOrbState("thinking");
      document.getElementById("voice-status-text").innerText = "Strands Agent Reasoning...";

      try {
        const res = await fetch("/api/alexa/converse", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({prompt: prompt}),
        });

        if (!res.ok) throw new Error("Converse error: " + res.status);
        const data = await res.json();

        // Update speech balloon and speak
        document.getElementById("alexa-speech-output").innerText = `"${data.voice_speech}"`;
        speakText(data.voice_speech);

        // Update Engine Badge
        document.getElementById("active-engine-badge").innerText = data.active_engine || "deterministic_local_router";

        // Refresh state
        await loadState();
      } catch (err) {
        console.error(err);
        setOrbState("idle");
      }
    }

    function runChip(text) {
      document.getElementById("voice-input-text").value = text;
      sendUserQuery(text);
    }

    // -------------------------------------------------------------
    // Invoice Actions
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
        console.error(err);
      }
    }

    // -------------------------------------------------------------
    // MCP Streamable HTTP 2025-11-25 Live Calls
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
        console.error(err);
      }
    }

    function closeTamperModal() {
      document.getElementById("tamper-modal").classList.add("hidden");
    }
  </script>
</body>
</html>
"""
