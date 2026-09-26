const defaultBorrowers = [
  {
    id: 'APP-2026-001',
    farmer_id: 'entrepreneur:413001:001',
    account_no: 'SBIN413001001',
    bank_name: 'State Bank of India',
    branch_name: 'Barshi Main Branch, Solapur',
    ifsc_code: 'SBIN0413001',
    name: 'Ramesh Pawar',
    village: 'Barshi Main Branch, Solapur',
    crop: 'Kirana & General Store',
    enterprise_type: 'Kirana & General Store',
    pincode: '413001',
    on_time_payment_pct_24m: '95%',
    dpd_trail_12m: '0-0-0-0-0-0-0-0-0-0-0-0',
    nach_bounces_12m: 0,
    avg_payment_delay_days: '0.0',
    bbps_utility_compliance_pct: '96%',
    credit_utilization_pct: '32%',
    score: 805,
    pd: '7.4%',
    band: 'Low',
    reasons: [
      { feature: 'Regional economic & climate stress', direction: 'increases_risk', pts: '+58 risk pts', width: '85%', color: 'rose' },
      { feature: 'Delayed commercial utility bills', direction: 'increases_risk', pts: '+20 risk pts', width: '45%', color: 'rose' },
      { feature: 'Operating cashflow deficit', direction: 'increases_risk', pts: '+45 risk pts', width: '70%', color: 'rose' },
    ],
    recommended_step: 'Standard review approved. High payment punctuality trail verified.',
  },
];

const state = {
  view: 'gateway',
  language: 'English',
  selected: 'APP-2026-001',
  activeBankNode: 'all',
  searchQuery: '',
  showAppModal: false,
  showOfficerAuthModal: false,
  showDocRequestModal: false,
  officerAuth: null,
  toastMessage: '',
  borrowersList: defaultBorrowers,
  api: 'Checking sandbox…',
  policy: { artifact_status: 'Loading…', manual_review_records: 0, fairness_status: 'Loading…', cohorts: {} },
  security: { audit_ledger: { status: 'Loading…' }, roles: [], rate_limit: {} },
  serverIp: '127.0.0.1',
  serverUrl: '',
  accessToken: null,
};

const copy = {
  English: {
    title: 'Why did my business credit need review?',
    answer:
      'Your enterprise credit line requires a lender review due to recent regional economic stress and delayed commercial utility bills. This is not a final rejection. You can share updated trade receipts, GST returns, or revenue evidence with the credit officer.',
    speak: 'Listen to explanation',
    ask: 'Ask about your enterprise loan in your language',
  },
  हिंदी: {
    title: 'मेरे व्यावसायिक ऋण की समीक्षा क्यों हो रही है?',
    answer:
      'क्षेत्रीय आर्थिक तनाव और उपयोगिता भुगतान में देरी के कारण आपके व्यावसायिक ऋण की समीक्षा जरूरी है। यह अंतिम अस्वीकृति नहीं है। आप ऋण अधिकारी के साथ नई बिक्री रसीदें या व्यापार जानकारी साझा कर सकते हैं।',
    speak: 'स्पष्टीकरण सुनें',
    ask: 'अपनी भाषा में व्यवसाय ऋण के बारे में पूछें',
  },
  मराठी: {
    title: 'माझ्या व्यावसायिक कर्जाचे पुनरावलोकन का होत आहे?',
    answer:
      'अलीकडील प्रादेशिक आर्थिक ताण आणि वीज बिलाचा भरणा उशिरा झाल्यामुळे कर्जाचे पुनरावलोकन आवश्यक आहे. हा अंतिम नकार नाही. तुम्ही कर्ज अधिकाऱ्याला नवीन विक्री किंवा व्यापाराची माहिती देऊ शकता।',
    speak: 'स्पष्टीकरण ऐका',
    ask: 'तुमच्या भाषेत कर्जाबद्दल विचारा',
  },
};

function apiFetch(url, options = {}) {
  const target = state.serverUrl ? `${state.serverUrl}${url}` : url;
  if (!options.headers) {
    options.headers = {};
  }
  if (state.accessToken) {
    options.headers['Authorization'] = `Bearer ${state.accessToken}`;
  }
  return fetch(target, options);
}

function badge(band) {
  const styles = { Low: 'bg-emerald-100 text-emerald-700', Moderate: 'bg-amber-100 text-amber-700', High: 'bg-rose-100 text-rose-700' };
  return `<span class="rounded-full px-2.5 py-1 text-xs font-bold ${styles[band] || 'bg-slate-100 text-slate-700'}">${band} risk</span>`;
}

function policyPanel() {
  const policy = state.policy || {};
  const cohorts = Object.entries(policy.cohorts || {});
  const statusStyle = policy.fairness_status === 'REVIEW_REQUIRED' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600';
  const cohortRows = cohorts.length
    ? cohorts
        .map(
          ([pincode, item]) =>
            `<div class="flex items-center justify-between border-t border-slate-100 py-2 text-xs"><span class="font-semibold text-slate-700">${pincode}</span><span class="text-slate-500">${item.records} records · ${Math.round(
              (item.priority_review_rate || 0) * 100
            )}% priority</span></div>`
        )
        .join('')
    : '<p class="mt-3 text-xs text-slate-500">Policy artifacts are loading. Run the Phase 7 policy command if this remains empty.</p>';
  return `<div class="mt-6 rounded-xl border border-slate-200 p-4"><div class="flex items-start justify-between gap-3"><div><p class="text-xs font-bold uppercase tracking-wider text-ink">Policy & fairness</p><p class="mt-1 text-xs text-slate-500">Synthetic diagnostic · policy ${
    policy.policy_version || 'loading'
  }</p></div><span class="rounded-full px-2 py-1 text-[10px] font-bold ${statusStyle}">${
    policy.fairness_status || 'Loading…'
  }</span></div><div class="mt-4 rounded-lg bg-emerald-50 p-3"><p class="text-xs font-bold text-leaf">${
    policy.manual_review_records || 0
  } manual-review records</p><p class="mt-1 text-xs text-slate-600">Automatic approval and decline are disabled.</p></div><div class="mt-3">${cohortRows}</div><p class="mt-3 text-[11px] leading-4 text-slate-500">PIN-code cohorts are scenario diagnostics, not protected-group fairness proof. A reviewer must assess any differences.</p></div>`;
}

function securityPanel() {
  const security = state.security || {};
  const audit = security.audit_ledger || {};
  const valid = audit.valid === true;
  const auditStyle = valid ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600';
  return `<div class="mt-4 rounded-xl border border-slate-200 p-4"><div class="flex items-start justify-between gap-3"><div><p class="text-xs font-bold uppercase tracking-wider text-ink">Integration security</p><p class="mt-1 text-xs text-slate-500">Sandbox controls only · no live partner link</p></div><span class="rounded-full px-2 py-1 text-[10px] font-bold ${auditStyle}">${
    audit.status || 'Loading…'
  }</span></div><div class="mt-4 grid grid-cols-2 gap-2 text-xs"><div class="rounded-lg bg-slate-50 p-2"><b class="block text-ink">Roles</b><span class="text-slate-500">${
    (security.roles || []).join(', ') || 'loading'
  }</span></div><div class="rounded-lg bg-slate-50 p-2"><b class="block text-ink">Rate limit</b><span class="text-slate-500">${
    security.rate_limit?.requests || '–'
  } / ${
    security.rate_limit?.window_seconds || '–'
  } sec</span></div></div><p class="mt-3 text-[11px] leading-4 text-slate-500">Signed webhooks, audit hashes, and retention controls are simulated with synthetic data. No secrets or audit-event contents are displayed here.</p></div>`;
}

