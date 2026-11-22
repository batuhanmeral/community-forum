// Previews show raw markdown, so `>!text!<` would be readable there. This masks it like the
// server's inline rule does: at least one character, may span single line breaks, never a
// blank line. One forward pass (no backtracking regex), so a body full of unclosed `>!`
// openers costs linear time; scanning stops past the last `!<`.
const BLANK_LINE = /\n[ \t]*\n/g;

export function maskInlineSpoilers(text: string, mask: string): string {
  const lastClose = text.lastIndexOf('!<');
  if (lastClose === -1) return text;
  let out = '';
  let emitted = 0;
  let from = 0;
  let close = -1;
  let blank = -2;
  for (;;) {
    const open = text.indexOf('>!', from);
    if (open === -1 || open + 3 > lastClose) break;
    if (close < open + 3) close = text.indexOf('!<', open + 3);
    if (close === -1) break;
    if (blank !== -1 && blank < open + 2) {
      BLANK_LINE.lastIndex = open + 2;
      blank = BLANK_LINE.exec(text)?.index ?? -1;
    }
    if (blank !== -1 && blank < close) {
      from = open + 2;
      continue;
    }
    out += text.slice(emitted, open) + mask;
    emitted = from = close + 2;
  }
  return out + text.slice(emitted);
}
