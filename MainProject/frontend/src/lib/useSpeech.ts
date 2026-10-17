import { useCallback, useEffect, useRef, useState } from "react";

// Minimal typings for the Web Speech API (not in lib.dom for all browsers).
interface SRResult { isFinal: boolean; 0: { transcript: string } }
interface SREvent { resultIndex: number; results: ArrayLike<SRResult> }
interface SRInstance {
  lang: string; continuous: boolean; interimResults: boolean;
  start(): void; stop(): void; abort(): void;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}
type SRCtor = new () => SRInstance;

const speechLang = (lang: string) => (lang === "hi" ? "hi-IN" : "en-IN");

export function getRecognitionCtor(): SRCtor | null {
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Speech-to-text with graceful fallback: `supported` is false where the browser has no API,
 *  and permission or network errors surface as a readable `error` so the UI can switch to typing. */
export function useSpeechToText(lang: string, onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<SRInstance | null>(null);
  const supported = typeof window !== "undefined" && !!getRecognitionCtor();
  const finalCb = useRef(onFinal);
  finalCb.current = onFinal;

  const stop = useCallback(() => {
    rec.current?.stop();
    setListening(false);
    setInterim("");
  }, []);

  const start = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) { setError("Voice input isn't supported in this browser. Chrome or Edge work best; you can type instead."); return; }
    setError(null);
    const r = new Ctor();
    r.lang = speechLang(lang);
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (e) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalCb.current(res[0].transcript.trim());
        else live += res[0].transcript;
      }
      setInterim(live);
    };
    r.onerror = (e) => {
      const map: Record<string, string> = {
        "not-allowed": "Microphone access is blocked. Allow it in the browser's site settings, or type your answer.",
        "service-not-allowed": "Microphone access is blocked. Allow it in the browser's site settings, or type your answer.",
        "audio-capture": "No microphone was found. Connect one, or type your answer.",
        network: "Speech recognition needs an internet connection. You can type your answer instead.",
        "no-speech": "Didn't catch anything. Try again, a little closer to the microphone.",
      };
      if (e.error !== "aborted") setError(map[e.error] ?? "Voice input stopped unexpectedly. You can keep typing.");
      setListening(false);
    };
    r.onend = () => { setListening(false); setInterim(""); };
    try {
      r.start();
      rec.current = r;
      setListening(true);
    } catch {
      setError("Couldn't start the microphone. You can type your answer instead.");
    }
  }, [lang]);

  useEffect(() => () => rec.current?.abort(), []);
  return { supported, listening, interim, error, start, stop, clearError: () => setError(null) };
}

export function useTextToSpeech(lang: string) {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [speaking, setSpeaking] = useState(false);

  const speak = useCallback((text: string) => {
    if (!supported || !text) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = speechLang(lang);
    const voices = window.speechSynthesis.getVoices();
    const v = voices.find((x) => x.lang === u.lang) ?? voices.find((x) => x.lang.startsWith(lang === "hi" ? "hi" : "en"));
    if (v) u.voice = v;
    u.rate = 0.98;
    u.onstart = () => setSpeaking(true);
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
  }, [lang, supported]);

  const cancel = useCallback(() => { if (supported) window.speechSynthesis.cancel(); setSpeaking(false); }, [supported]);
  useEffect(() => () => { if (supported) window.speechSynthesis.cancel(); }, [supported]);
  return { supported, speaking, speak, cancel };
}