function shell(content) {
  return `<main class="min-h-screen relative">${
    state.toastMessage
      ? `<div class="fixed top-5 right-5 z-50 flex items-center gap-2 rounded-xl bg-leaf px-4 py-3 text-sm font-bold text-white shadow-xl animate-bounce"><span>${state.toastMessage}</span></div>`
      : ''
  }<header class="border-b border-slate-200 bg-white"><div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4"><button class="flex items-center gap-3" onclick="setView('gateway')"><span class="grid h-10 w-10 place-items-center rounded-xl bg-leaf text-xl text-white">V</span><span class="text-left"><strong class="block text-lg text-ink">Vridhi</strong><small class="text-slate-500">Rural Risk Intelligence</small></span></button><div class="flex flex-wrap items-center justify-end gap-2"><span id="api-pill" class="hidden rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"></span>${
    state.officerAuth
      ? `<span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800 flex items-center gap-1.5">🔑 ${state.officerAuth.uid} <button onclick="logoutOfficer()" class="ml-1 text-rose-600 hover:underline">Logout</button></span>`
      : ''
  }<button onclick="setView('gateway')" class="rounded-lg px-3 py-2 text-sm font-semibold ${
    state.view === 'gateway' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
  }">🌐 Gateway</button><button onclick="setView('lender')" class="rounded-lg px-3 py-2 text-sm font-semibold ${
    state.view === 'lender' ? 'bg-ink text-white' : 'text-slate-600 hover:bg-slate-100'
  }">🏦 Lender desk</button><button onclick="setView('borrower')" class="rounded-lg px-3 py-2 text-sm font-semibold ${
    state.view === 'borrower' ? 'bg-leaf text-white' : 'text-slate-600 hover:bg-slate-100'
  }">🏪 Entrepreneur assistant</button><button onclick="setView('admin')" class="rounded-lg px-3 py-2 text-sm font-semibold ${
    state.view === 'admin' ? 'bg-saffron text-white' : 'text-slate-600 hover:bg-slate-100'
  }">⚙️ Sandbox admin</button></div></div></header>${content}${applicationFormModal()}${officerAuthModal()}${docRequestModal()}</main>`;
}

function officerAuthModal() {
  if (!state.showOfficerAuthModal) return '';
  return `<div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-md">
    <div class="w-full max-w-md rounded-3xl bg-white p-7 shadow-2xl space-y-5">
      <div class="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <span class="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800">🔐 Bank Security Gate</span>
          <h2 class="mt-2 text-2xl font-bold text-ink">Loan Officer Authentication</h2>
          <p class="text-xs text-slate-500">Enter Bank Officer UID to access the Underwriting Desk.</p>
        </div>
        <button onclick="closeOfficerAuthModal()" class="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-500 hover:bg-slate-200">✕</button>
      </div>

      <!-- Pre-filled Quick Demo Credentials -->
      <div class="rounded-2xl bg-blue-50 p-4 border border-blue-100">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs font-bold text-blue-900">Faculty Presentation Demo Credentials</p>
            <p class="text-[11px] text-blue-700 font-mono mt-0.5">UID: OFFICER-789 | Code: 413001</p>
          </div>
          <button onclick="autoFillOfficerDemo()" class="rounded-xl bg-blue-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-blue-700">⚡ Auto-fill</button>
        </div>
      </div>

      <form onsubmit="authenticateOfficer(event)" class="space-y-4">
        <div>
          <label class="block text-xs font-bold text-slate-700">Bank Officer UID / Employee ID *</label>
          <input type="text" id="auth-officer-uid" required placeholder="e.g. OFFICER-789" class="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm font-mono focus:border-blue-600 focus:outline-none" />
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-700">Bank Branch Security Code *</label>
          <input type="password" id="auth-branch-code" required placeholder="Enter 6-digit Branch PIN" class="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm font-mono focus:border-blue-600 focus:outline-none" />
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button type="button" onclick="closeOfficerAuthModal()" class="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-100">Cancel</button>
          <button type="submit" class="rounded-xl bg-ink px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-slate-800">🔐 Authenticate & Enter Desk</button>
        </div>
      </form>
    </div>
  </div>`;
}

function autoFillOfficerDemo() {
  const uidInput = document.getElementById('auth-officer-uid');
  const codeInput = document.getElementById('auth-branch-code');
  if (uidInput) uidInput.value = 'OFFICER-789';
  if (codeInput) codeInput.value = '413001';
}

function authenticateOfficer(e) {
  e.preventDefault();
  const uid = document.getElementById('auth-officer-uid').value.trim();
  const code = document.getElementById('auth-branch-code').value.trim();

  if (uid && code) {
    state.officerAuth = { uid, bank: 'State Bank of India', branch: 'Solapur Main' };
    state.showOfficerAuthModal = false;
    state.view = 'lender';
    state.toastMessage = `🔐 Authenticated as Officer ${uid}`;
    render();

    setTimeout(() => {
      state.toastMessage = '';
      render();
    }, 3000);
  }
}

function logoutOfficer() {
  state.officerAuth = null;
  state.view = 'gateway';
  state.toastMessage = '🔒 Officer logged out. Desk locked.';
  render();

  setTimeout(() => {
    state.toastMessage = '';
    render();
  }, 3000);
}

function closeOfficerAuthModal() {
  state.showOfficerAuthModal = false;
  render();
}

function openDocRequestModal(id) {
  state.selectedDocBorrower = id;
  state.showDocRequestModal = true;
  render();
}

function closeDocRequestModal() {
  state.showDocRequestModal = false;
  render();
}

function sendDocRequest(e) {
  e.preventDefault();
  const person = state.borrowersList.find((b) => b.id === state.selectedDocBorrower) || state.borrowersList[0];
  if (person) {
    person.requested_docs = true;
  }
  state.showDocRequestModal = false;
  state.toastMessage = `📩 Verification Document Request sent to ${person.name} (${person.account_no}) via SMS & WhatsApp!`;
  render();

  setTimeout(() => {
    state.toastMessage = '';
    render();
  }, 4000);
}

function docRequestModal() {
  if (!state.showDocRequestModal) return '';
  const person = state.borrowersList.find((b) => b.id === state.selectedDocBorrower) || state.borrowersList[0];

  return `<div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-md">
    <div class="w-full max-w-lg rounded-3xl bg-white p-7 shadow-2xl space-y-5">
      <div class="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <span class="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800">📄 Underwriter Document Dispatch</span>
          <h2 class="mt-2 text-2xl font-bold text-ink">Request Verification Documents</h2>
          <p class="text-xs text-slate-500">Applicant: <b>${person.name}</b> (${person.account_no}) · ${person.bank_name}</p>
        </div>
        <button onclick="closeDocRequestModal()" class="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-500 hover:bg-slate-200">✕</button>
      </div>

      <form onsubmit="sendDocRequest(event)" class="space-y-4">
        <div>
          <label class="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Select Required Verification Documents:</label>
          <div class="space-y-2.5 text-xs font-semibold text-slate-700 bg-slate-50 p-4 rounded-2xl border border-slate-200">
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" checked class="h-4 w-4 rounded border-slate-300 accent-blue-600" />
              <span>GST Returns & Trade Sales Receipts (Last 6 Months)</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" checked class="h-4 w-4 rounded border-slate-300 accent-blue-600" />
              <span>APMC Mandi Harvest & Commodity Sale Vouchers</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" checked class="h-4 w-4 rounded border-slate-300 accent-blue-600" />
              <span>Commercial Electricity & Utility Bill Payment Receipts</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" class="h-4 w-4 rounded border-slate-300 accent-blue-600" />
              <span>12-Month Account Aggregator Bank Statement</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" class="h-4 w-4 rounded border-slate-300 accent-blue-600" />
              <span>Shop Premises Ownership / Commercial Lease Agreement</span>
            </label>
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-700">Official Note to Applicant (Sent via SMS / WhatsApp) *</label>
          <textarea rows="3" required class="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-blue-600 focus:outline-none" placeholder="Please upload your recent APMC sales receipts and commercial electricity bill clearance to complete your working capital credit evaluation."></textarea>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button type="button" onclick="closeDocRequestModal()" class="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-100">Cancel</button>
          <button type="submit" class="rounded-xl bg-ink px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-slate-800">📤 Send SMS & WhatsApp Request</button>
        </div>
      </form>
    </div>
  </div>`;
}

function openBorrowerExplanation(id) {
  state.selected = id;
  state.view = 'borrower';
  const person = state.borrowersList.find((b) => b.id === id) || state.borrowersList[0];
  state.toastMessage = `💬 Opened Self-Service Voice Explanation for ${person.name}`;
  render();

  setTimeout(() => {
    speakAnswer();
  }, 500);

  setTimeout(() => {
    state.toastMessage = '';
    render();
  }, 4000);
}

