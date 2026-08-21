import {
  cvm,
  storage,
  themeGet,
  themeOnChanged,
  type CvmServer,
  type CvmServerRef,
  type McpTool,
  type McpToolResult,
  type Subscription,
  type Theme,
} from '@napplet/sdk';
import './styles.css';

type StatusKind = 'idle' | 'ok' | 'warn' | 'error';
type RememberedTotem = CvmServerRef & { name?: string; description?: string };
type RuntimeWindow = Window & {
  napplet?: { storage?: unknown; theme?: unknown };
};

const REMEMBERED_KEY = 'remembered-totem-v1';
const FALLBACK_THEME: Theme = {
  colors: { background: '#ecebe4', text: '#17221b', primary: '#c5532d' },
};
const runtimeWindow = window as RuntimeWindow;

const elements = {
  status: requireElement<HTMLOutputElement>('#status'),
  discoverForm: requireElement<HTMLFormElement>('#discoverForm'),
  discoverButton: requireElement<HTMLButtonElement>('#discoverButton'),
  searchInput: requireElement<HTMLInputElement>('#searchInput'),
  serverCount: requireElement<HTMLSpanElement>('#serverCount'),
  serverList: requireElement<HTMLDivElement>('#serverList'),
  selectedServer: requireElement<HTMLParagraphElement>('#selectedServer'),
  rememberButton: requireElement<HTMLButtonElement>('#rememberButton'),
  toolList: requireElement<HTMLDivElement>('#toolList'),
  toolName: requireElement<HTMLSpanElement>('#toolName'),
  argumentsInput: requireElement<HTMLTextAreaElement>('#argumentsInput'),
  runButton: requireElement<HTMLButtonElement>('#runButton'),
  output: requireElement<HTMLPreElement>('#output'),
};

let themeSubscription: Subscription | null = null;
let selectedServer: CvmServer | null = null;
let selectedTool: McpTool | null = null;

function requireElement<T extends HTMLElement>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element;
}

function setStatus(kind: StatusKind, message: string): void {
  elements.status.className = `status status-${kind}`;
  elements.status.textContent = message;
}

function setOutput(value: unknown): void {
  elements.output.textContent =
    typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

async function withTimeout<T>(
  promise: Promise<T>,
  label: string,
  timeoutMs = 5000,
): Promise<T> {
  let timer = 0;
  const timeout = new Promise<T>((_, reject) => {
    timer = window.setTimeout(() => {
      reject(new Error(`${label} did not resolve within ${timeoutMs}ms`));
    }, timeoutMs);
  });

  try {
    return await Promise.race([promise, timeout]);
  } finally {
    window.clearTimeout(timer);
  }
}

function shortPubkey(pubkey: string): string {
  return pubkey.length <= 20 ? pubkey : `${pubkey.slice(0, 10)}…${pubkey.slice(-8)}`;
}

function serverLabel(server: CvmServerRef & { name?: string }): string {
  return server.name?.trim() || `Totem ${shortPubkey(server.pubkey)}`;
}

function renderServers(servers: CvmServer[]): void {
  elements.serverCount.textContent = `${servers.length} found`;
  if (servers.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'No Totem services matched. Check that the shell has a ContextVM route to a nearby Totem.';
    elements.serverList.replaceChildren(empty);
    return;
  }

  const cards = servers.map((server) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'server-card';
    button.setAttribute('role', 'listitem');

    const name = document.createElement('strong');
    name.textContent = serverLabel(server);
    const description = document.createElement('span');
    description.textContent = server.description?.trim() || 'Totem ContextVM service';
    const identity = document.createElement('code');
    identity.textContent = shortPubkey(server.pubkey);
    button.append(name, description, identity);
    button.addEventListener('click', () => handleAction(() => selectServer(server)));
    return button;
  });
  elements.serverList.replaceChildren(...cards);
}

