/** Minimal WebSocket stand-in: tests drive the server side (open, receive, drop). */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  static reset() {
    FakeWebSocket.instances = [];
  }

  static get last(): FakeWebSocket {
    const socket = FakeWebSocket.instances.at(-1);
    if (!socket) throw new Error('no socket was opened');
    return socket;
  }

  readyState = 0;
  sent: string[] = [];
  closedWith: number | null = null;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close(code = 1000) {
    this.closedWith = code;
    this.readyState = 3;
  }

  // ─── server side ───

  open() {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  receive(data: unknown) {
    const text = typeof data === 'string' ? data : JSON.stringify(data);
    this.onmessage?.({ data: text } as MessageEvent);
  }

  drop(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }

  sentJson(): unknown[] {
    return this.sent.map((s) => JSON.parse(s));
  }
}

/** Open the last socket and let the server accept the auth frame. */
export function acceptLastSocket() {
  FakeWebSocket.last.open();
  FakeWebSocket.last.receive({ type: 'ready' });
}