function selectBankNode(bankCode) {
  state.activeBankNode = bankCode;
  if (bankCode === 'all') {
    apiFetch('/v1/borrowers')
      .then((res) => res.json())
      .then((data) => {
        if (data.borrowers && data.borrowers.length) {
          state.borrowersList = data.borrowers;
          state.selected = state.borrowersList[0].id;
          state.toastMessage = `🌐 Switched to Master Multi-Bank Network (${state.borrowersList.length} files)`;
          render();
          setTimeout(() => { state.toastMessage = ''; render(); }, 3000);
        }
      });
  } else {
    apiFetch(`/v1/bank/${bankCode}/borrowers`)
      .then((res) => res.json())
      .then((data) => {
        if (data.borrowers && data.borrowers.length) {
          state.borrowersList = data.borrowers;
          state.selected = state.borrowersList[0].id;
          state.toastMessage = `🔒 Connected to ${data.bank_name} Isolated Node (Port ${data.port} | servers/${bankCode}_node/)`;
          render();
          setTimeout(() => { state.toastMessage = ''; render(); }, 3000);
        }
      })
      .catch(() => {
        alert(`Dedicated Server Node for ${bankCode.toUpperCase()} is connecting...`);
      });
  }
}

function performHandshake() {
  const ip = document.getElementById('target-server-ip').value.trim();
  if (!ip) return;
  
  state.serverIp = ip;
  state.serverUrl = ip.includes(':') ? `http://${ip}` : `http://${ip}:8000`;

  const params = new URLSearchParams();
  params.append('grant_type', 'client_credentials');
  params.append('client_id', 'sandbox-client');
  params.append('client_secret', 'sandbox-secret');
  params.append('scope', 'consent:write');

  fetch(`${state.serverUrl}/v1/oauth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: params
  })
  .then((res) => {
    if (!res.ok) throw new Error('Handshake failed.');
    return res.json();
  })
  .then((data) => {
    if (data.access_token) {
      state.accessToken = data.access_token;
      state.toastMessage = '⚡ Handshake Successful! Dynamic Session API Key Generated!';
      
      // Load diagnostic parameters from new server
      apiFetch('/health')
        .then((res) => res.json())
        .then((info) => {
          state.api = info.model_loaded ? '● Sandbox connected' : '● Sandbox model unavailable';
          render();
        });
      
      // Load registered bank nodes from the new server
      apiFetch('/v1/bank/nodes')
        .then((res) => res.json())
        .then((data) => {
          if (data.nodes) {
            state.registeredNodes = data.nodes;
            render();
          }
          // Load borrowers from active node
          selectBankNode(state.activeBankNode);
        });
    }
  })

  .catch(() => {
    alert('Failed to connect to Bank Server Node. Check Wi-Fi connection and ensure server is active on your friend\'s laptop.');
  });
}

function gatewayView() {
  return shell(`<div class="mx-auto max-w-5xl px-5 py-12">
    <div class="text-center space-y-3">
      <span class="inline-block rounded-full bg-emerald-100 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-leaf">Dual-Sided Enterprise Credit Platform</span>
      <h1 class="text-4xl font-extrabold text-ink sm:text-5xl">Welcome to Vridhi Analytics</h1>
      <p class="mx-auto max-w-2xl text-base text-slate-600">India's Privacy-First Rural Credit Risk Engine for Banks & Empowering Rural Entrepreneurs.</p>
    </div>

    <div class="mt-12 grid gap-8 md:grid-cols-2">
      <!-- Card A: Bank Loan Officer Desk -->
      <div onclick="setView('lender')" class="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-8 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-ink hover:shadow-2xl">
        <div class="flex items-center justify-between">
          <span class="grid h-14 w-14 place-items-center rounded-2xl bg-ink text-2xl text-white shadow-md">🏦</span>
          <span class="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800">🔐 Dedicated Bank Node Network</span>
        </div>
        <h2 class="mt-6 text-2xl font-bold text-ink group-hover:text-blue-600">Bank Loan Officer Desk</h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">Underwriting terminal for bank officers. Select dedicated bank node (SBI, MAHB, CBIN), inspect 24M DPD trails, and export faculty CSVs.</p>
        
        <ul class="mt-6 space-y-2 text-xs font-medium text-slate-700">
          <li class="flex items-center gap-2"><span class="text-leaf font-bold">✓</span> Bank Officer UID Login & Security Verification</li>
          <li class="flex items-center gap-2"><span class="text-leaf font-bold">✓</span> Dedicated Isolated Server Node Folders per Bank</li>
          <li class="flex items-center gap-2"><span class="text-leaf font-bold">✓</span> 24-Month DPD & Delinquency History Tracks</li>
        </ul>

        <div class="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
          <span class="text-sm font-bold text-ink group-hover:text-blue-600">Enter Officer Desk →</span>
          <span class="rounded-xl bg-slate-100 px-4 py-2 text-xs font-bold text-slate-800 group-hover:bg-ink group-hover:text-white transition-colors">Authenticate & Enter</span>
        </div>
      </div>

      <!-- Card B: Common Rural Entrepreneur Portal -->
      <div onclick="setView('borrower')" class="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-8 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-leaf hover:shadow-2xl">
        <div class="flex items-center justify-between">
          <span class="grid h-14 w-14 place-items-center rounded-2xl bg-leaf text-2xl text-white shadow-md">🏪</span>
          <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">Public Self-Service</span>
        </div>
        <h2 class="mt-6 text-2xl font-bold text-ink group-hover:text-leaf">Rural Entrepreneur Portal</h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">Dedicated self-service portal for kirana owners, farmers & micro-entrepreneurs. Check credit score (300-900), talk to Vridhi Sahayak in Marathi/Hindi, and calculate EMIs.</p>

        <ul class="mt-6 space-y-2 text-xs font-medium text-slate-700">
          <li class="flex items-center gap-2"><span class="text-leaf font-bold">✓</span> Instant Credit Score Check (300 - 900)</li>
          <li class="flex items-center gap-2"><span class="text-leaf font-bold">✓</span> Multi-Lingual Voice Assistant (Sahayak)</li>
          <li class="flex items-center gap-2"><span class="text-leaf font-bold">✓</span> Simple Business Credit Improvement Guidance</li>
        </ul>

        <div class="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
          <span class="text-sm font-bold text-leaf">Check My Business Score →</span>
          <span class="rounded-xl bg-emerald-50 px-4 py-2 text-xs font-bold text-leaf group-hover:bg-leaf group-hover:text-white transition-colors">Open Portal</span>
        </div>
      </div>
    </div>

    <!-- External Server Handshake Gateway (Multi-Laptop Setup) -->
    <div class="mt-12 rounded-3xl bg-slate-50 p-7 border border-slate-200/80 max-w-2xl mx-auto text-center space-y-4 shadow-sm">
      <span class="inline-block rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800 uppercase tracking-wider">🔗 Multi-Laptop Handshake Connection</span>
      <h3 class="font-bold text-ink text-base">Connect to Friend's Laptop Server</h3>
      <p class="text-xs text-slate-500">Run the server nodes on your friend's laptop, type their IP address below, and click Connect to generate a dynamic session token.</p>
      
      <div class="flex items-center gap-2 justify-center pt-2">
        <span class="text-xs font-bold text-slate-700">Server Host IP:</span>
        <input type="text" id="target-server-ip" placeholder="e.g. 192.168.1.15" class="rounded-xl border border-slate-300 px-3.5 py-2 text-xs font-mono font-bold w-44 text-center focus:outline-none" value="${state.serverIp || '127.0.0.1'}" />
        <button onclick="performHandshake()" class="rounded-xl bg-ink px-5 py-2 text-xs font-bold text-white hover:bg-slate-800 shadow-md transition-all">🔄 Connect & Generate Session Key</button>
      </div>
      
      ${state.accessToken 
        ? `<div class="mt-2 text-xs font-bold text-emerald-700 flex items-center justify-center gap-1.5 bg-emerald-50 p-2.5 rounded-xl border border-emerald-200">
            <span>● Session Connected! access_token:</span>
            <span class="font-mono text-[10px] bg-emerald-100/50 px-2 py-0.5 rounded border border-emerald-300 text-emerald-800">${state.accessToken.slice(0, 30)}...</span>
           </div>`
        : `<p class="text-xs font-medium text-slate-500 pt-1">Enter your friend's laptop local IP to initiate the client credentials OAuth2 handshake.</p>`
      }
    </div>
  </div>`);
}

function applicationFormModal() {
  if (!state.showAppModal) return '';
  return `<div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
    <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-white p-7 shadow-2xl">
      <div class="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">Faculty Demo Mode</span>
          <h2 class="mt-2 text-2xl font-bold text-ink">Rural Entrepreneur Credit Form</h2>
          <p class="text-xs text-slate-500">Dynamic sector questionnaire for agricultural & non-agricultural rural micro-entrepreneurs.</p>
        </div>
        <button onclick="closeAppModal()" class="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-500 hover:bg-slate-200">✕</button>
      </div>

      <form onsubmit="submitLoanApplication(event)" class="mt-5 space-y-5">
        <!-- Section 1: Bank & Identification -->
        <div class="rounded-2xl bg-slate-50 p-4 space-y-3">
          <p class="text-xs font-bold uppercase tracking-wider text-ink">1. Enterprise & Bank Identification</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="block text-xs font-bold text-slate-700">Entrepreneur Full Name *</label>
              <input type="text" id="form-borrower-name" required placeholder="e.g. Ramesh Pawar" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Bank Name *</label>
              <input type="text" id="form-bank-name" required placeholder="e.g. State Bank of India" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Branch Name *</label>
              <input type="text" id="form-branch-name" required placeholder="e.g. Paithan Branch, Sambhajinagar" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Account Number *</label>
              <input type="text" id="form-account-number" required placeholder="e.g. SBIN413001001" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-mono focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">IFSC Code *</label>
              <input type="text" id="form-ifsc-code" required placeholder="e.g. SBIN0004130" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-mono focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">PIN Code *</label>
              <input type="number" id="form-pincode" required value="413001" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
          </div>
        </div>

        <!-- Section 2: Dynamic Enterprise Sector Questionnaire -->
        <div class="rounded-2xl bg-slate-50 p-4 space-y-3">
          <p class="text-xs font-bold uppercase tracking-wider text-ink">2. Dynamic Enterprise Sector Questionnaire</p>
          <div>
            <label class="block text-xs font-bold text-slate-800">Is this applicant an Agricultural / Farming Enterprise? *</label>
            <select id="form-is-agri" onchange="toggleSectorFields(this.value)" class="mt-1.5 w-full rounded-xl border border-emerald-600 bg-emerald-50 px-3 py-2.5 text-sm font-bold text-slate-900 focus:border-leaf focus:outline-none shadow-sm">
              <option value="no">No — Non-Agri Micro-Enterprise (Kirana, Dairy, Solar, Transport, Handicrafts)</option>
              <option value="yes">Yes — Agricultural / Farming Enterprise (Crop cultivation, Dairy-Agri)</option>
            </select>
          </div>

          <!-- Non-Agri Dynamic Fields -->
          <div id="non-agri-fields" class="space-y-3 pt-2">
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label class="block text-xs font-bold text-slate-700">Business / Enterprise Type *</label>
                <select id="form-non-agri-type" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold focus:border-leaf focus:outline-none">
                  <option value="Kirana & General Store">Kirana & General Provisions Store</option>
                  <option value="Dairy & Milk Collection Unit">Dairy & Milk Collection Unit</option>
                  <option value="Agri-Input & Seed Dealer">Agri-Input & Seed Dealership</option>
                  <option value="Spices & Food Processing Unit">Spices & Food Processing Unit</option>
                  <option value="Tractor & Machinery Rental">Tractor & Farm Machinery Rental</option>
                  <option value="Rural Solar & Electricals">Rural Solar & Electrical Solutions</option>
                  <option value="Handloom & Textile Enterprise">Handloom & Textile Enterprise</option>
                  <option value="Rural Transport & Logistics">Rural Transport & Freight Logistics</option>
                  <option value="Poultry & Hatchery Farm">Poultry & Hatchery Farm</option>
                  <option value="Cold Storage & Warehouse Unit">Cold Storage & Warehouse Unit</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700">Years in Operation (Business Vintage)</label>
                <input type="number" id="form-vintage-years" value="3" min="0" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700">Commercial Premises Status</label>
                <select id="form-premises-status" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none">
                  <option value="Owned Shop">Owned Commercial Premises</option>
                  <option value="Leased/Rented Shop">Leased / Rented Shop</option>
                  <option value="Home-based / Mobile">Home-based / Mobile Unit</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700">Daily Customer / Trade Footfall</label>
                <select id="form-footfall" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none">
                  <option value="High (50+ customers/day)">High (50+ transactions/day)</option>
                  <option value="Moderate (20-50/day)">Moderate (20-50 transactions/day)</option>
                  <option value="Low (<20/day)">Low (<20 transactions/day)</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Agri Dynamic Fields -->
          <div id="agri-fields" class="hidden space-y-3 pt-2">
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label class="block text-xs font-bold text-slate-700">Crop Cultivated *</label>
                <select id="form-agri-crop" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold focus:border-leaf focus:outline-none">
                  <option value="Cotton (Farm Enterprise)">Cotton</option>
                  <option value="Soybean (Farm Enterprise)">Soybean</option>
                  <option value="Paddy (Rice Enterprise)">Paddy (Rice)</option>
                  <option value="Sugarcane (Agri Enterprise)">Sugarcane</option>
                  <option value="Pomegranate / Fruit Farm">Pomegranate / Fruits</option>
                  <option value="Turmeric & Spices Farm">Turmeric / Spices Farm</option>
                  <option value="Pulses & Wheat Enterprise">Pulses & Wheat</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700">Cultivated Land Area (Acres)</label>
                <input type="number" id="form-land-acres" value="3.5" step="0.5" min="0" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700">Irrigation Facility</label>
                <select id="form-irrigation" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none">
                  <option value="Well / Canal Drip Irrigation">Drip Irrigation / Well</option>
                  <option value="Solar Pump Irrigation System">Solar Pump System</option>
                  <option value="Rainfed (Monsoon Dependent)">Rainfed (Monsoon Dependent)</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700">Harvest Proceeds Channel</label>
                <select id="form-apmc-channel" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none">
                  <option value="APMC Mandi Direct Trade">APMC Mandi Direct Trade</option>
                  <option value="Contract Farming / FPO">FPO / Contract Farming Buyer</option>
                  <option value="Local Village Trader">Local Village Trader</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Section 3: Financials & Utilities -->
        <div class="rounded-2xl bg-slate-50 p-4 space-y-3">
          <p class="text-xs font-bold uppercase tracking-wider text-ink">3. Financial & Credit Risk Indicators</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="block text-xs font-bold text-slate-700">Monthly Revenue / Inflow (INR) *</label>
              <input type="number" id="form-monthly-income" required value="55000" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Monthly Expenses / Outflow (INR) *</label>
              <input type="number" id="form-monthly-expense" required value="32000" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Working Capital / Cash Balance (INR) *</label>
              <input type="number" id="form-cash-balance" required value="22000" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Missed Utility / Commercial Bills</label>
              <input type="number" id="form-missed-utility" value="0" min="0" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-700">Overdue Loan Installments</label>
              <input type="number" id="form-overdue-installments" value="0" min="0" class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-leaf focus:outline-none" />
            </div>
            <div>
              <div class="flex justify-between text-xs font-bold text-slate-700">
                <span>Regional Climate / Economic Stress</span>
                <span id="drought-val-display" class="text-leaf">0.30</span>
              </div>
              <input type="range" id="form-drought-severity" min="0" max="1" step="0.05" value="0.30" oninput="document.getElementById('drought-val-display').textContent=this.value" class="mt-2 w-full accent-leaf" />
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button type="button" onclick="closeAppModal()" class="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-100">Cancel</button>
          <button type="submit" class="rounded-xl bg-leaf px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-emerald-700">⚡ Evaluate & Save to CSV</button>
        </div>
      </form>
    </div>
  </div>`;
}

function toggleSectorFields(val) {
  const agriContainer = document.getElementById('agri-fields');
  const nonAgriContainer = document.getElementById('non-agri-fields');
  if (val === 'yes') {
    if (agriContainer) agriContainer.classList.remove('hidden');
    if (nonAgriContainer) nonAgriContainer.classList.add('hidden');
  } else {
    if (agriContainer) agriContainer.classList.add('hidden');
    if (nonAgriContainer) nonAgriContainer.classList.remove('hidden');
  }
}

function openAppModal() {
  state.showAppModal = true;
  render();
}

function closeAppModal() {
  state.showAppModal = false;
  render();
}

function submitLoanApplication(e) {
  e.preventDefault();

  const isAgri = document.getElementById('form-is-agri').value === 'yes';
  const enterpriseType = isAgri
    ? document.getElementById('form-agri-crop').value
    : document.getElementById('form-non-agri-type').value;

  const payload = {
    borrower_name: document.getElementById('form-borrower-name').value,
    bank_name: document.getElementById('form-bank-name').value,
    branch_name: document.getElementById('form-branch-name').value,
    account_number: document.getElementById('form-account-number').value,
    ifsc_code: document.getElementById('form-ifsc-code').value,
    pincode: parseInt(document.getElementById('form-pincode').value) || 413001,
    crop_type: enterpriseType,
    monthly_income_inr: parseFloat(document.getElementById('form-monthly-income').value) || 0,
    monthly_expense_inr: parseFloat(document.getElementById('form-monthly-expense').value) || 0,
    cash_balance_inr: parseFloat(document.getElementById('form-cash-balance').value) || 0,
    missed_utility_bills: parseInt(document.getElementById('form-missed-utility').value) || 0,
    overdue_installments: parseInt(document.getElementById('form-overdue-installments').value) || 0,
    drought_severity: parseFloat(document.getElementById('form-drought-severity').value) || 0.2,
    is_agri: isAgri ? 'yes' : 'no',
    land_acres: isAgri ? parseFloat(document.getElementById('form-land-acres').value) || 0 : 0,
    irrigation_type: isAgri ? document.getElementById('form-irrigation').value : '',
    business_vintage_years: !isAgri ? parseInt(document.getElementById('form-vintage-years').value) || 0 : 0,
    premises_status: !isAgri ? document.getElementById('form-premises-status').value : '',
  };

  apiFetch('/v1/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 'SUCCESS' && data.application) {
        const row = data.application;
        const newBorrower = {
          id: row.application_id,
          farmer_id: `entrepreneur:${row.pincode}:${row.account_number.slice(-3)}`,
          account_no: row.account_number,
          bank_name: row.bank_name,
          branch_name: row.branch_name,
          ifsc_code: row.ifsc_code,
          name: row.borrower_name,
          village: row.branch_name,
          crop: row.crop_type,
          enterprise_type: row.crop_type,
          pincode: row.pincode,
          on_time_payment_pct_24m: '95%',
          dpd_trail_12m: '0-0-0-0-0-0-0-0-0-0-0-0',
          nach_bounces_12m: 0,
          avg_payment_delay_days: '0.0',
          bbps_utility_compliance_pct: '96%',
          credit_utilization_pct: '32%',
          score: parseInt(row.synthetic_credit_score) || 650,
          pd: row.risk_pd_pct,
          band: row.risk_band,
          reasons: [
            { feature: 'Regional economic & climate stress', direction: 'increases_risk', pts: `+${Math.round(parseFloat(row.drought_severity) * 50)} risk pts`, width: '60%', color: 'rose' },
            { feature: 'Healthy working capital reserve', direction: 'decreases_risk', pts: '-20 risk pts', width: '45%', color: 'emerald' },
          ],
          recommended_step: row.recommended_action,
        };

        state.borrowersList.unshift(newBorrower);
        state.selected = newBorrower.id;
        state.showAppModal = false;
        state.toastMessage = `✅ Enterprise ${newBorrower.id} scored & saved to CSV!`;

        render();

        setTimeout(() => {
          state.toastMessage = '';
          render();
        }, 4000);
      } else {
        alert('Error submitting application: ' + (data.detail || 'Unknown error'));
      }
    })
    .catch((err) => {
      alert('API offline. Demo application generated locally.');
      closeAppModal();
    });
}

function getFilteredBorrowers() {
  const query = state.searchQuery.trim().toLowerCase();
  return state.borrowersList.filter((person) => {
    if (!query) return true;
    return (
      person.name.toLowerCase().includes(query) ||
      person.id.toLowerCase().includes(query) ||
      (person.account_no && person.account_no.toLowerCase().includes(query)) ||
      (person.bank_name && person.bank_name.toLowerCase().includes(query)) ||
      (person.farmer_id && person.farmer_id.toLowerCase().includes(query)) ||
      person.village.toLowerCase().includes(query) ||
      person.crop.toLowerCase().includes(query) ||
      (person.enterprise_type && person.enterprise_type.toLowerCase().includes(query)) ||
      (person.pincode && person.pincode.toString().includes(query))
    );
  });
}

function lenderView() {
  const activeNodeTag = state.activeBankNode === 'all'
    ? '🌐 Master Multi-Bank Network'
    : `🔒 Dedicated ${state.activeBankNode.toUpperCase()} Node (servers/${state.activeBankNode}_node/)`;

  const nodesHtml = (state.registeredNodes || [])
    .map((node) => {
      const code = node.code;
      const isActive = state.activeBankNode === code;
      let btnColor = 'bg-blue-600';
      if (code === 'mahb') btnColor = 'bg-amber-600';
      if (code === 'cbin') btnColor = 'bg-emerald-600';
      if (code === 'bob') btnColor = 'bg-orange-600';
      if (code === 'pnb') btnColor = 'bg-red-600';
      if (code === 'ubi') btnColor = 'bg-indigo-600';
      if (code === 'canara') btnColor = 'bg-yellow-600';
      if (code === 'mgb') btnColor = 'bg-teal-600';
      if (code === 'icici') btnColor = 'bg-cyan-600';
      if (code === 'hdfc') btnColor = 'bg-sky-600';

      return `<button onclick="selectBankNode('${code}')" class="rounded-xl px-3.5 py-2 text-xs font-bold transition-all ${
        isActive ? `${btnColor} text-white shadow-md` : 'bg-white/10 text-white hover:bg-white/20'
      }">🏦 ${node.bank_name} (${node.bank_code} | Port ${node.port})</button>`;
    })
    .join('');

  return shell(`<div class="mx-auto grid max-w-7xl gap-6 px-5 py-7 lg:grid-cols-[1fr_340px]">
    <section class="space-y-6">
      <div class="rounded-2xl bg-ink p-7 text-white shadow-sm">
        <div class="flex items-center justify-between">
          <p class="text-sm text-blue-200">Faculty Demo Desk · Dedicated Multi-Bank Isolated Server Architecture</p>
          <span class="rounded-full bg-blue-500/20 px-3 py-1 text-xs font-mono font-bold text-blue-200 border border-blue-400/30">${activeNodeTag}</span>
        </div>

        <div class="mt-3 flex flex-wrap items-end justify-between gap-5">
          <div>
            <h1 class="text-3xl font-bold">Rural MSME & Enterprise Credit Risk Intelligence</h1>
            <p class="mt-2 max-w-2xl text-slate-300">Authenticated Officer Desk. Switch dedicated bank node server instances below to view physically isolated applicant records.</p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <button onclick="openAppModal()" class="rounded-xl bg-leaf px-4 py-3 font-bold text-white shadow-md hover:bg-emerald-700">+ New Application Form</button>
            <a href="/v1/applications/export-csv" download class="rounded-xl border border-white/20 bg-white/10 px-4 py-3 font-bold text-white hover:bg-white/20">📥 Export Faculty CSV</a>
          </div>
        </div>

        <!-- Dedicated Multi-Bank Isolated Server Node Switcher -->
        <div class="mt-6 pt-5 border-t border-white/10 flex flex-wrap items-center gap-3">
          <span class="text-xs font-bold text-slate-300 uppercase tracking-wider">Isolated Bank Server Nodes:</span>
          <button onclick="selectBankNode('all')" class="rounded-xl px-3.5 py-2 text-xs font-bold transition-all ${state.activeBankNode === 'all' ? 'bg-white text-ink shadow-md' : 'bg-white/10 text-white hover:bg-white/20'}">🌐 All Master Files</button>
          ${nodesHtml}
        </div>
      </div>

      
      <div class="grid gap-4 sm:grid-cols-3">
        <div class="rounded-2xl bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Active Node Catalog Files</p><p class="mt-2 text-3xl font-bold text-ink">${state.borrowersList.length}</p><p class="mt-1 text-sm text-emerald-700">Isolated in Node Folder</p></div>
        <div class="rounded-2xl bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Median credit score</p><p class="mt-2 text-3xl font-bold text-ink">685</p><p class="mt-1 text-sm text-emerald-700">+14 vs previous month</p></div>
        <div class="rounded-2xl bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Climate-watch regions</p><p class="mt-2 text-3xl font-bold text-ink">2</p><p class="mt-1 text-sm text-rose-700">Requires portfolio monitoring</p></div>
      </div>
      
      <!-- Direct Officer Search Lookup Panel -->
      <div class="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h2 class="font-bold text-ink text-lg">Loan Officer Account Lookup</h2>
            <p class="text-xs text-slate-500">Enter Account Number (e.g. <code>SBIN413001001</code>, <code>MAHB413001002</code>, <code>CBIN413001003</code>), Entrepreneur Name, or Business Type</p>
          </div>
          <span class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">${state.borrowersList.length} Entrepreneurs Ready</span>
        </div>

        <div class="mt-4 flex flex-col sm:flex-row items-center gap-3">
          <div class="relative w-full">
            <input type="text" id="officer-search-input" value="${state.searchQuery || ''}" oninput="onOfficerSearch(this.value)" placeholder="Type Account Number (e.g. SBIN413001001), Business Name or Kirana Store..." class="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3.5 pl-11 text-base text-slate-900 font-semibold focus:border-leaf focus:bg-white focus:outline-none shadow-inner" />
            <span class="absolute left-4 top-4 text-slate-400 text-base">🔍</span>
            ${state.searchQuery ? `<button onclick="clearSearch()" class="absolute right-3.5 top-3 rounded-full bg-slate-200 px-3 py-1 text-xs font-bold text-slate-600 hover:bg-slate-300">Clear</button>` : ''}
          </div>
        </div>
      </div>
      
      <!-- Full Underwriting Card -->
      <div id="detail" class="rounded-2xl bg-white p-7 shadow-sm border border-slate-100"></div>
    </section>
    
    <aside class="rounded-2xl bg-white p-6 shadow-sm">
      <h2 class="font-bold text-ink">Review guardrails</h2>
      <ol class="mt-4 space-y-4 text-sm text-slate-600">
        <li><b class="mr-2 text-leaf">01</b>Confirm consent before opening financial data.</li>
        <li><b class="mr-2 text-leaf">02</b>Use score as a review signal, never an automatic denial.</li>
        <li><b class="mr-2 text-leaf">03</b>Explain only approved, borrower-actionable reasons.</li>
        <li><b class="mr-2 text-leaf">04</b>Offer correction and human escalation.</li>
      </ol>
      <div class="mt-7 rounded-xl bg-emerald-50 p-4">
        <p class="text-xs font-bold uppercase tracking-wider text-leaf">Graph signal</p>
        <p class="mt-2 text-sm text-slate-600">Disabled by default. The current GraphSAGE research model did not pass the validation gate.</p>
      </div>
      ${policyPanel()}
      ${securityPanel()}
    </aside>
  </div>`);
}