async function discoverServers(): Promise<void> {
  setStatus('idle', 'Scanning services');
  setBusy(true);
  try {
    const search = elements.searchInput.value.trim() || 'Totem';
    const discovered = await withTimeout(
      cvm.discover({ search, limit: 24 }),
      'cvm.discover',
      12_000,
    );
    const remembered = await readRememberedServer();
    const servers = remembered && !discovered.some((server) => server.pubkey === remembered.pubkey)
      ? [remembered, ...discovered]
      : discovered;
    renderServers(servers);
    setStatus(servers.length ? 'ok' : 'warn', servers.length ? 'Totems found' : 'No Totems found');
  } finally {
    setBusy(false);
  }
}

async function selectServer(server: CvmServer): Promise<void> {
  selectedServer = server;
  selectedTool = null;
  elements.selectedServer.textContent = `${serverLabel(server)} · ${shortPubkey(server.pubkey)}`;
  elements.rememberButton.hidden = !runtimeWindow.napplet?.storage;
  elements.toolName.textContent = 'Loading tools';
  elements.argumentsInput.disabled = true;
  elements.runButton.disabled = true;
  setStatus('idle', 'Reading Totem tools');

  const tools = await withTimeout(
    cvm.listTools(server, { initialize: true, timeoutMs: 12_000, payment: 'deny' }),
    'cvm.listTools',
    14_000,
  );
  renderTools(tools);
  setStatus(tools.length ? 'ok' : 'warn', tools.length ? 'Tools ready' : 'Totem has no tools');
}

function renderTools(tools: McpTool[]): void {
  if (tools.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'This Totem did not advertise any MCP tools.';
    elements.toolList.replaceChildren(empty);
    elements.toolName.textContent = 'No tools available';
    return;
  }

  const buttons = tools.map((tool) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tool-card';
    button.setAttribute('role', 'listitem');
    const name = document.createElement('strong');
    name.textContent = tool.name;
    const description = document.createElement('span');
    description.textContent = tool.description?.trim() || 'No description advertised';
    button.append(name, description);
    button.addEventListener('click', () => chooseTool(tool, button));
    return button;
  });
  elements.toolList.replaceChildren(...buttons);
}

function chooseTool(tool: McpTool, button: HTMLButtonElement): void {
  selectedTool = tool;
  for (const candidate of elements.toolList.querySelectorAll<HTMLButtonElement>('button')) {
    candidate.dataset.selected = String(candidate === button);
  }
  elements.toolName.textContent = tool.name;
  elements.argumentsInput.value = JSON.stringify(argumentTemplate(tool), null, 2);
  elements.argumentsInput.disabled = false;
  elements.runButton.disabled = false;
  elements.output.textContent = tool.description || 'Ready to run.';
  elements.argumentsInput.focus();
}

function argumentTemplate(tool: McpTool): Record<string, unknown> {
  const template: Record<string, unknown> = {};
  for (const name of tool.inputSchema.required ?? []) {
    const schema = tool.inputSchema.properties?.[name];
    template[name] = defaultForSchema(schema);
  }
  return template;
}

function defaultForSchema(schema: unknown): unknown {
  if (typeof schema !== 'object' || schema === null) return '';
  const record = schema as Record<string, unknown>;
  if ('default' in record) return record.default;
  if (record.type === 'boolean') return false;
  if (record.type === 'number' || record.type === 'integer') return 0;
  if (record.type === 'array') return [];
  if (record.type === 'object') return {};
  return '';
}

function parseArguments(): Record<string, unknown> {
  const value: unknown = JSON.parse(elements.argumentsInput.value || '{}');
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Arguments must be a JSON object.');
  }
  return value as Record<string, unknown>;
}

