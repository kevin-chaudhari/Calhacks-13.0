"use client";

// Voice and translation helpers. Everything runs in the browser:
//  - Speech to text: Web Speech API (SpeechRecognition). Chrome and Edge; audio is processed by the
//    browser vendor's speech service, so it needs a network connection.
//  - Text to speech: speechSynthesis with a voice matching the language. All modern browsers.
//  - Translation: Chrome's on-device Translator API when present, else the HuddleUp API (Gemini, if a key
//    is configured). If neither is available the UI says so instead of pretending.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

export const LANGUAGES = [
  { code: "en-US", label: "English" },
  { code: "es-ES", label: "Español" },
  { code: "hi-IN", label: "हिन्दी" },
  { code: "zh-CN", label: "中文" },
  { code: "fr-FR", label: "Français" },
  { code: "ja-JP", label: "日本語" },
  { code: "pt-BR", label: "Português" },
] as const;

export const short = (bcp47: string) => bcp47.split("-")[0];

// ------------------------------------------------------------------ speech to text

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function recognitionCtor(): (new () => Recognition) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as (new () => Recognition) | null;
}

export function useSpeechToText(lang: string, onFinal: (text: string) => void) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const finalRef = useRef(onFinal);
  finalRef.current = onFinal;

  useEffect(() => setSupported(!!recognitionCtor()), []);

  const stop = useCallback(() => {
    rec.current?.stop();
  }, []);

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) {
      setError("Voice input needs Chrome or Edge.");
      return;
    }
    rec.current?.abort();
    const r = new Ctor();
    r.lang = lang;
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (e) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalRef.current(res[0].transcript.trim());
        else live += res[0].transcript;
      }
      setInterim(live);
    };
    r.onerror = (e) => {
      setError(e.error === "not-allowed" ? "Microphone permission was denied." : `Voice input stopped (${e.error}).`);
    };
    r.onend = () => {
      setListening(false);
      setInterim("");
    };
    setError(null);
    rec.current = r;
    r.start();
    setListening(true);
  }, [lang]);

  useEffect(() => () => rec.current?.abort(), []);
  return { supported, listening, interim, error, start, stop };
}

// ------------------------------------------------------------------ text to speech

export function speechSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string, lang: string, onEnd?: () => void) {
  if (!speechSupported()) return false;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  const voice =
    synth.getVoices().find((v) => v.lang === lang) ?? synth.getVoices().find((v) => v.lang.startsWith(short(lang)));
  if (voice) u.voice = voice;
  u.rate = 1;
  if (onEnd) u.onend = onEnd;
  synth.speak(u);
  return true;
}

export function stopSpeaking() {
  if (speechSupported()) window.speechSynthesis.cancel();
}

// ------------------------------------------------------------------ translation

type TranslatorApi = {
  availability?: (o: { sourceLanguage: string; targetLanguage: string }) => Promise<string>;
  create: (o: { sourceLanguage: string; targetLanguage: string }) => Promise<{ translate: (t: string) => Promise<string> }>;
};

export async function translate(text: string, from: string, to: string, token?: string | null): Promise<{ text: string; engine: string }> {
  const src = short(from);
  const dst = short(to);
  if (src === dst) return { text, engine: "none" };
  const T = (globalThis as unknown as { Translator?: TranslatorApi }).Translator;
  if (T) {
    try {
      const avail = T.availability ? await T.availability({ sourceLanguage: src, targetLanguage: dst }) : "available";
      if (avail !== "unavailable") {
        const tr = await T.create({ sourceLanguage: src, targetLanguage: dst });
        return { text: await tr.translate(text), engine: "on-device" };
      }
    } catch {
      /* fall through to the server */
    }
  }
  try {
    const r = await api<{ text: string; engine: string }>("/v1/translate", {
      body: { text, source: from, target: to },
      token: token ?? undefined,
    });
    return r;
  } catch (e) {
    throw new ApiError(
      e instanceof ApiError ? e.status : 0,
      "TRANSLATION_UNAVAILABLE",
      "Translation isn't available here. Use Chrome 138+ (on-device) or set GEMINI_API_KEY on the API.",
    );
  }
}