function detailCard(id) {
  const person = state.borrowersList.find((item) => item.id === id || item.account_no === id) || state.borrowersList[0];
  if (!person) return '';

  const reasonsHtml = (person.reasons || [])
    .map((r) => {
      const isInc = r.direction === 'increases_risk' || (r.contribution_log_odds && r.contribution_log_odds > 0);
      const label = r.feature ? r.feature.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : r.message;
      const pts = r.pts || (isInc ? `+${Math.round((r.contribution_log_odds || 1) * 20)} risk pts` : `-${Math.round(Math.abs(r.contribution_log_odds || 1) * 15)} risk pts`);
      const width = r.width || (isInc ? '75%' : '40%');
      const color = isInc ? 'rose' : 'emerald';

      return `<div>
        <div class="flex justify-between text-sm">
          <span>${r.message || label}</span>
          <b class="${color === 'rose' ? 'text-rose-600' : 'text-emerald-600'}">${pts}</b>
        </div>
        <div class="mt-1 h-2 rounded bg-slate-100">
          <div class="h-2 rounded ${color === 'rose' ? 'bg-rose-500' : 'bg-emerald-500'}" style="width: ${width}"></div>
        </div>
      </div>`;
    })
    .join('');

  return `<div class="flex flex-wrap items-start justify-between gap-4">
    <div>
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-leaf">Rural Entrepreneur Card · ${person.id}</span>
        <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-mono font-bold text-slate-800">${person.account_no || person.id}</span>
        ${person.ifsc_code ? `<span class="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-mono text-blue-700">${person.ifsc_code}</span>` : ''}
        ${person.requested_docs ? `<span class="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">📄 Docs Requested</span>` : ''}
        ${person.node_server ? `<span class="rounded-full bg-purple-100 px-2.5 py-1 text-xs font-mono text-purple-800 font-bold">${person.node_server}</span>` : ''}
      </div>
      <h2 class="mt-2 text-3xl font-bold text-ink">${person.name}</h2>
      <p class="mt-1 text-sm text-slate-500">${person.bank_name ? `<b>${person.bank_name}</b> (${person.branch_name})` : person.village} · <span class="font-semibold text-slate-700">${person.enterprise_type || person.crop}</span> ${person.pincode ? `(PIN: ${person.pincode})` : ''}</p>
    </div>
    <div class="text-right">
      <p class="text-4xl font-bold text-ink">${person.score}</p>
      <div class="mt-1">${badge(person.band)}</div>
      <p class="mt-1.5 text-xs text-slate-500 font-semibold">Risk probability ${person.pd}</p>
    </div>
  </div>
  
  <!-- 24-Month Repayment Behavioral History Card -->
  <div class="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
    <div class="flex items-center justify-between border-b border-slate-200/80 pb-3">
      <div>
        <h3 class="font-bold text-ink text-xs uppercase tracking-wider">24-Month Repayment Behavioral Track Record</h3>
        <p class="text-xs text-slate-500">Continuous payment history ingested via Account Aggregator, BBPS & Credit Bureau</p>
      </div>
      <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">${person.on_time_payment_pct_24m || '95%'} On-Time</span>
    </div>

    <div class="mt-4 grid gap-3 sm:grid-cols-4 text-xs">
      <div class="rounded-xl bg-white p-3 border border-slate-200/80 shadow-2xs">
        <span class="text-slate-500 font-medium block">24M Punctuality</span>
        <b class="text-base font-bold text-ink">${person.on_time_payment_pct_24m || '95%'}</b>
      </div>
      <div class="rounded-xl bg-white p-3 border border-slate-200/80 shadow-2xs">
        <span class="text-slate-500 font-medium block">12M NACH Bounces</span>
        <b class="text-base font-bold ${person.nach_bounces_12m > 0 ? 'text-rose-600' : 'text-emerald-600'}">${person.nach_bounces_12m !== undefined ? person.nach_bounces_12m : 0} Bounces</b>
      </div>
      <div class="rounded-xl bg-white p-3 border border-slate-200/80 shadow-2xs">
        <span class="text-slate-500 font-medium block">Avg Delay (Days)</span>
        <b class="text-base font-bold text-ink">${person.avg_payment_delay_days || '0.0'} Days</b>
      </div>
      <div class="rounded-xl bg-white p-3 border border-slate-200/80 shadow-2xs">
        <span class="text-slate-500 font-medium block">BBPS Utility Compliance</span>
        <b class="text-base font-bold text-ink">${person.bbps_utility_compliance_pct || '96%'}</b>
      </div>
    </div>

    <div class="mt-3 flex items-center justify-between text-xs text-slate-700 bg-white p-3 rounded-xl border border-slate-200/80 font-mono">
      <span class="font-sans font-medium text-slate-600">12-Month DPD Track (Days Past Due):</span>
      <span class="font-bold tracking-widest text-ink">${person.dpd_trail_12m || '0-0-0-0-0-0-0-0-0-0-0-0'}</span>
    </div>
  </div>

  <div class="mt-6 grid gap-6 md:grid-cols-2">
    <div>
      <h3 class="font-bold text-ink text-base">TreeSHAP Score Explanation</h3>
      <p class="mt-1 text-xs text-slate-500">Key enterprise feature contributions driving credit evaluation.</p>
      <div class="mt-4 space-y-3.5">
        ${reasonsHtml || '<p class="text-sm text-slate-500">No score explanations recorded for this profile.</p>'}
      </div>
    </div>
    
    <div class="rounded-2xl bg-slate-50 p-6 flex flex-col justify-between border border-slate-200">
      <div>
        <h3 class="font-bold text-ink text-base">Recommended Underwriter Step</h3>
        <p class="mt-2 text-sm leading-6 text-slate-700 font-medium">${person.recommended_step || 'Request updated trade receipts and discuss a working capital repayment plan.'}</p>
      </div>
      <div class="mt-6 flex flex-wrap gap-3">
        <button onclick="openDocRequestModal('${person.id}')" class="rounded-xl bg-ink px-4 py-2.5 text-sm font-bold text-white shadow-md hover:bg-slate-800 transition-all duration-200 cursor-pointer">📄 Request Business Documents</button>
        <button onclick="openBorrowerExplanation('${person.id}')" class="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-100 hover:border-slate-400 transition-all duration-200 cursor-pointer">💬 Open Borrower Explanation</button>
      </div>
    </div>
  </div>`;
}