async function runTool(): Promise<void> {
  if (!selectedServer || !selectedTool) throw new Error('Choose a Totem and tool first.');
  setStatus('idle', `Running ${selectedTool.name}`);
  elements.runButton.disabled = true;
  try {
    const result = await withTimeout(
      cvm.callTool(selectedServer, selectedTool.name, parseArguments(), {
        initialize: true,
        timeoutMs: 30_000,
        payment: 'prompt',
      }),
      `cvm.callTool ${selectedTool.name}`,
      32_000,
    );
    setOutput(formatToolResult(result));
    setStatus(result.isError ? 'error' : 'ok', result.isError ? 'Totem reported an error' : 'Tool complete');
  } finally {
    elements.runButton.disabled = false;
  }
}

function formatToolResult(result: McpToolResult): unknown {
  if (result.content.length === 1 && result.content[0]?.type === 'text') {
    const text = result.content[0].text ?? '';
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return result;
}

async function rememberServer(): Promise<void> {
  if (!selectedServer || !runtimeWindow.napplet?.storage) return;
  const remembered: RememberedTotem = {
    pubkey: selectedServer.pubkey,
    relays: selectedServer.relays,
    name: selectedServer.name,
    description: selectedServer.description,
  };
  await withTimeout(storage.setItem(REMEMBERED_KEY, JSON.stringify(remembered)), 'storage.setItem');
  elements.rememberButton.textContent = 'Remembered';
  setStatus('ok', 'Totem remembered');
}

async function readRememberedServer(): Promise<RememberedTotem | null> {
  if (!runtimeWindow.napplet?.storage) return null;
  const raw = await withTimeout(storage.getItem(REMEMBERED_KEY), 'storage.getItem', 3000).catch(() => null);
  if (!raw) return null;
  try {
    const remembered = JSON.parse(raw) as RememberedTotem;
    if (!remembered.pubkey || typeof remembered.pubkey !== 'string') return null;
    return remembered;
  } catch {
    await storage.removeItem(REMEMBERED_KEY).catch(() => undefined);
    return null;
  }
}

function applyTheme(theme: Theme): void {
  const { background, text, primary } = theme.colors;
  const root = document.documentElement;
  root.style.setProperty('--page', background);
  root.style.setProperty('--ink', text);
  root.style.setProperty('--accent', primary);
  root.style.setProperty('--surface', `color-mix(in srgb, ${background} 88%, ${text})`);
  root.style.setProperty('--surface-strong', `color-mix(in srgb, ${background} 78%, ${text})`);
  root.style.setProperty('--border', `color-mix(in srgb, ${text} 22%, ${background})`);
  root.style.setProperty('--muted', `color-mix(in srgb, ${text} 62%, ${background})`);
  root.style.backgroundColor = background;
  document.body.style.backgroundColor = background;
  document.body.style.color = text;
  elements.output.style.backgroundColor = `color-mix(in srgb, ${text} 92%, ${background})`;
  elements.output.style.color = background;
}

async function initializeTheme(): Promise<void> {
  applyTheme(FALLBACK_THEME);
  if (!runtimeWindow.napplet?.theme) return;
  applyTheme(await withTimeout(themeGet(), 'theme.get', 4000));
  themeSubscription = themeOnChanged(applyTheme);
}

function setBusy(busy: boolean): void {
  elements.discoverButton.disabled = busy;
  elements.searchInput.disabled = busy;
}

function handleAction(action: () => Promise<void>): void {
  action().catch((error: unknown) => {
    setStatus('error', 'Action failed');
    setOutput(error instanceof Error ? error.message : error);
  });
}

elements.discoverForm.addEventListener('submit', (event) => {
  event.preventDefault();
  handleAction(discoverServers);
});
elements.rememberButton.addEventListener('click', () => handleAction(rememberServer));
elements.runButton.addEventListener('click', () => handleAction(runTool));

window.addEventListener('beforeunload', () => {
  themeSubscription?.close();
  if (selectedServer) void cvm.close(selectedServer).catch(() => undefined);
});

setOutput('Scan for a Totem, then choose one of its advertised tools.');
void initializeTheme().catch(() => applyTheme(FALLBACK_THEME));
