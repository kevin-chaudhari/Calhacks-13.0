"use client";

import { Languages, Mic, MicOff, Send, Square, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { time } from "@/lib/format";
import type { ChatMessage } from "@/lib/types";
import { LANGUAGES, short, speak, speechSupported, stopSpeaking, translate, useSpeechToText } from "@/lib/voice";
import { Avatar, Button, Card, CardHeader, Chip, cx } from "@/components/ui/primitives";

const LANG_KEY = "rally.chat.lang";

function initials(name: string) {
  return name.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
}

function Bubble({ m, mine, myLang, token, autoTranslate }: { m: ChatMessage; mine: boolean; myLang: string; token?: string | null; autoTranslate: boolean }) {
  const [tr, setTr] = useState<{ text: string; engine: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState<"orig" | "tr" | null>(null);
  const foreign = short(m.lang) !== short(myLang);

  async function doTranslate() {
    setBusy(true);
    setErr(null);
    try {
      setTr(await translate(m.text, m.lang, myLang, token));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (autoTranslate && foreign && !mine && !tr && !busy && !err) doTranslate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoTranslate, foreign, mine, myLang]);

  const say = (which: "orig" | "tr") => {
    if (speaking === which) {
      stopSpeaking();
      setSpeaking(null);
      return;
    }
    const ok = which === "orig" ? speak(m.text, m.lang, () => setSpeaking(null)) : speak(tr!.text, myLang, () => setSpeaking(null));
    if (ok) setSpeaking(which);
  };

  return (
    <li className={cx("flex gap-2.5", mine && "flex-row-reverse")}>
      <Avatar initials={initials(m.authorName)} size={28} />
      <div className={cx("max-w-[82%] min-w-0", mine && "text-right")}>
        <div className={cx("flex flex-wrap items-center gap-1.5 text-[12px] text-muted", mine && "justify-end")}>
          <span className="font-medium text-ink">{m.authorName}</span>
          {m.authorRole === "vendor" && <Chip tone="sim">{m.authorTitle || "Vendor"}</Chip>}
          {m.viaVoice && <span title="Dictated by voice" className="inline-flex items-center gap-0.5"><Mic size={11} /> voice</span>}
          {foreign && <span className="font-mono">{short(m.lang)}</span>}
          <span className="font-mono">{time(m.at)}</span>
        </div>
        <div className={cx("mt-1 inline-block rounded-[10px] px-3 py-2 text-left text-[14px] leading-5", mine ? "bg-accent text-accent-ink" : "bg-surface-2")}>
          {m.text}
        </div>
        {tr && (
          <div className="mt-1 rounded-[8px] border border-line px-3 py-1.5 text-left text-[13px]">
            <span className="mr-1 font-mono text-[11px] text-muted">{short(myLang)} · {tr.engine}</span>
            {tr.text}
            {speechSupported() && (
              <button onClick={() => say("tr")} className="ml-2 inline-flex align-middle text-muted hover:text-ink" aria-label="Read translation aloud">
                {speaking === "tr" ? <Square size={12} /> : <Volume2 size={13} />}
              </button>
            )}
          </div>
        )}
        {err && <div className="mt-1 text-[12px] text-danger">{err}</div>}
        <div className={cx("mt-1 flex gap-2 text-[12px] text-muted", mine && "justify-end")}>
          {speechSupported() && (
            <button onClick={() => say("orig")} className="inline-flex items-center gap-1 hover:text-ink" aria-label="Read aloud">
              {speaking === "orig" ? <Square size={12} /> : <Volume2 size={12} />} {speaking === "orig" ? "Stop" : "Listen"}
            </button>
          )}
          {foreign && !tr && (
            <button onClick={doTranslate} disabled={busy} className="inline-flex items-center gap-1 hover:text-ink">
              <Languages size={12} /> {busy ? "Translating…" : `Translate to ${LANGUAGES.find((l) => l.code === myLang)?.label ?? myLang}`}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

export function ChatPanel({
  title, meta, messages, meId, canSend, disabledReason, onSend, token, defaultAutoRead = false,
}: {
  title: string;
  meta?: React.ReactNode;
  messages: ChatMessage[];
  meId?: string;
  canSend: boolean;
  disabledReason?: string;
  onSend: (text: string, lang: string, viaVoice: boolean) => Promise<void>;
  token?: string | null;
  defaultAutoRead?: boolean;
}) {
  const [lang, setLang] = useState<string>("en-US");
  const [text, setText] = useState("");
  const [viaVoice, setViaVoice] = useState(false);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [autoRead, setAutoRead] = useState(defaultAutoRead);
  const [autoTranslate, setAutoTranslate] = useState(true);
  const seen = useRef<number>(messages.length);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LANG_KEY);
      if (saved) setLang(saved);
    } catch {}
  }, []);
  const changeLang = (l: string) => {
    setLang(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {}
  };

  const stt = useSpeechToText(lang, (finalText) => {
    if (!finalText) return;
    setText((t) => (t ? t + " " : "") + finalText);
    setViaVoice(true);
  });

  // read new incoming messages aloud
  useEffect(() => {
    if (messages.length > seen.current) {
      const fresh = messages.slice(seen.current).filter((m) => m.authorId !== meId);
      if (autoRead && fresh.length) speak(fresh.map((m) => `${m.authorName} says: ${m.text}`).join(". "), fresh[fresh.length - 1].lang);
      seen.current = messages.length;
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, autoRead, meId]);

  async function send() {
    const t = (text + (stt.interim ? " " + stt.interim : "")).trim();
    if (!t || sending) return;
    if (stt.listening) stt.stop();
    setSending(true);
    setErr(null);
    try {
      await onSend(t, lang, viaVoice);
      setText("");
      setViaVoice(false);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="flex flex-col">
      <CardHeader
        title={title}
        meta={meta}
        action={
          <label className="flex items-center gap-1.5 text-[12px] text-muted">
            <Languages size={13} />
            <select aria-label="My language" value={lang} onChange={(e) => changeLang(e.target.value)} className="h-7 rounded-[6px] border border-line bg-surface px-1.5 text-[12px] text-ink">
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </label>
        }
      />
      <div className="flex flex-wrap gap-3 border-b border-line px-5 py-2 text-[12px] text-muted">
        <label className="inline-flex items-center gap-1.5"><input type="checkbox" checked={autoRead} onChange={(e) => setAutoRead(e.target.checked)} className="accent-[var(--accent)]" /> Read new messages aloud</label>
        <label className="inline-flex items-center gap-1.5"><input type="checkbox" checked={autoTranslate} onChange={(e) => setAutoTranslate(e.target.checked)} className="accent-[var(--accent)]" /> Auto-translate to my language</label>
      </div>
      <ol ref={listRef} className="max-h-[420px] min-h-[160px] space-y-4 overflow-y-auto px-5 py-4" aria-live="polite">
        {messages.length === 0 && <li className="py-8 text-center text-[13px] text-muted">No messages yet. Say hello, by typing or with the mic.</li>}
        {messages.map((m) => (
          <Bubble key={m.id} m={m} mine={m.authorId === meId} myLang={lang} token={token} autoTranslate={autoTranslate} />
        ))}
      </ol>
      <div className="border-t border-line p-3">
        {stt.listening && (
          <div className="mb-2 flex items-center gap-2 text-[12px] text-accent" role="status">
            <span className="h-2 w-2 animate-pulse rounded-full bg-danger" /> Listening in {LANGUAGES.find((l) => l.code === lang)?.label}…
            {stt.interim && <span className="truncate text-muted">“{stt.interim}”</span>}
          </div>
        )}
        {(stt.error || err) && <div className="mb-2 text-[12px] text-danger">{stt.error || err}</div>}
        <div className="flex items-end gap-2">
          <button
            onClick={stt.listening ? stt.stop : stt.start}
            disabled={!canSend || !stt.supported}
            title={stt.supported ? (stt.listening ? "Stop dictation" : "Dictate (speech to text)") : "Voice input needs Chrome or Edge"}
            aria-label={stt.listening ? "Stop dictation" : "Start dictation"}
            className={cx(
              "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[6px] border disabled:opacity-40",
              stt.listening ? "border-danger bg-danger-soft text-danger" : "border-line bg-surface text-muted hover:text-ink",
            )}
          >
            {stt.listening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            disabled={!canSend}
            placeholder={canSend ? "Type, or tap the mic and speak" : disabledReason}
            aria-label="Message"
            className="min-h-9 flex-1 resize-none rounded-[6px] border border-line bg-surface px-3 py-2 text-[14px] outline-none focus:border-accent disabled:opacity-60"
          />
          <Button onClick={send} disabled={!canSend || sending || !(text.trim() || stt.interim)} aria-label="Send">
            <Send size={15} />
          </Button>
        </div>
      </div>
    </Card>
  );
}