function adminView() {
  const security = state.security || {};
  const ledger = security.audit_ledger || {};
  const scopes = security.role_scopes || {};
  const roleCards =
    Object.entries(scopes)
      .map(
        ([role, values]) =>
          `<div class="rounded-xl border border-slate-200 p-4"><p class="font-bold capitalize text-ink">${role.replace('_', ' ')}</p><p class="mt-2 text-xs leading-5 text-slate-500">${values.join(
            ' · '
          )}</p></div>`
      )
      .join('') || '<p class="text-sm text-slate-500">Loading role permissions…</p>';
  const ledgerGood = ledger.valid === true;
  return shell(`<div class="mx-auto max-w-7xl px-5 py-7"><section class="rounded-3xl bg-gradient-to-br from-ink to-slate-800 p-7 text-white shadow-sm"><div class="flex flex-wrap items-start justify-between gap-5"><div><p class="text-sm text-blue-200">Phase 8 · read-only sandbox administration</p><h1 class="mt-2 text-3xl font-bold">Integration security control room</h1><p class="mt-2 max-w-2xl text-slate-300">Monitor the synthetic partner boundary, roles, and audit controls without exposing secrets, customer data, or privileged actions in a browser.</p></div><div class="rounded-2xl bg-white/10 px-4 py-3 text-sm"><b class="block text-white">Live partner links</b><span class="text-blue-100">Disabled</span></div></div></section><div class="mt-6 grid gap-4 md:grid-cols-3"><div class="rounded-2xl bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Audit-ledger integrity</p><p class="mt-2 text-2xl font-bold ${
    ledgerGood ? 'text-emerald-700' : 'text-amber-700'
  }">${ledger.status || 'Loading…'}</p><p class="mt-1 text-sm text-slate-500">${ledger.entries || 0} minimised events</p></div><div class="rounded-2xl bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Partner webhooks</p><p class="mt-2 text-2xl font-bold text-ink">Signed only</p><p class="mt-1 text-sm text-slate-500">Synthetic HMAC simulation</p></div><div class="rounded-2xl bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Rate limiting</p><p class="mt-2 text-2xl font-bold text-ink">${
    security.rate_limit?.requests || '–'
  } requests</p><p class="mt-1 text-sm text-slate-500">per ${
    security.rate_limit?.window_seconds || '–'
  } seconds</p></div></div><div class="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]"><section class="rounded-2xl bg-white p-6 shadow-sm"><div class="flex flex-wrap items-center justify-between gap-3"><div><h2 class="font-bold text-ink">Role access matrix</h2><p class="mt-1 text-sm text-slate-500">Each role receives only the minimum sandbox scopes needed for its task.</p></div><span class="rounded-full bg-emerald-50 px-3 py-2 text-xs font-bold text-leaf">Role-limited tokens</span></div><div class="mt-5 grid gap-3 sm:grid-cols-3">${roleCards}</div><div class="mt-6 rounded-xl bg-slate-50 p-4"><p class="text-sm font-bold text-ink">Admin-only controls</p><p class="mt-1 text-sm leading-6 text-slate-600">Signed partner-webhook acceptance, audit-integrity checks, and expired synthetic-metadata retention require an admin token at the API. This read-only screen does not expose client secrets or trigger those actions.</p></div></section><aside class="rounded-2xl bg-white p-6 shadow-sm"><h2 class="font-bold text-ink">Deployment boundary</h2><ul class="mt-4 space-y-3 text-sm leading-6 text-slate-600"><li><b class="text-rose-600">✕</b> No real UPI, AA, FIU, or lender connection</li><li><b class="text-rose-600">✕</b> No real borrower or account data</li><li><b class="text-rose-600">✕</b> No production secret manager or external penetration test</li><li><b class="text-emerald-600">✓</b> Synthetic signed-webhook and audit-chain simulation</li></ul><div class="mt-6 rounded-xl bg-amber-50 p-4"><p class="text-xs font-bold uppercase tracking-wider text-amber-800">Next real-world gate</p><p class="mt-2 text-sm text-amber-900">A regulated partner and independent security review are required before any controlled shadow pilot.</p></div></aside></div></div>`);
}

