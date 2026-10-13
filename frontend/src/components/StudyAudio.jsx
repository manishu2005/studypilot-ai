import { useEffect, useState } from "react";

const LANGUAGE_OPTIONS = [
  { value: "en-IN", label: "English" },
  { value: "hi-IN", label: "Hindi" },
];

export default function StudyAudio({ text = "", language = "en-IN" }) {
  const [selectedLanguage, setSelectedLanguage] = useState(language);
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(false);

  useEffect(()=>{
    setSupported(
        typeof window !== "undefined" && 
        "speechSynthesis" in window &&
        "SpeechSynthesisUtterance" in window
    );
    return ()=>{
        if("speechSynthesis" in window){
            window.speechSynthesis.cancel();
        }
    }
  },[]);

  function stopAudio(){
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function playAudio(){
    const content = String(text).trim();
    if(!content || !supported) return

    stopAudio();

    const utterance = new SpeechSynthesisUtterance(content);
    utterance.lang = selectedLanguage;
    utterance.rate = 0.95;

    const voices = window.speechSynthesis.getVoices();
    const languagePrefix = selectedLanguage.split("-")[0];

    const preferredVoice = voices.find(
      (voice) => voice.lang.toLowerCase() === selectedLanguage.toLowerCase()
    ) || voices.find(
      (voice) => voice.lang.toLowerCase().startsWith(languagePrefix)
    );

    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  if (!supported) {
    return (
      <p role="status">
        Audio playback is not supported in this browser.
      </p>
    );
  }

  return (
    <section aria-label="Study audio controls">
      <label htmlFor="study-audio-language">Audio language</label>

      <select
        id="study-audio-language"
        value={selectedLanguage}
        onChange={(event) => {
          stopAudio();
          setSelectedLanguage(event.target.value);
        }}
      >
        {LANGUAGE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <button type="button" onClick={playAudio} disabled={!text.trim()}>
        Play explanation
      </button>

      <button
        type="button"
        onClick={stopAudio}
        disabled={!speaking}
      >
        Stop
      </button>

      <p role="status">
        {speaking ? "Audio is playing." : "Audio is stopped."}
      </p>
    </section>
  );
}