function borrowerView() {
  const text = copy[state.language];
  const person = state.borrowersList.find((b) => b.id === state.selected || b.account_no === state.selected) || state.borrowersList[0];

  return shell(`<div class="mx-auto max-w-4xl px-5 py-8 space-y-6">
    <!-- Header Banner -->
    <div class="rounded-3xl bg-gradient-to-br from-leaf to-emerald-800 p-7 text-white shadow-lg">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="text-xs font-bold uppercase tracking-wider text-emerald-100">Vridhi Sahayak · Rural Entrepreneur Self-Service Portal</p>
          <h1 class="mt-1 text-3xl font-bold">Check your credit score & pre-approved limit</h1>
          <p class="mt-1.5 max-w-xl text-sm text-emerald-100">Clear business credit information, in your own language. Free & privacy-first.</p>
        </div>
        <div class="flex items-center gap-2 rounded-2xl bg-white/10 p-3 backdrop-blur-sm">
          <span class="text-xs font-semibold text-emerald-100">Language:</span>
          <select onchange="setLanguage(this.value)" class="rounded-lg border-0 bg-white px-3 py-1.5 font-bold text-slate-800 text-sm focus:outline-none">
            <option ${state.language === 'English' ? 'selected' : ''}>English</option>
            <option ${state.language === 'हिंदी' ? 'selected' : ''}>हिंदी</option>
            <option ${state.language === 'मराठी' ? 'selected' : ''}>मराठी</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Quick Borrower Score Lookup -->
    <div class="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h2 class="font-bold text-ink text-lg">Enter Your Account Number to Check Score</h2>
          <p class="text-xs text-slate-500">Try <code>SBIN413001001</code>, <code>MAHB413001002</code>, <code>CBIN413001003</code>, or your name</p>
        </div>
        <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">Instant Verification</span>
      </div>

      <div class="mt-4 flex flex-col sm:flex-row items-center gap-3">
        <input type="text" id="borrower-search-input" value="${state.searchQuery || ''}" oninput="onBorrowerSearch(this.value)" placeholder="Type Account Number (e.g. SBIN413001001) or Ramesh Pawar..." class="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3.5 text-base font-semibold text-slate-900 focus:border-leaf focus:bg-white focus:outline-none shadow-inner" />
      </div>
    </div>

    <!-- Active Borrower Score Card -->
    ${person ? `<div class="rounded-2xl bg-white p-6 shadow-sm border border-slate-100 space-y-5">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span class="text-xs font-bold uppercase tracking-wider text-leaf">Verified Applicant Profile</span>
          <h2 class="mt-1 text-2xl font-bold text-ink">${person.name}</h2>
          <p class="text-sm text-slate-500">${person.bank_name ? `<b>${person.bank_name}</b> (${person.branch_name})` : person.village} · <span class="font-bold text-slate-800">${person.enterprise_type || person.crop}</span></p>
        </div>
        <div class="text-right">
          <p class="text-4xl font-extrabold text-leaf">${person.score}</p>
          <div class="mt-1">${badge(person.band)}</div>
        </div>
      </div>

      <!-- Actionable Score Tips -->
      <div class="rounded-xl bg-slate-50 p-4 border border-slate-200/80">
        <p class="text-xs font-bold uppercase tracking-wider text-ink">💡 How to Improve Your Business Credit Score</p>
        <ul class="mt-2 space-y-2 text-xs text-slate-700">
          <li class="flex items-center gap-2"><span class="text-emerald-600 font-bold">✓</span> Pay commercial electricity bills before the 5th of every month (+25 points boost)</li>
          <li class="flex items-center gap-2"><span class="text-emerald-600 font-bold">✓</span> Maintain ₹15,000+ minimum monthly working capital in your bank account (+20 points boost)</li>
          <li class="flex items-center gap-2"><span class="text-emerald-600 font-bold">✓</span> File monthly APMC Mandi or GST sales receipts on time (+18 points boost)</li>
        </ul>
      </div>
    </div>` : ''}

    <!-- Voice Sahayak Interactive Assistant -->
    <div class="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
      <div class="rounded-2xl bg-emerald-50/70 p-5 border border-emerald-100">
        <p class="text-xs font-bold uppercase tracking-wider text-leaf">Vridhi Sahayak · AI Assistant</p>
        <h2 class="mt-2 text-xl font-bold text-ink">${person ? `${person.name}'s Credit Status Explanation` : text.title}</h2>
        <p id="assistant-answer" class="mt-3 text-sm leading-7 text-slate-700">${person ? `Hello ${person.name}, your current business credit score is ${person.score} (${person.band} Risk Band). Your account at ${person.bank_name || 'Bank'} shows an on-time payment track record of ${person.on_time_payment_pct_24m || '95%'}. ${person.recommended_step}` : text.answer}</p>
        <button onclick="speakAnswer()" class="mt-5 rounded-xl bg-leaf px-5 py-3 text-sm font-bold text-white shadow-md hover:bg-emerald-700">🔊 ${text.speak}</button>
      </div>

      <div class="mt-6">
        <label class="text-sm font-semibold text-ink">${text.ask}</label>
        <div class="mt-2 flex gap-2">
          <input id="question" class="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-leaf focus:outline-none" placeholder="Type or click microphone to speak..." />
          <button onclick="listen()" class="rounded-xl border border-leaf px-4 py-3 font-bold text-leaf hover:bg-emerald-50">🎙</button>
          <button onclick="answerQuestion()" class="rounded-xl bg-ink px-5 py-3 text-sm font-bold text-white hover:bg-slate-800">Ask</button>
        </div>
        <p id="voice-status" class="mt-2 text-xs text-slate-500">Voice capture works in Chrome/Edge browsers. Supports English, Hindi, and Marathi.</p>
      </div>
    </div>
  </div>`);
}

function onBorrowerSearch(val) {
  state.searchQuery = val;
  const filtered = getFilteredBorrowers();
  if (filtered.length) {
    state.selected = filtered[0].id;
    render();
  }
}

function setView(view) {
  if (view === 'lender' && !state.officerAuth) {
    state.showOfficerAuthModal = true;
    render();
    return;
  }
  state.view = view;
  render();
}

function render() {
  const appEl = document.getElementById('app');
  if (!appEl) return;

  if (state.view === 'gateway') {
    appEl.innerHTML = gatewayView();
  } else if (state.view === 'lender') {
    appEl.innerHTML = lenderView();
    updateDetailView();
  } else if (state.view === 'admin') {
    appEl.innerHTML = adminView();
  } else {
    appEl.innerHTML = borrowerView();
  }

  const pill = document.getElementById('api-pill');
  if (pill) {
    pill.textContent = state.api;
    pill.classList.remove('hidden');
  }
}

function updateDetailView() {
  const target = document.getElementById('detail');
  if (target) {
    target.innerHTML = detailCard(state.selected);
  }
}

function selectBorrower(id) {
  state.selected = id;
  updateDetailView();
}

function onOfficerSearch(val) {
  state.searchQuery = val;
  const filtered = getFilteredBorrowers();
  if (filtered.length) {
    state.selected = filtered[0].id;
    updateDetailView();
  } else {
    const target = document.getElementById('detail');
    if (target) {
      target.innerHTML = `<div class="p-8 text-center text-slate-500 rounded-2xl border border-dashed border-slate-300 bg-slate-50">
        <p class="text-lg font-bold text-slate-800">No applicant found matching "${val}"</p>
        <p class="mt-1 text-sm text-slate-500">Try entering a valid Account Number (e.g. <code>SBIN413001001</code>, <code>MAHB413001002</code>, <code>CBIN413001003</code>), Entrepreneur Name, or Business Type (e.g. Kirana, Dairy, Solar).</p>
      </div>`;
    }
  }
}

function clearSearch() {
  state.searchQuery = '';
  const searchInput = document.getElementById('officer-search-input');
  if (searchInput) searchInput.value = '';
  onOfficerSearch('');
}

function setLanguage(language) {
  state.language = language;
  render();
}
function answerQuestion() {
  const answer = document.getElementById('assistant-answer');
  if (answer) answer.textContent = copy[state.language].answer;
}
function speakAnswer() {
  const person = state.borrowersList.find((b) => b.id === state.selected || b.account_no === state.selected) || state.borrowersList[0];
  const textToSpeak = person
    ? `Hello ${person.name}, your current business credit score is ${person.score}. ${person.recommended_step}`
    : copy[state.language].answer;
  const message = new SpeechSynthesisUtterance(textToSpeak);
  message.lang = state.language === 'मराठी' ? 'mr-IN' : state.language === 'हिंदी' ? 'hi-IN' : 'en-IN';
  speechSynthesis.speak(message);
}
function listen() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const status = document.getElementById('voice-status');
  if (!Recognition) {
    status.textContent = 'Voice recognition is not available in this browser. Please type your question.';
    return;
  }
  const recognition = new Recognition();
  recognition.lang = state.language === 'मराठी' ? 'mr-IN' : state.language === 'हिंदी' ? 'hi-IN' : 'en-IN';
  recognition.onresult = (event) => {
    document.getElementById('question').value = event.results[0][0].transcript;
    status.textContent = 'Voice captured locally in this browser. Review before sending.';
  };
  recognition.start();
}

function loadInitialData() {
  apiFetch('/health')
    .then((response) => response.json())
    .then((info) => {
      state.api = info.model_loaded ? '● Sandbox connected' : '● Sandbox model unavailable';
      const pill = document.getElementById('api-pill');
      if (pill) pill.textContent = state.api;
    })
    .catch(() => {
      state.api = '● Demo mode';
      const pill = document.getElementById('api-pill');
      if (pill) pill.textContent = state.api;
    });

  apiFetch('/v1/borrowers')
    .then((response) => response.json())
    .then((data) => {
      if (data.borrowers && data.borrowers.length) {
        state.borrowersList = data.borrowers;
        if (!state.selected || !state.borrowersList.some((b) => b.id === state.selected)) {
          state.selected = state.borrowersList[0].id;
        }
        if (state.view === 'lender') {
          render();
        }
      }
    })
    .catch(() => {});

  apiFetch('/v1/policy/reference-summary')
    .then((response) => response.json())
    .then((info) => {
      state.policy = info;
      const policyEl = document.getElementById('policy-panel-container');
      if (policyEl) policyEl.innerHTML = policyPanel();
    })
    .catch(() => {});

  apiFetch('/v1/security/sandbox-summary')
    .then((response) => response.json())
    .then((info) => {
      state.security = info;
      const secEl = document.getElementById('security-panel-container');
      if (secEl) secEl.innerHTML = securityPanel();
    })
    .catch(() => {});

  apiFetch('/v1/bank/nodes')
    .then((res) => res.json())
    .then((data) => {
      if (data.nodes) {
        state.registeredNodes = data.nodes;
        render();
      }
    })
    .catch(() => {});
}


loadInitialData();
render();
